"""
Alert processor - sends email alerts for strong buy signals.
"""

import os
from typing import List
from datetime import datetime

from ..database.connection import get_session
from ..database.schema import Signal, ThresholdCategory
from ..email import EmailSender, render_alert_email
from ..signals import SignalGenerator


def process_alerts(
    subscribers: List[str] = None,
    base_url: str = None,
    dry_run: bool = False
) -> dict:
    """
    Process pending alerts and send emails.

    Args:
        subscribers: List of subscriber emails (if None, uses SUBSCRIBER_EMAILS env var)
        base_url: Base URL for deep dive links (defaults to localhost)
        dry_run: If True, don't actually send emails or mark as sent

    Returns:
        dict: Processing results
    """
    session = get_session()

    try:
        # Get unsent strong buy signals
        strong_signals = SignalGenerator.get_strong_signals(session, unsent_only=True)

        if not strong_signals:
            print("✅ No pending alerts to send")
            return {
                "status": "success",
                "signals_processed": 0,
                "emails_sent": 0
            }

        print(f"📬 Found {len(strong_signals)} pending alert(s)")

        # Get subscribers
        if subscribers is None:
            env_subscribers = os.getenv('SUBSCRIBER_EMAILS', '')
            subscribers = [e.strip() for e in env_subscribers.split(',') if e.strip()]

        if not subscribers:
            print("⚠️  No subscribers configured. Set SUBSCRIBER_EMAILS environment variable.")
            return {
                "status": "no_subscribers",
                "signals_processed": 0,
                "emails_sent": 0
            }

        # Get base URL
        if base_url is None:
            base_url = os.getenv('BASE_URL', 'http://localhost:3000')

        # Initialize email sender (skip if dry run)
        if not dry_run:
            try:
                sender = EmailSender()
            except ValueError as e:
                print(f"❌ Email sender initialization failed: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "signals_processed": 0,
                    "emails_sent": 0
                }

        # Process each signal
        emails_sent = 0
        for signal in strong_signals:
            txn = signal.transaction
            company = txn.company
            insider = txn.insider

            # Build conviction reasons
            conviction_reasons = []
            if txn.total_value and txn.total_value > 1_000_000:
                conviction_reasons.append(f"${txn.total_value/1_000_000:.1f}M purchase (high conviction)")

            from ..signals.conviction_scorer import ConvictionScorer
            if ConvictionScorer._has_clustered_buys(txn, session):
                conviction_reasons.append("Multiple buys within 30 days (strong signal)")

            if ConvictionScorer._is_c_suite(insider):
                conviction_reasons.append(f"C-Suite executive ({insider.title})")

            # Build track record reasons
            track_record_reasons = []
            perf = insider.performance

            if perf and perf.win_rate_3m:
                track_record_reasons.append(f"{perf.win_rate_3m:.0%} win rate over 3 months")
            if perf and perf.alpha_vs_spy:
                track_record_reasons.append(f"{perf.alpha_vs_spy:+.1%} alpha vs SPY")

            if not track_record_reasons:
                track_record_reasons.append("No historical data yet (new insider)")

            # Render email
            deep_dive_url = f"{base_url}/company/{company.ticker}"

            html_content, plain_content = render_alert_email(
                ticker=company.ticker,
                company_name=company.name,
                insider_name=insider.name,
                insider_title=insider.title,
                trade_value=txn.total_value or 0,
                trade_date=txn.trade_date,
                signal_score=signal.total_score,
                conviction_score=signal.conviction_score,
                track_record_score=signal.track_record_score,
                conviction_reasons=conviction_reasons,
                track_record_reasons=track_record_reasons,
                deep_dive_url=deep_dive_url
            )

            subject = f"[STRONG BUY] ${company.ticker} - High-Conviction Insider Purchase"

            # Send to all subscribers
            if dry_run:
                print(f"[DRY RUN] Would send alert for ${company.ticker} to {len(subscribers)} subscriber(s)")
                print(f"  Subject: {subject}")
                print(f"  Conviction: {signal.conviction_score}/3, Track Record: {signal.track_record_score}/5")
            else:
                results = sender.send_batch_alerts(subscribers, subject, html_content, plain_content)
                success_count = sum(1 for sent in results.values() if sent)

                if success_count > 0:
                    # Mark signal as sent
                    SignalGenerator.mark_alert_sent(signal, session)
                    emails_sent += success_count
                    print(f"✅ Sent alert for ${company.ticker} to {success_count}/{len(subscribers)} subscriber(s)")
                else:
                    print(f"❌ Failed to send alert for ${company.ticker}")

        return {
            "status": "success",
            "signals_processed": len(strong_signals),
            "emails_sent": emails_sent,
            "dry_run": dry_run
        }

    finally:
        session.close()
