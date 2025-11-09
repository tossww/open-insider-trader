#!/usr/bin/env python3
"""
Initialize database and scrape initial data.

Usage:
    python scripts/initialize_db.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import init_db, get_session
from src.collectors.openinsider import OpenInsiderScraper
from src.signals.signal_generator import SignalGenerator


def main():
    """Initialize database and load initial data."""

    print("🚀 Initializing Open Insider Trader Database\n")
    print("=" * 60)

    # Step 1: Create database tables
    print("\n📦 Step 1: Creating database schema...")
    try:
        init_db()
        print("✅ Database tables created")
    except Exception as e:
        print(f"❌ Failed to create database: {e}")
        return False

    # Step 2: Scrape initial data
    print("\n🌐 Step 2: Scraping OpenInsider.com...")
    try:
        scraper = OpenInsiderScraper()
        session = get_session()
        df = scraper.fetch_latest_purchases(days_back=30, min_value=50000)
        saved = scraper.save_to_database(df, session)
        session.close()
        print(f"✅ Scraped and saved {saved} transactions")
    except Exception as e:
        print(f"❌ Failed to scrape data: {e}")
        return False

    # Step 3: Generate signals
    print("\n🎯 Step 3: Generating signals...")
    try:
        session = get_session()
        signals = SignalGenerator.generate_signals(session, min_value=50_000)
        print(f"✅ Generated {len(signals)} signals")

        # Show distribution
        strong = sum(1 for s in signals if s.total_score >= 7)
        watch = sum(1 for s in signals if 5 <= s.total_score < 7)
        weak = sum(1 for s in signals if 3 <= s.total_score < 5)

        print(f"\n📊 Signal Distribution:")
        print(f"  Strong Buy (≥7): {strong}")
        print(f"  Watch (5-6):     {watch}")
        print(f"  Weak (3-4):      {weak}")

        session.close()
    except Exception as e:
        print(f"❌ Failed to generate signals: {e}")
        return False

    print("\n" + "=" * 60)
    print("✅ Initialization complete!")
    print("\nNext steps:")
    print("  1. Start API server: python scripts/run_api.py")
    print("  2. Start frontend:   cd frontend && npm run dev")
    print("  3. Visit: http://localhost:3000")

    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
