"""
APScheduler-based job scheduler.

Runs:
- Data scraping (every 6 hours)
- Signal generation (after scraping)
- Alert processing (every hour)
- Performance recalculation (weekly)
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

from ..collectors.openinsider import OpenInsiderCollector
from ..signals import SignalGenerator
from ..database.connection import get_session
from .alert_processor import process_alerts


_scheduler = None


def scrape_and_score_job():
    """Job: Scrape OpenInsider and generate signals."""
    print(f"\n🔄 [{datetime.now().strftime('%Y-%m-%d %H:%M')}] Running scrape + score job...")

    try:
        # 1. Scrape new transactions
        collector = OpenInsiderCollector()
        transactions = collector.collect()
        print(f"✅ Scraped {len(transactions)} transactions")

        # 2. Generate signals for new transactions
        session = get_session()
        try:
            signals = SignalGenerator.generate_signals(session, min_value=50_000)
            print(f"✅ Generated {len(signals)} signals")

            # Show strong buys
            strong = [s for s in signals if s.total_score >= 7]
            if strong:
                print(f"🔥 {len(strong)} STRONG BUY signal(s) detected!")
        finally:
            session.close()

    except Exception as e:
        print(f"❌ Scrape + score job failed: {e}")


def alert_processing_job():
    """Job: Process pending alerts."""
    print(f"\n📬 [{datetime.now().strftime('%Y-%m-%d %H:%M')}] Processing alerts...")

    try:
        result = process_alerts()
        if result['status'] == 'success' and result['emails_sent'] > 0:
            print(f"✅ Sent {result['emails_sent']} alert(s)")
    except Exception as e:
        print(f"❌ Alert processing failed: {e}")


def performance_calc_job():
    """Job: Recalculate insider performance metrics."""
    print(f"\n📊 [{datetime.now().strftime('%Y-%m-%d %H:%M')}] Recalculating performance...")

    try:
        from ..backtesting.insider_performance import calculate_all_insider_performance
        session = get_session()
        try:
            updated = calculate_all_insider_performance(session)
            print(f"✅ Updated performance for {updated} insiders")
        finally:
            session.close()
    except Exception as e:
        print(f"❌ Performance calculation failed: {e}")


def start_scheduler():
    """Start the background scheduler."""
    global _scheduler

    if _scheduler is not None:
        print("⚠️  Scheduler already running")
        return

    _scheduler = BackgroundScheduler()

    # Job 1: Scrape + score every 6 hours (or use cron for daily after market close)
    _scheduler.add_job(
        scrape_and_score_job,
        trigger=IntervalTrigger(hours=6),
        id='scrape_and_score',
        name='Scrape OpenInsider and generate signals',
        replace_existing=True
    )

    # Job 2: Process alerts every hour
    _scheduler.add_job(
        alert_processing_job,
        trigger=IntervalTrigger(hours=1),
        id='process_alerts',
        name='Process pending email alerts',
        replace_existing=True
    )

    # Job 3: Recalculate performance weekly (Sundays at 2 AM)
    _scheduler.add_job(
        performance_calc_job,
        trigger=CronTrigger(day_of_week='sun', hour=2, minute=0),
        id='performance_calc',
        name='Recalculate insider performance',
        replace_existing=True
    )

    _scheduler.start()
    print("✅ Scheduler started")
    print("  - Scraping: Every 6 hours")
    print("  - Alerts: Every hour")
    print("  - Performance: Weekly (Sun 2 AM)")


def stop_scheduler():
    """Stop the scheduler."""
    global _scheduler

    if _scheduler is not None:
        _scheduler.shutdown()
        _scheduler = None
        print("✅ Scheduler stopped")
