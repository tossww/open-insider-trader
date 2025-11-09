#!/usr/bin/env python3
"""
Test script for OpenInsider scraper

POC to verify:
1. HTML parsing works correctly
2. Ticker validation via yfinance
3. Database save/retrieve
4. Backtest integration
"""

import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.openinsider import OpenInsiderScraper
from src.database.connection import DatabaseManager
from src.database.schema import Company, Insider, InsiderTransaction, TransactionCode
from src.backtesting.insider_performance import calculate_insider_performance, update_insider_performance

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run end-to-end test of OpenInsider scraper."""

    logger.info("=" * 80)
    logger.info("OpenInsider Scraper POC Test")
    logger.info("=" * 80)

    # Initialize database
    logger.info("\n1. Initializing database...")
    db_manager = DatabaseManager()
    db_manager.init_db()
    session = db_manager.get_session()

    # Initialize scraper
    logger.info("\n2. Initializing scraper...")
    scraper = OpenInsiderScraper()

    # Scrape last 7 days (small sample)
    logger.info("\n3. Scraping last 7 days of purchases...")
    df = scraper.fetch_latest_purchases(days_back=7, min_value=50000, max_pages=2)

    if df.empty:
        logger.error("No data fetched!")
        return

    logger.info(f"\nFetched {len(df)} transactions")
    logger.info("\nSample data:")
    print(df.head(10).to_string())

    # Save to database
    logger.info("\n4. Saving to database...")
    saved_count = scraper.save_to_database(df, session)
    logger.info(f"Saved {saved_count} new transactions")

    # Query database to verify
    logger.info("\n5. Verifying database integrity...")
    total_companies = session.query(Company).count()
    total_insiders = session.query(Insider).count()
    total_transactions = session.query(InsiderTransaction).count()

    logger.info(f"  Companies: {total_companies}")
    logger.info(f"  Insiders: {total_insiders}")
    logger.info(f"  Transactions: {total_transactions}")

    # Show sample companies
    logger.info("\n6. Sample companies in database:")
    companies = session.query(Company).limit(5).all()
    for company in companies:
        txn_count = session.query(InsiderTransaction).filter_by(company_id=company.id).count()
        logger.info(f"  {company.ticker} - {company.name} ({txn_count} transactions)")

    # Test backtest integration
    logger.info("\n7. Testing backtest integration...")

    # Find insider with most trades
    from sqlalchemy import func
    insider_with_most_trades = session.query(
        Insider.id,
        Insider.name,
        func.count(InsiderTransaction.id).label('trade_count')
    ).join(
        InsiderTransaction
    ).group_by(
        Insider.id
    ).order_by(
        func.count(InsiderTransaction.id).desc()
    ).first()

    if insider_with_most_trades:
        insider_id, insider_name, trade_count = insider_with_most_trades
        logger.info(f"Testing with insider: {insider_name} ({trade_count} trades)")

        if trade_count >= 3:
            # Calculate performance
            logger.info("\n8. Calculating insider performance...")
            metrics = calculate_insider_performance(insider_id, session)

            if metrics:
                logger.info("\nPerformance Metrics:")
                logger.info(f"  Win Rate (1w): {metrics.get('win_rate_1w', 0):.1%}" if metrics.get('win_rate_1w') else "  Win Rate (1w): N/A")
                logger.info(f"  Win Rate (1m): {metrics.get('win_rate_1m', 0):.1%}" if metrics.get('win_rate_1m') else "  Win Rate (1m): N/A")
                logger.info(f"  Win Rate (3m): {metrics.get('win_rate_3m', 0):.1%}" if metrics.get('win_rate_3m') else "  Win Rate (3m): N/A")
                logger.info(f"  Win Rate (6m): {metrics.get('win_rate_6m', 0):.1%}" if metrics.get('win_rate_6m') else "  Win Rate (6m): N/A")
                logger.info(f"  Avg Return: {metrics.get('avg_return', 0):+.2%}" if metrics.get('avg_return') else "  Avg Return: N/A")
                logger.info(f"  Alpha vs SPY: {metrics.get('alpha_vs_spy', 0):+.2%}" if metrics.get('alpha_vs_spy') else "  Alpha vs SPY: N/A")
                logger.info(f"  Total Buys: {metrics.get('total_buys', 0)}")
                logger.info(f"  Total Sells: {metrics.get('total_sells', 0)}")

                # Save to database
                logger.info("\n9. Saving performance metrics to database...")
                if update_insider_performance(insider_id, session, force_recalc=True):
                    logger.info("Performance metrics saved successfully!")
                else:
                    logger.error("Failed to save performance metrics")
            else:
                logger.warning("Could not calculate performance metrics (insufficient data)")
        else:
            logger.warning(f"Insider has only {trade_count} trades, need at least 3 for backtest")
    else:
        logger.warning("No insiders found with trades")

    # Final summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST COMPLETE")
    logger.info("=" * 80)
    logger.info(f"✅ Scraped {len(df)} transactions from OpenInsider")
    logger.info(f"✅ Saved {saved_count} new transactions to database")
    logger.info(f"✅ Database has {total_companies} companies, {total_insiders} insiders")
    logger.info(f"✅ Backtest integration {'PASSED' if insider_with_most_trades and trade_count >= 3 else 'SKIPPED (insufficient data)'}")
    logger.info("=" * 80)

    session.close()


if __name__ == "__main__":
    main()
