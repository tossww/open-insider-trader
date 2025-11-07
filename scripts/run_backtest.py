#!/usr/bin/env python3
"""
Run backtest on filtered signals.

Validates insider trading strategy using historical price data.
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
import sqlite3
import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from backtesting.backtest_engine import BacktestEngine, Signal
from backtesting.metrics import MetricsCalculator


def load_signals_from_db(
    db_path: str = 'data/insider_trades.db',
    min_score: float = 2.0,
    limit: int = 100
) -> list[Signal]:
    """
    Load filtered signals from database.

    Args:
        db_path: Path to SQLite database
        min_score: Minimum composite score
        limit: Maximum number of signals

    Returns:
        List of Signal objects
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    query = """
    SELECT
        c.ticker,
        t.filing_date,
        t.trade_date,
        i.name as insider_name,
        i.officer_title,
        t.total_value,
        fs.composite_score,
        fs.cluster_size
    FROM filtered_signals fs
    JOIN insider_transactions t ON fs.transaction_id = t.id
    JOIN companies c ON t.company_id = c.id
    JOIN insiders i ON t.insider_id = i.id
    WHERE fs.composite_score >= ?
    ORDER BY fs.composite_score DESC
    LIMIT ?
    """

    cursor = conn.execute(query, (min_score, limit))
    rows = cursor.fetchall()
    conn.close()

    signals = []
    for row in rows:
        signals.append(Signal(
            ticker=row['ticker'],
            filing_date=datetime.fromisoformat(row['filing_date']),
            trade_date=datetime.fromisoformat(row['trade_date']),
            insider_name=row['insider_name'],
            officer_title=row['officer_title'] or 'Unknown',
            total_value=row['total_value'],
            composite_score=row['composite_score'],
            cluster_size=row['cluster_size']
        ))

    return signals


def load_config(config_path: str = 'config.yaml') -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def format_results_table(results: dict) -> str:
    """Format backtest results as a nice table."""
    lines = []
    lines.append("\n" + "="*80)
    lines.append("BACKTEST RESULTS SUMMARY")
    lines.append("="*80)

    # Header
    header = f"{'Period':<10} {'Trades':<8} {'Win%':<8} {'Avg Net':<12} {'Total Net':<12} {'Max DD':<10} {'Sharpe':<8}"
    lines.append(header)
    lines.append("-"*80)

    # Sort by holding period
    sorted_periods = sorted(results.keys(), key=lambda x: x if x != -1 else 999999)

    for period in sorted_periods:
        result = results[period]
        period_label = f"{period}d" if period != -1 else "max"

        if result.total_trades == 0:
            continue

        # Calculate metrics
        returns = [t.net_return for t in result.trades]
        calculator = MetricsCalculator()
        metrics = calculator.calculate_metrics(returns, period)

        row = (
            f"{period_label:<10} "
            f"{result.total_trades:<8} "
            f"{result.win_rate*100:<7.1f}% "
            f"{result.avg_net_return*100:<11.2f}% "
            f"{result.total_net_return*100:<11.2f}% "
            f"{metrics.max_drawdown*100:<9.2f}% "
            f"{metrics.sharpe_ratio:<8.2f}"
        )
        lines.append(row)

    lines.append("="*80)
    return "\n".join(lines)


