"""
5-Year Historical Data Collection Script

Collects Form 4 insider trading data from the past 5 years across
diverse sectors to enable statistically valid backtesting.

Features:
- Progress tracking with checkpoint system
- Resume capability if interrupted
- Rate limiting to respect SEC API limits
- Comprehensive logging
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import logging
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List
import yaml
from collectors.sec_edgar import SECEdgarClient
from collectors.market_cap import MarketCapFetcher
from processors.form4_parser import Form4Parser
from database.connection import init_db, get_session
from database.schema import Company, Insider, RawForm4Filing, InsiderTransaction, MarketCap

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/collection_5year.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# Comprehensive ticker list across sectors
TICKER_LIST = {
    'Technology': ['AAPL', 'MSFT', 'GOOGL', 'META', 'NVDA', 'AMD', 'INTC', 'TSLA', 'ORCL', 'CRM', 'ADBE', 'CSCO'],
    'Finance': ['JPM', 'BAC', 'WFC', 'C', 'GS', 'MS', 'BLK', 'SCHW', 'AXP'],
    'Healthcare': ['JNJ', 'UNH', 'PFE', 'ABBV', 'TMO', 'ABT', 'MRK', 'LLY'],
    'Consumer': ['AMZN', 'WMT', 'HD', 'NKE', 'MCD', 'SBUX', 'TGT', 'COST'],
    'Industrials': ['BA', 'CAT', 'GE', 'HON', 'UPS', 'LMT', 'MMM'],
    'Energy': ['XOM', 'CVX', 'COP', 'SLB', 'EOG'],
    'Telecom': ['T', 'VZ', 'TMUS'],
    'Materials': ['LIN', 'APD', 'ECL', 'DD']
}

# Flatten ticker list
ALL_TICKERS = [ticker for sector in TICKER_LIST.values() for ticker in sector]


class ProgressTracker:
    """Track and persist collection progress."""

    def __init__(self, checkpoint_file: str = 'data/collection_progress.json'):
        self.checkpoint_file = checkpoint_file
        self.progress = self._load_progress()

    def _load_progress(self) -> Dict:
        """Load progress from checkpoint file."""
        if Path(self.checkpoint_file).exists():
            with open(self.checkpoint_file, 'r') as f:
                return json.load(f)
        return {
            'completed_tickers': [],
            'failed_tickers': [],
            'total_filings': 0,
            'total_transactions': 0,
            'last_updated': None
        }

    def save_progress(self):
        """Save current progress to checkpoint file."""
        self.progress['last_updated'] = datetime.now().isoformat()
        with open(self.checkpoint_file, 'w') as f:
            json.dump(self.progress, f, indent=2)

    def mark_ticker_complete(self, ticker: str, filings: int, transactions: int):
        """Mark a ticker as completed."""
        if ticker not in self.progress['completed_tickers']:
            self.progress['completed_tickers'].append(ticker)
        self.progress['total_filings'] += filings
        self.progress['total_transactions'] += transactions
        self.save_progress()

    def mark_ticker_failed(self, ticker: str, error: str):
        """Mark a ticker as failed."""
        self.progress['failed_tickers'].append({'ticker': ticker, 'error': error})
        self.save_progress()

    def is_ticker_complete(self, ticker: str) -> bool:
        """Check if ticker already processed."""
        return ticker in self.progress['completed_tickers']

    def get_remaining_tickers(self, all_tickers: List[str]) -> List[str]:
        """Get list of tickers not yet processed."""
        return [t for t in all_tickers if not self.is_ticker_complete(t)]


def get_or_create_company(session, ticker: str, name: str, cik: str) -> Company:
    """Get existing company or create new one."""
    company = session.query(Company).filter_by(ticker=ticker).first()
    if not company:
        company = Company(ticker=ticker, name=name, cik=cik)
        session.add(company)
        session.flush()
    return company


def get_or_create_insider(session, owner_info, company_id: int) -> Insider:
    """Get existing insider or create new one."""
    insider = session.query(Insider).filter_by(
        name=owner_info.name,
        cik=owner_info.cik,
        company_id=company_id
    ).first()

    if not insider:
        insider = Insider(
            name=owner_info.name,
            cik=owner_info.cik,
            company_id=company_id,
            is_director=owner_info.is_director,
            is_officer=owner_info.is_officer,
            is_ten_percent_owner=owner_info.is_ten_percent_owner,
            officer_title=owner_info.officer_title
        )
        session.add(insider)
        session.flush()

    return insider


def store_insider_trade(session, insider_trade, company_id: int, insider_id: int, accession_number: str) -> int:
    """Store insider trade and transactions in database."""

    # Check if filing already exists
    existing_filing = session.query(RawForm4Filing).filter_by(
        accession_number=accession_number
    ).first()

    if existing_filing:
        return 0

    # Create filing record
    filing = RawForm4Filing(
        filing_url=insider_trade.filing_url,
        accession_number=accession_number,
        filing_date=datetime.strptime(insider_trade.filing_date, '%Y-%m-%d'),
        xml_content="",
        is_amendment=insider_trade.is_amendment
    )
    session.add(filing)
    session.flush()

    # Create transaction records
    transaction_count = 0
    for tx in insider_trade.transactions:
        transaction = InsiderTransaction(
            form4_filing_id=filing.id,
            insider_id=insider_id,
            company_id=company_id,
            trade_date=datetime.strptime(tx.transaction_date, '%Y-%m-%d'),
            filing_date=datetime.strptime(insider_trade.filing_date, '%Y-%m-%d'),
            transaction_code=tx.transaction_code,
            acquisition_or_disposition=tx.acquisition_or_disposition,
            shares=tx.shares,
            price_per_share=tx.price_per_share,
            total_value=tx.total_value,
            security_title=tx.security_title,
            is_derivative=tx.is_derivative
        )
        session.add(transaction)
        transaction_count += 1

    return transaction_count


def store_market_cap(session, company_id: int, date: datetime, market_cap: float):
    """Store market cap data."""
    existing = session.query(MarketCap).filter_by(
        company_id=company_id,
        date=date.replace(hour=0, minute=0, second=0, microsecond=0)
    ).first()

    if existing:
        return

    market_cap_record = MarketCap(
        company_id=company_id,
        date=date.replace(hour=0, minute=0, second=0, microsecond=0),
        market_cap_usd=market_cap
    )
    session.add(market_cap_record)


def process_ticker(
    ticker: str,
    sec_client: SECEdgarClient,
    parser: Form4Parser,
    market_cap_fetcher: MarketCapFetcher,
    session,
    start_date: datetime,
    end_date: datetime
) -> tuple[int, int]:
    """
    Process all Form 4 filings for a ticker.

    Returns:
        Tuple of (filings_count, transactions_count)
    """
    logger.info(f"Processing {ticker}...")

    # Get CIK
    cik = sec_client.get_company_cik(ticker)
    if not cik:
        raise ValueError(f"Could not find CIK for {ticker}")

    # Get filings
    filings = sec_client.get_form4_filings(cik, start_date, end_date)
    logger.info(f"  Found {len(filings)} filings for {ticker}")

    if not filings:
        return 0, 0

    filings_processed = 0
    transactions_created = 0

    # Process each filing
    for idx, filing in enumerate(filings, 1):
        try:
            # Progress indicator every 10 filings
            if idx % 10 == 0:
                logger.info(f"  Progress: {idx}/{len(filings)} filings processed")

            # Download XML
            xml_content = sec_client.get_form4_xml(filing['filing_url'])
            if not xml_content:
                continue

            # Parse
            insider_trade = parser.parse_form4_xml(
                xml_content,
                filing['filing_url'],
                filing['filing_date']
            )

            if not insider_trade or not insider_trade.transactions:
                continue

            # Get or create company
            company = get_or_create_company(
                session,
                ticker,
                insider_trade.issuer_name or ticker,
                cik
            )

            # Get or create insider
            insider = get_or_create_insider(
                session,
                insider_trade.owner_info,
                company.id
            )

            # Store trade
            tx_count = store_insider_trade(
                session,
                insider_trade,
                company.id,
                insider.id,
                filing['accession_number']
            )

            if tx_count > 0:
                filings_processed += 1
                transactions_created += tx_count

                # Fetch market cap for filing date
                filing_date = datetime.strptime(filing['filing_date'], '%Y-%m-%d')
                market_cap = market_cap_fetcher.get_market_cap_at_date(ticker, filing_date)

                if market_cap:
                    store_market_cap(session, company.id, filing_date, market_cap)

            # Commit every 50 filings to avoid losing progress
            if idx % 50 == 0:
                session.commit()

        except Exception as e:
            logger.warning(f"  Error processing filing {filing.get('filing_url', 'unknown')}: {e}")
            continue

    # Final commit for this ticker
    session.commit()

    logger.info(f"  ✅ {ticker}: {filings_processed} filings, {transactions_created} transactions")
    return filings_processed, transactions_created


def main():
    """Main 5-year collection script."""
    print("=" * 80)
    print("5-YEAR HISTORICAL DATA COLLECTION")
    print("=" * 80)
    print()

    # Load config
    config_path = Path(__file__).parent.parent / 'config.yaml'
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Date range: 5 years back from today
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5*365)

    print(f"📅 Date Range: {start_date.date()} to {end_date.date()}")
    print(f"📊 Tickers: {len(ALL_TICKERS)} across {len(TICKER_LIST)} sectors")
    print(f"⏱️  Estimated time: 2-4 hours (respecting SEC rate limits)")
    print()

    # Initialize database
    print("[1/4] Initializing database...")
    init_db()
    print("✅ Database initialized")

    # Initialize progress tracker
    print("\n[2/4] Loading progress tracker...")
    tracker = ProgressTracker()

    remaining = tracker.get_remaining_tickers(ALL_TICKERS)
    completed = len(tracker.progress['completed_tickers'])

    print(f"✅ Progress: {completed}/{len(ALL_TICKERS)} tickers complete")
    if completed > 0:
        print(f"   Resuming from checkpoint...")
        print(f"   Already collected: {tracker.progress['total_filings']} filings, "
              f"{tracker.progress['total_transactions']} transactions")
    print(f"   Remaining: {len(remaining)} tickers")
    print()

    # Initialize clients
    print("[3/4] Initializing API clients...")
    sec_config = config['data_sources']['sec_api']
    sec_client = SECEdgarClient(sec_config)
    parser = Form4Parser()
    market_cap_fetcher = MarketCapFetcher()
    print("✅ API clients ready")
    print()

    # Main collection loop
    print("[4/4] Collecting data...")
    print("=" * 80)

    session = get_session()
    start_time = time.time()

    try:
        for idx, ticker in enumerate(remaining, 1):
            print(f"\n[{idx}/{len(remaining)}] {ticker}")
            print("-" * 40)

            try:
                filings, transactions = process_ticker(
                    ticker,
                    sec_client,
                    parser,
                    market_cap_fetcher,
                    session,
                    start_date,
                    end_date
                )

                tracker.mark_ticker_complete(ticker, filings, transactions)

                # Estimate time remaining
                elapsed = time.time() - start_time
                avg_time_per_ticker = elapsed / idx
                remaining_time = avg_time_per_ticker * (len(remaining) - idx)
                eta_minutes = remaining_time / 60

                print(f"⏱️  ETA: {eta_minutes:.1f} minutes remaining")

            except Exception as e:
                logger.error(f"Failed to process {ticker}: {e}")
                tracker.mark_ticker_failed(ticker, str(e))
                continue

        # Final stats
        elapsed_total = time.time() - start_time
        print()
        print("=" * 80)
        print("✅ COLLECTION COMPLETE")
        print("=" * 80)
        print(f"⏱️  Total time: {elapsed_total/60:.1f} minutes")
        print(f"📊 Total filings: {tracker.progress['total_filings']}")
        print(f"📊 Total transactions: {tracker.progress['total_transactions']}")
        print()

        # Database stats
        print("📈 Database Summary:")
        company_count = session.query(Company).count()
        insider_count = session.query(Insider).count()
        transaction_count = session.query(InsiderTransaction).count()
        market_cap_count = session.query(MarketCap).count()

        print(f"   Companies: {company_count}")
        print(f"   Insiders: {insider_count}")
        print(f"   Transactions: {transaction_count}")
        print(f"   Market caps: {market_cap_count}")
        print()

        if tracker.progress['failed_tickers']:
            print(f"⚠️  Failed tickers: {len(tracker.progress['failed_tickers'])}")
            for fail in tracker.progress['failed_tickers']:
                print(f"   - {fail['ticker']}: {fail['error']}")
        print()

        print("Next step: Run signal generation and backtesting with full dataset")
        print("  python3 scripts/generate_signals.py --store-db")
        print("  python3 scripts/run_dashboard.py")

    except KeyboardInterrupt:
        print("\n\n⚠️  Collection interrupted by user")
        print(f"📊 Progress saved: {tracker.progress['total_filings']} filings collected")
        print("   Run script again to resume from checkpoint")

    except Exception as e:
        session.rollback()
        logger.error(f"Collection failed: {e}")
        raise

    finally:
        session.close()


if __name__ == '__main__':
    main()
