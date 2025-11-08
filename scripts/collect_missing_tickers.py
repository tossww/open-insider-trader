"""
Quick script to collect the 3 missing tickers: AMD, META, NVDA
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import logging
from datetime import datetime, timedelta
from collectors.sec_edgar import SECEdgarClient
from collectors.market_cap import MarketCapFetcher
from processors.form4_parser import Form4Parser
from database.connection import init_db, get_session
from database.schema import Company, Insider, RawForm4Filing, InsiderTransaction, MarketCap

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MISSING_TICKERS = ['AMD', 'META', 'NVDA']


def main():
    print("🎯 Collecting Missing Tickers: AMD, META, NVDA")
    print("="*60)

    # Initialize
    init_db()
    sec_config = {
        'base_url': 'https://www.sec.gov/cgi-bin/browse-edgar',
        'user_agent': 'Open InsiderTrader research tossww-studio@gmail.com',
        'rate_limit_per_second': 10
    }
    sec_client = SECEdgarClient(sec_config)
    market_cap_fetcher = MarketCapFetcher()
    parser = Form4Parser()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=5*365)

    print(f"📅 Date Range: {start_date.date()} to {end_date.date()}\n")

    for ticker in MISSING_TICKERS:
        print(f"\n{'='*60}")
        print(f"Processing {ticker}...")
        print(f"{'='*60}")

        # Get CIK
        cik = sec_client.get_company_cik(ticker)
        if not cik:
            print(f"❌ Could not find CIK for {ticker}")
            continue

        print(f"✓ Found CIK: {cik}")

        session = get_session()

        try:
            # Create/get company
            company = session.query(Company).filter_by(ticker=ticker).first()
            if not company:
                company = Company(ticker=ticker, name=ticker, cik=cik)
                session.add(company)
                session.flush()
                print(f"✓ Created company record")

            # Collect filings in yearly chunks
            all_filings = []
            current_start = start_date

            while current_start < end_date:
                current_end = min(current_start + timedelta(days=365), end_date)
                print(f"  Fetching {current_start.date()} to {current_end.date()}...", end='')

                filings = sec_client.get_form4_filings(cik, current_start, current_end)
                print(f" {len(filings)} filings")

                all_filings.extend(filings)
                current_start = current_end

            if not all_filings:
                print(f"ℹ️  No filings found for {ticker}")
                session.close()
                continue

            print(f"\n✓ Total filings to process: {len(all_filings)}")

            # Process filings
            filing_count = 0
            transaction_count = 0

            for i, filing_meta in enumerate(all_filings, 1):
                if i % 25 == 0:
                    print(f"  Progress: {i}/{len(all_filings)} filings...")

                # Check if already processed
                existing = session.query(RawForm4Filing).filter_by(
                    accession_number=filing_meta['accession_number']
                ).first()
                if existing:
                    continue

                # Get XML
                xml_content = sec_client.get_form4_xml(filing_meta['filing_url'])
                if not xml_content:
                    continue

                # Parse
                try:
                    insider_trades = parser.parse_form4(xml_content, filing_meta['filing_url'])
                except Exception as e:
                    logger.warning(f"Parse error: {e}")
                    continue

                # Store
                for trade in insider_trades:
                    # Get/create insider
                    insider = session.query(Insider).filter_by(
                        name=trade.owner_info.name,
                        cik=trade.owner_info.cik,
                        company_id=company.id
                    ).first()

                    if not insider:
                        insider = Insider(
                            name=trade.owner_info.name,
                            cik=trade.owner_info.cik,
                            company_id=company.id,
                            is_director=trade.owner_info.is_director,
                            is_officer=trade.owner_info.is_officer,
                            is_ten_percent_owner=trade.owner_info.is_ten_percent_owner,
                            officer_title=trade.owner_info.officer_title
                        )
                        session.add(insider)
                        session.flush()

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

                        # Market cap
                        if txn.transaction_date:
                            try:
                                mc = market_cap_fetcher.get_market_cap(ticker, txn.transaction_date)
                                if mc:
                                    mc_rec = MarketCap(
                                        company_id=company.id,
                                        date=txn.transaction_date,
                                        market_cap_usd=mc
                                    )
                                    session.add(mc_rec)
                            except:
                                pass

                    filing_count += 1

            session.commit()
            print(f"\n✅ {ticker}: {filing_count} filings, {transaction_count} transactions stored")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            session.rollback()
        finally:
            session.close()

    print("\n" + "="*60)
    print("✅ COLLECTION COMPLETE")
    print("="*60)


if __name__ == '__main__':
    main()
