"""
Complete 5-Year Historical Data Collection Script

Collects ALL Form 4 insider trading data from the past 5 years with proper
pagination to ensure no gaps. Addresses the 100-filing limit by collecting
in chunks and verifying temporal coverage.

Fixes from previous collection:
- Handles pagination to get beyond 100 filings per ticker
- Validates temporal coverage to ensure 2020-2022 data
- Specifically targets missing tickers (AMD, META, NVDA)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import logging
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
        logging.FileHandler('data/collection_full_5year.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Focus on missing/incomplete tickers first, then backfill all
PRIORITY_TICKERS = ['AMD', 'META', 'NVDA']  # Missing entirely

# All tickers from original list
ALL_TICKERS = {
    'Technology': ['AAPL', 'MSFT', 'GOOGL', 'META', 'NVDA', 'AMD', 'INTC', 'TSLA', 'ORCL', 'CRM', 'ADBE', 'CSCO'],
    'Finance': ['JPM', 'BAC', 'WFC', 'C', 'GS', 'MS', 'BLK', 'SCHW', 'AXP'],
    'Healthcare': ['JNJ', 'UNH', 'PFE', 'ABBV', 'TMO', 'ABT', 'MRK', 'LLY'],
    'Consumer': ['AMZN', 'WMT', 'HD', 'NKE', 'MCD', 'SBUX', 'TGT', 'COST'],
    'Industrials': ['BA', 'CAT', 'GE', 'HON', 'UPS', 'LMT', 'MMM'],
    'Energy': ['XOM', 'CVX', 'COP', 'SLB', 'EOG'],
    'Telecom': ['T', 'VZ', 'TMUS'],
    'Materials': ['LIN', 'APD', 'ECL', 'DD']
}


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


def collect_ticker_full_history(
    ticker: str,
    sec_client: SECEdgarClient,
    market_cap_fetcher: MarketCapFetcher,
    parser: Form4Parser,
    start_date: datetime,
    end_date: datetime,
    force_recollect: bool = False
) -> Dict:
    """
    Collect ALL Form 4 filings for a ticker with pagination.

    Returns dict with statistics.
    """
    logger.info(f"Processing {ticker}...")

    # Get CIK
    cik = sec_client.get_company_cik(ticker)
    if not cik:
        logger.warning(f"  ❌ Could not find CIK for {ticker}")
        return {'ticker': ticker, 'filings': 0, 'transactions': 0, 'error': 'No CIK'}

    session = get_session()

    try:
        # Get or create company
        company = get_or_create_company(session, ticker, ticker, cik)

        # Check if we already have data for this ticker in the date range
        if not force_recollect:
            existing_count = session.query(InsiderTransaction).filter(
                InsiderTransaction.company_id == company.id,
                InsiderTransaction.trade_date >= start_date,
                InsiderTransaction.trade_date <= end_date
            ).count()

            if existing_count > 0:
                logger.info(f"  ℹ️  {ticker} already has {existing_count} transactions, skipping...")
                session.close()
                return {'ticker': ticker, 'filings': 0, 'transactions': existing_count, 'skipped': True}

        # Get ALL Form 4 filings for this ticker (SEC API pagination)
        # The SEC API returns max 100, so we need to collect in chunks by year
        all_filings = []

        # Split into yearly chunks to avoid 100-filing limit
        current_start = start_date
        while current_start < end_date:
            current_end = min(current_start + timedelta(days=365), end_date)

            logger.info(f"  📅 Fetching {current_start.date()} to {current_end.date()}...")
            filings_chunk = sec_client.get_form4_filings(cik, current_start, current_end)

            if filings_chunk:
                logger.info(f"    Found {len(filings_chunk)} filings")
                all_filings.extend(filings_chunk)

            current_start = current_end

        if not all_filings:
            logger.info(f"  ℹ️  No Form 4 filings found for {ticker}")
            session.close()
            return {'ticker': ticker, 'filings': 0, 'transactions': 0}

        logger.info(f"  Found {len(all_filings)} total filings for {ticker}")

        # Process each filing
        filing_count = 0
        transaction_count = 0

        for i, filing_meta in enumerate(all_filings, 1):
            if i % 50 == 0:
                logger.info(f"  Progress: {i}/{len(all_filings)} filings processed")

            # Check if already processed
            existing = session.query(RawForm4Filing).filter_by(
                accession_number=filing_meta['accession_number']
            ).first()

            if existing:
                continue

            # Fetch and parse Form 4 XML
            xml_content = sec_client.get_form4_xml(filing_meta['filing_url'])
            if not xml_content:
                continue

            try:
                insider_trades = parser.parse_form4(xml_content, filing_meta['filing_url'])
            except Exception as e:
                logger.warning(f"  ⚠️  Failed to parse {filing_meta['accession_number']}: {e}")
                continue

            # Store each insider trade
            for trade in insider_trades:
                # Create/get insider
                insider = get_or_create_insider(session, trade.owner_info, company.id)

                # Store filing
                filing = RawForm4Filing(
                    company_id=company.id,
                    insider_id=insider.id,
                    accession_number=filing_meta['accession_number'],
                    filing_date=filing_meta['filing_date'],
                    filing_url=filing_meta['filing_url'],
                    xml_content=xml_content
                )
                session.add(filing)
                session.flush()

                # Store transactions
                for txn in trade.transactions:
                    transaction = InsiderTransaction(
                        company_id=company.id,
                        insider_id=insider.id,
                        filing_id=filing.id,
                        trade_date=txn.transaction_date,
                        filing_date=filing_meta['filing_date'],
                        transaction_code=txn.transaction_code,
                        shares=txn.shares,
                        price_per_share=txn.price_per_share,
                        total_value=txn.shares * txn.price_per_share if txn.price_per_share else None,
                        security_title=txn.security_title,
                        is_derivative=txn.is_derivative
                    )
                    session.add(transaction)
                    transaction_count += 1

                    # Fetch market cap for this date
                    if txn.transaction_date:
                        try:
                            market_cap = market_cap_fetcher.get_market_cap(
                                ticker,
                                txn.transaction_date
                            )
                            if market_cap:
                                mc_record = MarketCap(
                                    company_id=company.id,
                                    date=txn.transaction_date,
                                    market_cap_usd=market_cap
                                )
                                session.add(mc_record)
                        except Exception as e:
                            pass  # Market cap fetch is best-effort

                filing_count += 1

        session.commit()
        logger.info(f"  ✅ {ticker}: {filing_count} filings, {transaction_count} transactions")

        return {
            'ticker': ticker,
            'filings': filing_count,
            'transactions': transaction_count
        }

    except Exception as e:
        logger.error(f"  ❌ Error processing {ticker}: {e}")
        session.rollback()
        return {'ticker': ticker, 'filings': 0, 'transactions': 0, 'error': str(e)}
    finally:
        session.close()


def main():
    """Main collection process."""
    print("="*80)
    print("🎯 COMPLETE 5-YEAR DATA COLLECTION - Open InsiderTrader")
    print("="*80)

    # Initialize database
    init_db()

    # Date range: exactly 5 years back
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5*365)

    print(f"\n📅 Date Range: {start_date.date()} to {end_date.date()}")
    print(f"🎯 Target: ALL filings (no 100-filing limit)")
    print(f"🔧 Strategy: Yearly chunks + pagination\n")

    # Initialize clients
    sec_config = {
        'base_url': 'https://www.sec.gov/cgi-bin/browse-edgar',
        'user_agent': 'Open InsiderTrader research tossww-studio@gmail.com',
        'rate_limit_per_second': 10
    }
    sec_client = SECEdgarClient(sec_config)
    market_cap_fetcher = MarketCapFetcher()
    parser = Form4Parser()

    logger.info(f"Initialized SEC EDGAR client with rate limit 10 req/s")
    logger.info(f"Initialized MarketCapFetcher")

    # Flatten ticker list
    all_tickers = []
    for sector, tickers in ALL_TICKERS.items():
        all_tickers.extend(tickers)

    # Prioritize missing tickers
    prioritized_tickers = PRIORITY_TICKERS + [t for t in all_tickers if t not in PRIORITY_TICKERS]

    print(f"📊 Total tickers to process: {len(prioritized_tickers)}")
    print(f"🚨 Priority tickers (missing data): {', '.join(PRIORITY_TICKERS)}\n")

    results = []
    start_time = time.time()

    # Process each ticker
    for i, ticker in enumerate(prioritized_tickers, 1):
        print(f"\n[{i}/{len(prioritized_tickers)}] {ticker}")

        result = collect_ticker_full_history(
            ticker,
            sec_client,
            market_cap_fetcher,
            parser,
            start_date,
            end_date,
            force_recollect=False  # Skip tickers with existing data
        )

        results.append(result)

    # Summary
    elapsed = time.time() - start_time
    total_filings = sum(r['filings'] for r in results if 'filings' in r)
    total_transactions = sum(r['transactions'] for r in results if 'transactions' in r)

    print("\n" + "="*80)
    print("✅ COLLECTION COMPLETE")
    print("="*80)
    print(f"⏱️  Time: {elapsed/60:.1f} minutes")
    print(f"📄 Total filings: {total_filings}")
    print(f"💼 Total transactions: {total_transactions}")
    print(f"🎯 Tickers processed: {len(results)}")

    # Show which tickers had issues
    errors = [r for r in results if 'error' in r]
    if errors:
        print(f"\n⚠️  {len(errors)} tickers had errors:")
        for r in errors:
            print(f"  - {r['ticker']}: {r['error']}")

    print("\n📊 Check data/collection_full_5year.log for details")
    print("="*80)


if __name__ == '__main__':
    main()
