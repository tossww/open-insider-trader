"""
2-Year Historical Data Collection Script

Collects Form 4 insider trading data from the past 2 years across
diverse sectors for faster initial backtesting validation.

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
        logging.FileHandler('data/collection_2year.log'),
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

    def __init__(self, checkpoint_file: str = 'data/collection_progress_2year.json'):
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


def store_insider_trade(session, insider_trade, company_id: int, insider_id: int, accession_number: str, filing_url: str, filing_date_str: str, xml_content: str) -> int:
    """Store insider trade and transactions in database."""

    # Check if filing already exists
    existing_filing = session.query(RawForm4Filing).filter_by(
        accession_number=accession_number
    ).first()

    if existing_filing:
        logger.debug(f"Filing {accession_number} already exists, skipping")
        return 0

    # Parse filing date
    filing_date = datetime.strptime(filing_date_str, '%Y-%m-%d')

    # Create filing record
    filing = RawForm4Filing(
        accession_number=accession_number,
        filing_url=filing_url,
        filing_date=filing_date,
        xml_content=xml_content,
        is_amendment=insider_trade.is_amendment
    )
    session.add(filing)
    session.flush()

    # Store transactions
    transaction_count = 0
    for txn in insider_trade.transactions:
        transaction = InsiderTransaction(
            form4_filing_id=filing.id,
            insider_id=insider_id,
            company_id=company_id,
            trade_date=datetime.strptime(txn.transaction_date, '%Y-%m-%d'),
            filing_date=filing_date,
            transaction_code=txn.transaction_code,
            acquisition_or_disposition=txn.acquisition_or_disposition,
            shares=txn.shares,
            price_per_share=txn.price_per_share,
            total_value=txn.total_value,
            security_title=txn.security_title,
            is_derivative=txn.is_derivative
        )
        session.add(transaction)
        transaction_count += 1

    return transaction_count


def fetch_market_cap(session, company_id: int, ticker: str, filing_date: datetime, cap_fetcher: MarketCapFetcher):
    """Fetch and store market cap if not already present."""
    date_str = filing_date.strftime('%Y-%m-%d')

    # Check if already stored
    existing = session.query(MarketCap).filter_by(
        company_id=company_id,
        date=filing_date.replace(hour=0, minute=0, second=0, microsecond=0)
    ).first()

    if existing:
        return

    # Fetch market cap
    market_cap = cap_fetcher.get_market_cap_at_date(ticker, filing_date)

    if market_cap:
        cap_record = MarketCap(
            company_id=company_id,
            date=filing_date.replace(hour=0, minute=0, second=0, microsecond=0),
            market_cap_usd=market_cap
        )
        session.add(cap_record)
        logger.debug(f"Stored market cap for {ticker} on {date_str}: ${market_cap:,.0f}")


def collect_ticker_data(ticker: str, session, sec_client: SECEdgarClient,
                       parser: Form4Parser, cap_fetcher: MarketCapFetcher,
                       start_date: datetime, end_date: datetime) -> tuple[int, int]:
    """Collect all Form 4 filings for a single ticker within date range."""

    logger.info(f"Collecting data for {ticker}...")

    # Get CIK for ticker
    cik = sec_client.get_company_cik(ticker)
    if not cik:
        logger.error(f"Could not find CIK for {ticker}")
        return 0, 0

    # Fetch Form 4 filings
    filings = sec_client.get_form4_filings(
        cik=cik,
        start_date=start_date,
        end_date=end_date
    )

    if not filings:
        logger.warning(f"No filings found for {ticker}")
        return 0, 0

    logger.info(f"Found {len(filings)} filings for {ticker}")

    filing_count = 0
    transaction_count = 0

    for filing in filings:
        try:
            # Fetch and parse XML
            xml_content = sec_client.get_form4_xml(filing['filing_url'])
            if not xml_content:
                logger.warning(f"Could not fetch XML for {filing['accession_number']}")
                continue

            insider_trade = parser.parse_form4_xml(
                xml_content,
                filing['filing_url'],
                filing['filing_date']
            )
            if not insider_trade:
                logger.warning(f"Could not parse {filing['accession_number']}")
                continue

            # Store company
            company = get_or_create_company(
                session,
                ticker=ticker,
                name=insider_trade.issuer_name or ticker,
                cik=cik
            )

            # Store insider
            insider = get_or_create_insider(
                session,
                owner_info=insider_trade.owner_info,
                company_id=company.id
            )

            # Store trade and transactions
            txn_count = store_insider_trade(
                session,
                insider_trade,
                company.id,
                insider.id,
                filing['accession_number'],
                filing['filing_url'],
                filing['filing_date'],
                xml_content
            )

            if txn_count > 0:
                filing_count += 1
                transaction_count += txn_count

                # Fetch market cap
                filing_dt = datetime.strptime(filing['filing_date'], '%Y-%m-%d')
                fetch_market_cap(session, company.id, ticker, filing_dt, cap_fetcher)

                # Commit every 50 filings
                if filing_count % 50 == 0:
                    session.commit()
                    logger.info(f"{ticker}: Processed {filing_count} filings, {transaction_count} transactions")

            # Rate limit: 10 requests per second
            time.sleep(0.1)

        except Exception as e:
            logger.error(f"Error processing {filing['accession_number']}: {e}")
            continue

    # Final commit
    session.commit()
    logger.info(f"✓ {ticker} complete: {filing_count} filings, {transaction_count} transactions")

    return filing_count, transaction_count


def main():
    """Main collection workflow."""

    # Load config
    config_path = Path(__file__).parent.parent / 'config.yaml'
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Initialize database
    logger.info("Initializing database...")
    init_db()

    # Initialize components
    sec_client = SECEdgarClient(config)
    parser = Form4Parser()
    cap_fetcher = MarketCapFetcher()
    tracker = ProgressTracker()

    # Date range: Last 2 years
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730)  # ~2 years

    logger.info(f"Collection period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    logger.info(f"Total tickers: {len(ALL_TICKERS)}")

    # Get remaining tickers
    remaining_tickers = tracker.get_remaining_tickers(ALL_TICKERS)
    logger.info(f"Remaining tickers: {len(remaining_tickers)}")

    if tracker.progress['completed_tickers']:
        logger.info(f"Resuming from previous run. Already completed: {len(tracker.progress['completed_tickers'])}")

    # Process each ticker
    session = get_session()

    for idx, ticker in enumerate(remaining_tickers, 1):
        try:
            logger.info(f"\n[{idx}/{len(remaining_tickers)}] Processing {ticker}...")

            filings, transactions = collect_ticker_data(
                ticker=ticker,
                session=session,
                sec_client=sec_client,
                parser=parser,
                cap_fetcher=cap_fetcher,
                start_date=start_date,
                end_date=end_date
            )

            tracker.mark_ticker_complete(ticker, filings, transactions)

        except Exception as e:
            logger.error(f"Failed to process {ticker}: {e}")
            tracker.mark_ticker_failed(ticker, str(e))
            continue

    # Final summary
    logger.info("\n" + "="*60)
    logger.info("Collection Complete!")
    logger.info(f"Total tickers processed: {len(tracker.progress['completed_tickers'])}")
    logger.info(f"Total filings: {tracker.progress['total_filings']}")
    logger.info(f"Total transactions: {tracker.progress['total_transactions']}")
    logger.info(f"Failed tickers: {len(tracker.progress['failed_tickers'])}")
    logger.info("="*60)

    session.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nCollection interrupted by user. Progress saved. Run again to resume.")
    except Exception as e:
        logger.error(f"Collection failed: {e}", exc_info=True)