def print_detailed_results(period: int, result, config: dict):
    """Print detailed results for a specific holding period."""
    print(f"\n{'='*80}")
    print(f"DETAILED RESULTS: {period}d holding period" if period != -1 else "DETAILED RESULTS: Max holding period")
    print(f"{'='*80}")

    if result.total_trades == 0:
        print("No valid trades for this period.")
        return

    # Basic stats
    print(f"\n📊 Trade Statistics:")
    print(f"   Total trades: {result.total_trades}")
    print(f"   Winning trades: {result.winning_trades} ({result.win_rate:.1%})")
    print(f"   Losing trades: {result.losing_trades}")

    # Returns
    print(f"\n💰 Returns:")
    print(f"   Average net return: {result.avg_net_return:.2%}")
    print(f"   Median net return: {result.median_net_return:.2%}")
    print(f"   Total net return: {result.total_net_return:.2%}")
    print(f"   Max win: {result.max_win:.2%}")
    print(f"   Max loss: {result.max_loss:.2%}")

    # Risk metrics
    returns = [t.net_return for t in result.trades]
    calculator = MetricsCalculator(risk_free_rate=config['backtesting']['risk_free_rate'])
    metrics = calculator.calculate_metrics(returns, period)

    print(f"\n⚠️  Risk Metrics:")
    print(f"   Sharpe ratio: {metrics.sharpe_ratio:.2f}")
    print(f"   Max drawdown: {metrics.max_drawdown:.2%}")
    print(f"   Calmar ratio: {metrics.calmar_ratio:.2f}")
    print(f"   Std deviation: {metrics.std_return:.2%}")
    print(f"   Profit factor: {metrics.profit_factor:.2f}" if metrics.profit_factor else "   Profit factor: N/A")

    # Distribution
    print(f"\n📈 Distribution:")
    print(f"   Skewness: {metrics.skewness:.2f}")
    print(f"   Kurtosis: {metrics.kurtosis:.2f}")

    # Benchmark comparison
    if result.alpha is not None:
        print(f"\n🎯 vs S&P 500:")
        print(f"   Strategy avg return: {result.avg_net_return:.2%}")
        print(f"   S&P 500 avg return: {result.avg_spy_return:.2%}")
        print(f"   Alpha: {result.alpha:.2%}")

    # Top 5 trades
    print(f"\n🏆 Top 5 Trades:")
    top_trades = sorted(result.trades, key=lambda t: t.net_return, reverse=True)[:5]
    for i, trade in enumerate(top_trades, 1):
        print(f"   {i}. {trade.ticker} ({trade.entry_date.date()}) → {trade.net_return:.2%}")

    # Bottom 5 trades
    print(f"\n💥 Bottom 5 Trades:")
    bottom_trades = sorted(result.trades, key=lambda t: t.net_return)[:5]
    for i, trade in enumerate(bottom_trades, 1):
        print(f"   {i}. {trade.ticker} ({trade.entry_date.date()}) → {trade.net_return:.2%}")


def main():
    parser = argparse.ArgumentParser(description='Run backtest on insider trading signals')
    parser.add_argument('--config', default='config.yaml', help='Path to config file')
    parser.add_argument('--db', default='data/insider_trades.db', help='Path to database')
    parser.add_argument('--min-score', type=float, default=2.0, help='Minimum signal score')
    parser.add_argument('--limit', type=int, default=100, help='Max signals to test')
    parser.add_argument('--periods', nargs='+', type=int, help='Holding periods (overrides config)')
    parser.add_argument('--detailed', type=int, help='Show detailed results for specific period')
    parser.add_argument('--benchmark', action='store_true', help='Include benchmark comparison')

    args = parser.parse_args()

    # Load config
    print(f"Loading config from {args.config}...")
    config = load_config(args.config)

    # Load signals
    print(f"Loading signals from {args.db}...")
    signals = load_signals_from_db(args.db, args.min_score, args.limit)

    if not signals:
        print("Error: No signals found in database.")
        return 1

    print(f"Loaded {len(signals)} signals")
    print(f"Score range: {min(s.composite_score for s in signals):.2f} - {max(s.composite_score for s in signals):.2f}")
    print(f"Date range: {min(s.filing_date for s in signals).date()} - {max(s.filing_date for s in signals).date()}")

    # Get holding periods
    holding_periods = args.periods if args.periods else config['backtesting']['holding_periods']

    # Initialize backtest engine
    engine = BacktestEngine(
        commission_pct=config['backtesting']['commission_pct'],
        slippage_pct=config['backtesting']['slippage_pct']
    )

    # Run backtest
    print(f"\nRunning backtest for {len(holding_periods)} holding periods...")
    results = engine.backtest_multiple_periods(signals, holding_periods)

    # Add benchmark comparison if requested
    if args.benchmark:
        print("\nCalculating benchmark comparison...")
        for period, result in results.items():
            if result.total_trades > 0:
                results[period] = engine.add_benchmark_comparison(
                    result,
                    config['backtesting']['benchmark_ticker']
                )

    # Print summary table
    print(format_results_table(results))

    # Print detailed results if requested
    if args.detailed is not None:
        if args.detailed in results:
            print_detailed_results(args.detailed, results[args.detailed], config)
        else:
            print(f"\nError: No results found for {args.detailed}d holding period")

    print("\n✅ Backtest complete!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
