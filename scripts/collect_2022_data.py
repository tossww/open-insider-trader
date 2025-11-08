"""
Targeted 2022 Data Collection

Focus on filling the 2022 gap with monthly chunks to ensure comprehensive coverage.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import logging
import time
from datetime import datetime, timedelta
from typing import Dict
from collectors.sec_edgar import SECEdgarClient
from collectors.market_cap import MarketCapFetcher
from processors.form4_parser import Form4Parser
from database.connection import init_db, get_session
from database.schema import Company, Insider, RawForm4Filing, InsiderTransaction, MarketCap

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

ALL_TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'META', 'NVDA', 'AMD', 'INTC', 'TSLA', 'ORCL', 'CRM', 'ADBE', 'CSCO',
    'JPM', 'BAC', 'WFC', 'C', 'GS', 'MS', 'BLK', 'SCHW', 'AXP',
    'JNJ', 'UNH', 'PFE', 'ABBV', 'TMO', 'ABT', 'MRK', 'LLY',
    'AMZN', 'WMT', 'HD', 'NKE', 'MCD', 'SBUX', 'TGT', 'COST',
    'BA', 'CAT', 'GE', 'HON', 'UPS', 'LMT', 'MMM',
    'XOM', 'CVX', 'COP', 'SLB', 'EOG',
    'T', 'VZ', 'TMUS',
    'LIN', 'APD', 'ECL', 'DD'
]


def collect_ticker_2022(ticker: str, sec_client, market_cap_fetcher, parser) -> Dict:
    """Collect 2022 data for a single ticker using monthly chunks."""

    logger.info(f"\n{'='*60}\n{ticker}\n{'='*60}")

    cik = sec_client.get_company_cik(ticker)
    if not cik:
        return {'ticker': ticker, 'error': 'No CIK'}

    session = get_session()

    try:
        company = session.query(Company).filter_by(ticker=ticker).first()
        if not company:
            company = Company(ticker=ticker, name=ticker, cik=cik)
            session.add(company)
            session.flush()

        # Collect 2022 in MONTHLY chunks
        all_filings = []
        start = datetime(2022, 1, 1)

        for month in range(1, 13):
            month_start = datetime(2022, month, 1)
            if month == 12:
                month_end = datetime(2023, 1, 1)
            else:
                month_end = datetime(2022, month + 1, 1)

            filings = sec_client.get_form4_filings(cik, month_start, month_end)
            if filings:
                logger.info(f"  {month_start.strftime('%Y-%m')}: {len(filings)} filings")
                all_filings.extend(filings)

        if not all_filings:
            logger.info(f"  No 2022 filings")
            session.close()
            return {'ticker': ticker, 'filings': 0, 'transactions': 0}

        logger.info(f"  Total: {len(all_filings)} filings")

        # Process filings
        new_filings = 0
        new_transactions = 0

        for filing_meta in all_filings:
            # Check if already processed
            if session.query(RawForm4Filing).filter_by(
                accession_number=filing_meta['accession_number']
            ).first():
                continue

            # Fetch and parse
            xml_content = sec_client.get_form4_xml(filing_meta['filing_url'])
            if not xml_content:
                continue

            try:
                insider_trade = parser.parse_form4_xml(
                    xml_content,
                    filing_meta['filing_url'],
                    filing_meta['filing_date']
                )
                if not insider_trade or not insider_trade.transactions:
                    continue
            except Exception as e:
                logger.warning(f"  Parse error: {e}")
                continue

            # Store
            try:
                # Get/create insider
                insider = session.query(Insider).filter_by(
                    name=insider_trade.owner_info.name,
                    cik=insider_trade.owner_info.cik,
                    company_id=company.id
                ).first()

                if not insider:
                    insider = Insider(
                        name=insider_trade.owner_info.name,
                        cik=insider_trade.owner_info.cik,
                        company_id=company.id,
                        is_director=insider_trade.owner_info.is_director,
                        is_officer=insider_trade.owner_info.is_officer,
                        is_ten_percent_owner=insider_trade.owner_info.is_ten_percent_owner,
                        officer_title=insider_trade.owner_info.officer_title
                    )
                    session.add(insider)
                    session.flush()

                filing_date_obj = datetime.strptime(filing_meta['filing_date'], '%Y-%m-%d')

                # Store filing
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
                    trade_date_obj = None
                    if txn.transaction_date:
                        try:
                            trade_date_obj = datetime.strptime(txn.transaction_date, '%Y-%m-%d')
                        except:
                            pass

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
                    new_transactions += 1

                new_filings += 1

            except Exception as e:
                logger.error(f"  Store error: {e}")
                session.rollback()
                continue

        session.commit()
        logger.info(f"  ✅ {ticker}: +{new_filings} filings, +{new_transactions} transactions")

        return {'ticker': ticker, 'filings': new_filings, 'transactions': new_transactions}

    except Exception as e:
        logger.error(f"  ❌ Fatal error: {e}")
        session.rollback()
        return {'ticker': ticker, 'error': str(e)}
    finally:
        session.close()


def main():
    print("\n" + "="*80)
    print("🎯 TARGETED 2022 DATA COLLECTION")
    print("="*80)

    init_db()

    sec_config = {
        'base_url': 'https://www.sec.gov/cgi-bin/browse-edgar',
        'user_agent': 'Open InsiderTrader research tossww-studio@gmail.com',
        'rate_limit_per_second': 10
    }
    sec_client = SECEdgarClient(sec_config)
    market_cap_fetcher = MarketCapFetcher()
    parser = Form4Parser()

    print(f"\n📅 Target: All of 2022 (monthly chunks)")
    print(f"📊 Tickers: {len(ALL_TICKERS)}\n")

    results = []
    start_time = time.time()

    for i, ticker in enumerate(ALL_TICKERS, 1):
        print(f"[{i}/{len(ALL_TICKERS)}]", end=' ')
        result = collect_ticker_2022(ticker, sec_client, market_cap_fetcher, parser)
        results.append(result)

    elapsed = time.time() - start_time
    total_filings = sum(r.get('filings', 0) for r in results)
    total_transactions = sum(r.get('transactions', 0) for r in results)

    print("\n" + "="*80)
    print("✅ 2022 COLLECTION COMPLETE")
    print("="*80)
    print(f"⏱️  Time: {elapsed/60:.1f} minutes")
    print(f"📄 New filings: {total_filings:,}")
    print(f"💼 New transactions: {total_transactions:,}")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
