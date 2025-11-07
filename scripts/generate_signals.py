#!/usr/bin/env python
"""
Generate Signals CLI

Command-line interface for generating insider trading signals.

Usage:
    python scripts/generate_signals.py [OPTIONS]

Options:
    --min-score FLOAT    Minimum composite score (default: from config)
    --top-n INT          Show only top N signals (default: 50)
    --store-db           Store signals in database (default: False)
    --actionable-only    Show only actionable signals (default: False)
    --config PATH        Path to config file (default: config.yaml)
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.pipeline.signal_generator import SignalGenerator
from src.database.connection import get_session
from src.database.schema import FilteredSignal


def format_currency(value: float) -> str:
    """Format currency with K/M/B suffixes."""
    if value >= 1_000_000_000:
        return f"${value/1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    elif value >= 1_000:
        return f"${value/1_000:.1f}K"
    else:
        return f"${value:.2f}"


def print_report(report, top_n: int = 50):
    """Pretty-print signal report."""
    print("\n" + "=" * 80)
    print("INSIDER TRADING SIGNAL REPORT")
    print("=" * 80)
    print(f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Config: {report.config_path}")
    print()

    # Filter statistics
    print("FILTERING PIPELINE:")
    print("-" * 80)
    fs = report.filter_stats
    print(f"  Total transactions:        {fs['total_input']:>6}")
    print(f"  Purchases only (P):        {fs['stage_1_purchases']:>6}")
    print(f"  >= $100K trades:           {fs['stage_2_min_value']:>6}")
    print(f"  Executive weight > 0:      {fs['stage_3_executive']:>6}")
    print(f"  Market cap % filter:       {fs['stage_4_market_cap_pct']:>6}")
    print(f"  Final filtered signals:    {fs['final_filtered']:>6}")
    print()

    # Cluster statistics
    print("CLUSTERING:")
    print("-" * 80)
    cs = report.cluster_stats
    print(f"  Total clusters:            {cs['total_clusters']:>6}")
    print(f"  Average cluster size:      {cs['avg_cluster_size']:>6.2f}")
    print(f"  Max cluster size:          {cs['max_cluster_size']:>6}")
    print(f"  Solo transactions:         {cs['solo_transactions']:>6}")
    print(f"  Clustered transactions:    {cs['clustered_transactions']:>6}")
    print()

    # Score statistics
    print("SCORING:")
    print("-" * 80)
    ss = report.score_stats
    print(f"  Total signals:             {ss['total_signals']:>6}")
    print(f"  Actionable (>=2.0):        {ss['actionable_signals']:>6}")
    print(f"  Average score:             {ss['avg_score']:>6.2f}")
    print(f"  Score range:               {ss['min_score']:>6.2f} - {ss['max_score']:.2f}")
    print()

    # Top signals
    signals_to_show = report.signals[:top_n]
    if signals_to_show:
        print(f"TOP {len(signals_to_show)} SIGNALS (by composite score):")
        print("=" * 80)

        for i, signal in enumerate(signals_to_show, 1):
            actionable = "✓" if signal['is_actionable'] else " "
            cluster_info = f"Cluster: {signal['cluster_size']}" if signal.get('cluster_size', 1) > 1 else "Solo"

            # Header line
            print(f"\n{i:2}. [{actionable}] {signal['ticker']:5} | Score: {signal['composite_score']:.2f} | {cluster_info}")

            # Insider info
            print(f"    {signal['insider_name']:30} ({signal['officer_title'] or 'N/A'})")

            # Trade details
            trade_value = format_currency(signal['total_value'])
            market_cap = format_currency(signal['market_cap_usd']) if signal['market_cap_usd'] else 'N/A'
            trade_pct = f"{signal['trade_pct_of_market_cap']*100:.6f}%" if signal['trade_pct_of_market_cap'] else 'N/A'

            print(f"    Trade: {trade_value:>10} | Market Cap: {market_cap:>10} | Trade %: {trade_pct:>12}")

            # Filing dates
            filing_date = signal['filing_date']
            if isinstance(filing_date, str):
                filing_date = filing_date[:10]  # Just date part
            else:
                filing_date = filing_date.strftime('%Y-%m-%d')

            print(f"    Filed: {filing_date}")

            # Weights breakdown
            print(f"    Weights: Exec={signal['executive_weight']:.1f} × "
                  f"Dollar={signal['dollar_weight']:.2f} × "
                  f"Cluster={signal['cluster_weight']:.1f} × "
                  f"MarketCap={signal['market_cap_weight']:.2f}")

        print("\n" + "=" * 80)
    else:
        print("No signals found matching criteria.")
        print("=" * 80)


def store_signals_in_db(report):
    """Store signals in database."""
    session = get_session()

    try:
        # Clear existing filtered signals (optional - could keep historical)
        session.query(FilteredSignal).delete()

        # Insert new signals
        for signal in report.signals:
            fs = FilteredSignal(
                transaction_id=signal['id'],
                executive_weight=signal['executive_weight'],
                dollar_weight=signal['dollar_weight'],
                cluster_weight=signal['cluster_weight'],
                market_cap_weight=signal['market_cap_weight'],
                composite_score=signal['composite_score'],
                cluster_id=signal.get('cluster_id'),
                cluster_size=signal.get('cluster_size', 1),
                is_actionable=signal['is_actionable']
            )
            session.add(fs)

        session.commit()
        print(f"\n✓ Stored {len(report.signals)} signals in database")

    except Exception as e:
        session.rollback()
        print(f"\n✗ Error storing signals: {e}")
        raise
    finally:
        session.close()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Generate insider trading signals',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate all signals
  python scripts/generate_signals.py

  # Show only top 10
  python scripts/generate_signals.py --top-n 10

  # Filter by minimum score
  python scripts/generate_signals.py --min-score 3.0

  # Store in database
  python scripts/generate_signals.py --store-db

  # Show only actionable signals
  python scripts/generate_signals.py --actionable-only
        """
    )

    parser.add_argument('--min-score', type=float, default=None,
                        help='Minimum composite score (default: from config)')
    parser.add_argument('--top-n', type=int, default=50,
                        help='Show only top N signals (default: 50)')
    parser.add_argument('--store-db', action='store_true',
                        help='Store signals in database (default: False)')
    parser.add_argument('--actionable-only', action='store_true',
                        help='Show only actionable signals (default: False)')
    parser.add_argument('--config', type=str, default='config.yaml',
                        help='Path to config file (default: config.yaml)')

    args = parser.parse_args()

    # Generate signals
    print("Generating signals...")
    generator = SignalGenerator(config_path=args.config)
    report = generator.generate_and_filter(
        min_score=args.min_score,
        top_n=args.top_n if not args.actionable_only else None,  # Apply top_n after actionable filter
        actionable_only=args.actionable_only
    )

    # Print report
    print_report(report, top_n=args.top_n)

    # Store in database if requested
    if args.store_db:
        store_signals_in_db(report)


if __name__ == '__main__':
    main()
