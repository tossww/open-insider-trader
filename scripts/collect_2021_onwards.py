"""
Comprehensive Data Collection from 2021 Onwards

Collects ALL insider trading data from 2021 to present with proper:
- Method name fixes (parse_form4_xml instead of parse_form4)
- Pagination to bypass 100-filing SEC API limit
- Error handling and logging
- Progress tracking
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List
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
        logging.FileHandler('data/collection_2021_onwards.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# All tickers from config
ALL_TICKERS = [
    # Technology
    'AAPL', 'MSFT', 'GOOGL', 'META', 'NVDA', 'AMD', 'INTC', 'TSLA', 'ORCL', 'CRM', 'ADBE', 'CSCO',
    # Finance
    'JPM', 'BAC', 'WFC', 'C', 'GS', 'MS', 'BLK', 'SCHW', 'AXP',
    # Healthcare
    'JNJ', 'UNH', 'PFE', 'ABBV', 'TMO', 'ABT', 'MRK', 'LLY',
    # Consumer
    'AMZN', 'WMT', 'HD', 'NKE', 'MCD', 'SBUX', 'TGT', 'COST',
    # Industrials
    'BA', 'CAT', 'GE', 'HON', 'UPS', 'LMT', 'MMM',
    # Energy
    'XOM', 'CVX', 'COP', 'SLB', 'EOG',
    # Telecom
    'T', 'VZ', 'TMUS',
    # Materials
    'LIN', 'APD', 'ECL', 'DD'
]

# Prioritize missing tickers
PRIORITY_TICKERS = ['AMD', 'META', 'NVDA']


def get_or_create_company(session, ticker: str, cik: str) -> Company:
    """Get existing company or create new one."""
    company = session.query(Company).filter_by(ticker=ticker).first()
    if not company:
        company = Company(ticker=ticker, name=ticker, cik=cik)
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


def collect_ticker_data(
    ticker: str,
    sec_client: SECEdgarClient,
    market_cap_fetcher: MarketCapFetcher,
    parser: Form4Parser,
    start_date: datetime,
    end_date: datetime,
    force_recollect: bool = False
) -> Dict:
    """
    Collect ALL Form 4 filings for a ticker from start_date onwards.

    Returns dict with statistics.
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing {ticker}")
    logger.info(f"{'='*60}")

    # Get CIK
    cik = sec_client.get_company_cik(ticker)
    if not cik:
        logger.error(f"❌ Could not find CIK for {ticker}")
        return {'ticker': ticker, 'filings': 0, 'transactions': 0, 'error': 'No CIK'}

    logger.info(f"✓ Found CIK: {cik}")

    session = get_session()

    try:
        # Get or create company
        company = get_or_create_company(session, ticker, cik)

        # Check existing data
        existing_txn_count = session.query(InsiderTransaction).filter(
            InsiderTransaction.company_id == company.id,
            InsiderTransaction.trade_date >= start_date
        ).count()

        if not force_recollect and existing_txn_count > 100:
            logger.info(f"ℹ️  {ticker} already has {existing_txn_count} transactions from {start_date.date()}, skipping...")
            session.close()
            return {'ticker': ticker, 'filings': 0, 'transactions': existing_txn_count, 'skipped': True}

        # Collect filings in 6-month chunks to avoid 100-filing limit
        all_filings = []
        current_start = start_date

        while current_start < end_date:
            current_end = min(current_start + timedelta(days=180), end_date)  # 6 month chunks

            logger.info(f"  📅 Fetching {current_start.date()} to {current_end.date()}...")
            filings_chunk = sec_client.get_form4_filings(cik, current_start, current_end)

            if filings_chunk:
                logger.info(f"    ✓ Found {len(filings_chunk)} filings")
                all_filings.extend(filings_chunk)

            current_start = current_end

        if not all_filings:
            logger.info(f"ℹ️  No Form 4 filings found for {ticker}")
            session.close()
            return {'ticker': ticker, 'filings': 0, 'transactions': 0}

        logger.info(f"  ✓ Total filings to process: {len(all_filings)}")

        # Process each filing
        filing_count = 0
        transaction_count = 0
        parse_errors = 0

        for i, filing_meta in enumerate(all_filings, 1):
            if i % 25 == 0:
                logger.info(f"  Progress: {i}/{len(all_filings)} filings ({transaction_count} transactions so far)")

            # Check if already processed
            existing = session.query(RawForm4Filing).filter_by(
                accession_number=filing_meta['accession_number']
            ).first()

            if existing:
                continue

            # Fetch Form 4 XML
            xml_content = sec_client.get_form4_xml(filing_meta['filing_url'])
            if not xml_content:
                logger.warning(f"  ⚠️  Failed to fetch XML for {filing_meta['accession_number']}")
                continue

            # Parse Form 4 (FIXED: use parse_form4_xml, not parse_form4)
            try:
                insider_trade = parser.parse_form4_xml(
                    xml_content,
                    filing_meta['filing_url'],
                    filing_meta['filing_date']
                )

                if not insider_trade or not insider_trade.transactions:
                    continue

            except Exception as e:
                parse_errors += 1
                logger.warning(f"  ⚠️  Parse error for {filing_meta['accession_number']}: {e}")
                continue

            # Store filing and transactions
            try:
                # Create/get insider
                insider = get_or_create_insider(session, insider_trade.owner_info, company.id)

                # Parse filing date to datetime
                filing_date_obj = datetime.strptime(filing_meta['filing_date'], '%Y-%m-%d')

                # Store filing (schema: no company_id or insider_id!)
                filing = RawForm4Filing(
                    accession_number=filing_meta['accession_number'],
                    filing_date=filing_date_obj,
                    filing_url=filing_meta['filing_url'],
                    xml_content=xml_content,
                    is_amendment=insider_trade.is_amendment
                )
                session.add(filing)
                session.flush()

                # Store transactions
                for txn in insider_trade.transactions:
                    # Parse date string to datetime if needed
                    trade_date_obj = None
                    if txn.transaction_date:
                        try:
                            trade_date_obj = datetime.strptime(txn.transaction_date, '%Y-%m-%d')
                        except ValueError:
                            pass

                    # Schema uses form4_filing_id, not filing_id
                    transaction = InsiderTransaction(
                        company_id=company.id,
                        insider_id=insider.id,
                        form4_filing_id=filing.id,
                        trade_date=trade_date_obj,
                        filing_date=filing_date_obj,
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

                    # Fetch market cap (best effort)
                    if trade_date_obj:
                        try:
                            market_cap = market_cap_fetcher.get_market_cap(ticker, trade_date_obj)
                            if market_cap:
                                mc_record = MarketCap(
                                    company_id=company.id,
                                    date=trade_date_obj,
                                    market_cap_usd=market_cap
                                )
                                session.add(mc_record)
                        except:
                            pass

                filing_count += 1

                # Commit every 50 filings to avoid memory issues
                if filing_count % 50 == 0:
                    session.commit()

            except Exception as e:
                logger.error(f"  ❌ Error storing filing {filing_meta['accession_number']}: {e}")
                session.rollback()
                continue

        # Final commit
        session.commit()

        logger.info(f"\n✅ {ticker} COMPLETE:")
        logger.info(f"  • Filings processed: {filing_count}")
        logger.info(f"  • Transactions stored: {transaction_count}")
        if parse_errors > 0:
            logger.info(f"  • Parse errors: {parse_errors}")

        return {
            'ticker': ticker,
            'filings': filing_count,
            'transactions': transaction_count,
            'parse_errors': parse_errors
        }

    except Exception as e:
        logger.error(f"❌ Fatal error processing {ticker}: {e}")
        session.rollback()
        return {'ticker': ticker, 'filings': 0, 'transactions': 0, 'error': str(e)}
    finally:
        session.close()


def main():
    """Main collection process."""
    print("\n" + "="*80)
    print("🎯 COMPREHENSIVE DATA COLLECTION - 2021 ONWARDS")
    print("="*80)

    # Initialize database
    init_db()

    # Date range: 2021-01-01 to now
    start_date = datetime(2021, 1, 1)
    end_date = datetime.now()

    print(f"\n📅 Date Range: {start_date.date()} to {end_date.date()}")
    print(f"📊 Total tickers: {len(ALL_TICKERS)}")
    print(f"🎯 Priority (missing data): {', '.join(PRIORITY_TICKERS)}")
    print(f"🔧 Strategy: 6-month chunks to bypass 100-filing limit\n")

    # Initialize clients
    sec_config = {
        'base_url': 'https://www.sec.gov/cgi-bin/browse-edgar',
        'user_agent': 'Open InsiderTrader research tossww-studio@gmail.com',
        'rate_limit_per_second': 10
    }
    sec_client = SECEdgarClient(sec_config)
    market_cap_fetcher = MarketCapFetcher()
    parser = Form4Parser()

    # Prioritize missing tickers
    prioritized_tickers = PRIORITY_TICKERS + [t for t in ALL_TICKERS if t not in PRIORITY_TICKERS]

    results = []
    start_time = time.time()

    # Process each ticker
    for i, ticker in enumerate(prioritized_tickers, 1):
        print(f"\n[{i}/{len(prioritized_tickers)}] {ticker}")
        print("-" * 60)

        result = collect_ticker_data(
            ticker,
            sec_client,
            market_cap_fetcher,
            parser,
            start_date,
            end_date,
            force_recollect=False
        )

        results.append(result)

    # Summary
    elapsed = time.time() - start_time
    total_filings = sum(r.get('filings', 0) for r in results)
    total_transactions = sum(r.get('transactions', 0) for r in results)
    total_errors = sum(r.get('parse_errors', 0) for r in results)
    skipped = sum(1 for r in results if r.get('skipped', False))
    failed = [r for r in results if 'error' in r]

    print("\n" + "="*80)
    print("✅ COLLECTION COMPLETE")
    print("="*80)
    print(f"⏱️  Time elapsed: {elapsed/60:.1f} minutes")
    print(f"📄 Total filings: {total_filings:,}")
    print(f"💼 Total transactions: {total_transactions:,}")
    print(f"⏭️  Skipped (already collected): {skipped}")
    if total_errors > 0:
        print(f"⚠️  Parse errors: {total_errors}")

    if failed:
        print(f"\n❌ {len(failed)} tickers had fatal errors:")
        for r in failed:
            print(f"  • {r['ticker']}: {r.get('error', 'Unknown')}")

    print(f"\n📊 Detailed log: data/collection_2021_onwards.log")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
