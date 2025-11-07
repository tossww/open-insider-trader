"""
Quick test script to verify AI analysis integration.

Tests the BacktestAnalyzer with sample metrics.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from ai.analyzer import BacktestAnalyzer
from backtesting.metrics import RiskMetrics


def test_ai_analysis():
    """Test AI analyzer with sample metrics."""
    print("🤖 Testing AI Analysis Integration\n")
    print("=" * 60)

    # Create sample strategy metrics (based on TSLA backtest)
    strategy_metrics = RiskMetrics(
        total_return=0.6573,  # 65.73%
        avg_return=0.0438,    # 4.38%
        median_return=0.0438,
        std_return=0.0,       # All trades identical (TSLA only)
        sharpe_ratio=15.0,    # Very high due to no variance
        max_drawdown=0.0,     # No drawdown (all positive)
        calmar_ratio=999.0,   # Infinite due to no drawdown
        win_rate=1.0,         # 100% win rate
        profit_factor=None,   # No losses
        skewness=0.0,
        kurtosis=0.0
    )

    # Create benchmark metrics (approximate SPY)
    benchmark_metrics = RiskMetrics(
        total_return=0.0106,  # 1.06% (avg SPY 21d)
        avg_return=0.0071,    # 0.71%
        median_return=0.0071,
        std_return=0.01,
        sharpe_ratio=0.5,
        max_drawdown=0.05,    # 5% typical drawdown
        calmar_ratio=0.3,
        win_rate=0.6,
        profit_factor=None,
        skewness=0.0,
        kurtosis=0.0
    )

    alpha = 0.0367  # +3.67%

    # Initialize analyzer
    try:
        analyzer = BacktestAnalyzer()
        print("✅ Analyzer initialized successfully\n")
    except ValueError as e:
        print(f"❌ Failed to initialize analyzer: {e}")
        print("   Make sure ANTHROPIC_API_KEY is set in .env")
        return

    # Run analysis
    print("📊 Analyzing backtest results...")
    print(f"   Strategy: {strategy_metrics.avg_return:.2%} avg return")
    print(f"   Benchmark: {benchmark_metrics.avg_return:.2%} avg return")
    print(f"   Alpha: {alpha:+.2%}\n")

    try:
        recommendation = analyzer.analyze(
            strategy_metrics=strategy_metrics,
            benchmark_metrics=benchmark_metrics,
            alpha=alpha,
            holding_days=21,
            total_signals=15,
            period_label="21 days"
        )

        print("=" * 60)
        print(f"\n🎯 RECOMMENDATION: {recommendation.recommendation}")
        print(f"💪 CONFIDENCE: {recommendation.confidence}\n")

        print("📊 KEY FINDINGS:")
        for i, finding in enumerate(recommendation.rationale, 1):
            print(f"   {i}. {finding}")

        print("\n⚠️  RISK FACTORS:")
        for i, risk in enumerate(recommendation.risk_factors, 1):
            print(f"   {i}. {risk}")

        print("\n" + "=" * 60)
        print("✅ AI Analysis Integration Test: PASSED")

    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_ai_analysis()
