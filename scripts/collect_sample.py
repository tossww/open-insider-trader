"""
Phase 2: Sample Data Collection Script

Collect 1 month of Form 4 data for 5 tickers and store in database with market caps.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import logging
from datetime import datetime, timedelta
import yaml
from collectors.sec_edgar import SECEdgarClient
from collectors.market_cap import MarketCapFetcher
from processors.form4_parser import Form4Parser
from database.connection import init_db, get_session
from database.schema import Company, Insider, RawForm4Filing, InsiderTransaction, MarketCap

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def get_or_create_company(session, ticker: str, name: str, cik: str) -> Company:
    """Get existing company or create new one."""
    company = session.query(Company).filter_by(ticker=ticker).first()
    if not company:
        company = Company(ticker=ticker, name=name, cik=cik)
        session.add(company)
        session.flush()
        logger.info(f"Created company: {ticker}")
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
        logger.info(f"Created insider: {owner_info.name}")

    return insider


def store_insider_trade(session, insider_trade, company_id: int, insider_id: int, accession_number: str):
    """Store insider trade and transactions in database."""

    # Check if filing already exists
    existing_filing = session.query(RawForm4Filing).filter_by(
        accession_number=accession_number
    ).first()

    if existing_filing:
        logger.debug(f"Filing already exists: {accession_number}")
        return 0

    # Create filing record
    filing = RawForm4Filing(
        filing_url=insider_trade.filing_url,
        accession_number=accession_number,
        filing_date=datetime.strptime(insider_trade.filing_date, '%Y-%m-%d'),
        xml_content="",  # Could store XML here if needed
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
    # Check if already exists
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


def main():
    """Main collection script."""
    print("=" * 80)
    print("PHASE 2: SAMPLE DATA COLLECTION")
    print("=" * 80)
    print()

    # Load config
    config_path = Path(__file__).parent.parent / 'config.yaml'
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Initialize database
    print("[1/5] Initializing database...")
    init_db()
    print("✅ Database initialized")

    # Initialize clients
    print("\n[2/5] Initializing API clients...")
    sec_config = config['data_sources']['sec_api']
    sec_client = SECEdgarClient(sec_config)
    parser = Form4Parser()
    market_cap_fetcher = MarketCapFetcher()
    print("✅ API clients ready")

    # Target tickers (tech + financials)
    tickers = ['AAPL', 'MSFT', 'TSLA', 'WMT', 'JPM', 'BAC', 'GS', 'C']
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)  # Extended for more filings

    print(f"\n[3/5] Collecting Form 4 filings...")
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Date range: {start_date.date()} to {end_date.date()}")

    session = get_session()
    total_filings = 0
    total_transactions = 0
    total_market_caps = 0

    try:
        for ticker in tickers:
            print(f"\n  Processing {ticker}...")

            # Get CIK
            cik = sec_client.get_company_cik(ticker)
            if not cik:
                print(f"    ❌ Could not find CIK for {ticker}")
                continue

            # Get filings
            filings = sec_client.get_form4_filings(cik, start_date, end_date)
            print(f"    Found {len(filings)} filings")

            if not filings:
                continue

            # Process each filing
            for filing in filings[:30]:  # Limit to 30 per ticker for better sample
                try:
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
                        total_filings += 1
                        total_transactions += tx_count

                        # Fetch market cap for filing date
                        filing_date = datetime.strptime(filing['filing_date'], '%Y-%m-%d')
                        market_cap = market_cap_fetcher.get_market_cap_at_date(ticker, filing_date)

                        if market_cap:
                            store_market_cap(session, company.id, filing_date, market_cap)
                            total_market_caps += 1

                except Exception as e:
                    logger.error(f"Error processing filing {filing['filing_url']}: {e}")
                    continue

            # Commit after each ticker
            session.commit()
            print(f"    ✅ Processed {ticker}")

        print(f"\n[4/5] Data collection complete!")
        print(f"  Total filings: {total_filings}")
        print(f"  Total transactions: {total_transactions}")
        print(f"  Market caps fetched: {total_market_caps}")

        # Verify database
        print(f"\n[5/5] Verifying database...")
        company_count = session.query(Company).count()
        insider_count = session.query(Insider).count()
        transaction_count = session.query(InsiderTransaction).count()
        market_cap_count = session.query(MarketCap).count()

        print(f"  Companies: {company_count}")
        print(f"  Insiders: {insider_count}")
        print(f"  Transactions: {transaction_count}")
        print(f"  Market caps: {market_cap_count}")

        print()
        print("=" * 80)
        print("✅ PHASE 2 COMPLETE")
        print("=" * 80)
        print()
        print(f"Database created at: ./data/insider_trades.db")
        print(f"Total transactions stored: {transaction_count}")

    except Exception as e:
        session.rollback()
        logger.error(f"Collection failed: {e}")
        raise

    finally:
        session.close()


if __name__ == '__main__':
    main()
