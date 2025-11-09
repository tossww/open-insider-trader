#!/usr/bin/env python3
"""
Test script for signal scoring system.

Tests conviction scoring, track record scoring, and signal generation.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.schema import Base, TransactionCode
from src.signals import SignalGenerator, ConvictionScorer, TrackRecordScorer


def test_signal_scoring():
    """Test signal scoring on existing database."""

    # Connect to database
    db_path = Path(__file__).parent.parent / 'data' / 'insider_trades.db'
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False

    engine = create_engine(f'sqlite:///{db_path}')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("🚀 Testing Signal Scoring System\n")
    print("=" * 60)

    # Test 1: Generate signals for all transactions
    print("\n📊 Test 1: Generating signals...")
    try:
        signals = SignalGenerator.generate_signals(
            session=session,
            min_value=50_000,  # $50K minimum
            holding_period='3m'
        )
        print(f"✅ Generated {len(signals)} signals")

        # Show score distribution
        score_dist = {}
        category_dist = {}
        for sig in signals:
            score_dist[sig.total_score] = score_dist.get(sig.total_score, 0) + 1
            cat = sig.threshold_category.value
            category_dist[cat] = category_dist.get(cat, 0) + 1

        print("\n📈 Score Distribution:")
        for score in sorted(score_dist.keys()):
            count = score_dist[score]
            bar = '█' * (count // 2)
            print(f"  Score {score}: {count:3d} {bar}")

        print("\n🎯 Category Distribution:")
        for cat, count in sorted(category_dist.items()):
            print(f"  {cat:12s}: {count:3d}")

    except Exception as e:
        print(f"❌ Signal generation failed: {e}")
        return False

    # Test 2: Get strong buy signals
    print("\n" + "=" * 60)
    print("\n🔥 Test 2: Strong Buy Signals (Score ≥7)")
    strong_signals = SignalGenerator.get_strong_signals(session, unsent_only=False)

    if strong_signals:
        print(f"✅ Found {len(strong_signals)} STRONG BUY signals\n")

        # Show top 5
        for i, sig in enumerate(strong_signals[:5], 1):
            txn = sig.transaction
            company = txn.company
            insider = txn.insider

            print(f"{i}. ${company.ticker} - {company.name}")
            print(f"   Insider: {insider.name} ({insider.title or 'N/A'})")
            print(f"   Trade: ${txn.total_value:,.0f} on {txn.trade_date.date()}")
            print(f"   Score: {sig.total_score} (Conviction: {sig.conviction_score}, Track Record: {sig.track_record_score})")
            print()
    else:
        print("⚠️  No STRONG BUY signals found")

    # Test 3: Conviction scoring breakdown
    print("=" * 60)
    print("\n🎯 Test 3: Conviction Scoring Examples")

    # Get a few high-conviction transactions
    from src.database.schema import InsiderTransaction

    high_value_txns = session.query(InsiderTransaction).filter(
        InsiderTransaction.transaction_code == TransactionCode.P,
        InsiderTransaction.total_value > 1_000_000
    ).limit(3).all()

    for txn in high_value_txns:
        conviction = ConvictionScorer.score_transaction(txn, session)
        print(f"\n${txn.company.ticker} - {txn.insider.name}")
        print(f"  Value: ${txn.total_value:,.0f}")
        print(f"  Title: {txn.insider.title or 'N/A'}")
        print(f"  C-Suite: {ConvictionScorer._is_c_suite(txn.insider)}")
        print(f"  Clustered: {ConvictionScorer._has_clustered_buys(txn, session)}")
        print(f"  → Conviction Score: {conviction}/3")

    # Test 4: Track record scoring
    print("\n" + "=" * 60)
    print("\n📊 Test 4: Track Record Scoring Examples")

    from src.database.schema import InsiderPerformance

    # Get insiders with performance data
    top_performers = session.query(InsiderPerformance).filter(
        InsiderPerformance.win_rate_3m.isnot(None),
        InsiderPerformance.alpha_vs_spy.isnot(None)
    ).order_by(InsiderPerformance.win_rate_3m.desc()).limit(3).all()

    for perf in top_performers:
        insider = perf.insider
        # Find a recent transaction from this insider
        txn = session.query(InsiderTransaction).filter(
            InsiderTransaction.insider_id == insider.id,
            InsiderTransaction.transaction_code == TransactionCode.P
        ).first()

        if txn:
            track_score = TrackRecordScorer.score_transaction(txn, session, '3m')
            print(f"\n{insider.name} at ${txn.company.ticker}")
            print(f"  Win Rate (3m): {perf.win_rate_3m:.1%}")
            print(f"  Alpha vs SPY: {perf.alpha_vs_spy:+.2%}")
            print(f"  → Track Record Score: {track_score}/5")

    print("\n" + "=" * 60)
    print("\n✅ All tests completed!")

    session.close()
    return True


if __name__ == '__main__':
    success = test_signal_scoring()
    sys.exit(0 if success else 1)
