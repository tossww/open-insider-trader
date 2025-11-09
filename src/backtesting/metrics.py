"""
Risk and performance metrics for backtesting.

Calculates Sharpe ratio, max drawdown, Calmar ratio, and other key metrics.
"""

from typing import List, Optional
import numpy as np
from dataclasses import dataclass


@dataclass
class RiskMetrics:
    """Risk-adjusted performance metrics."""

    # Return metrics
    total_return: float
    avg_return: float
    median_return: float
    std_return: float

    # Risk metrics
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: float

    # Trade statistics
    win_rate: float
    profit_factor: Optional[float]  # Avg win / Avg loss

    # Outlier analysis
    skewness: float
    kurtosis: float

    def to_dict(self):
        """Convert to dictionary for display."""
        return {
            'total_return': f"{self.total_return:.2%}",
            'avg_return': f"{self.avg_return:.2%}",
            'median_return': f"{self.median_return:.2%}",
            'std_return': f"{self.std_return:.2%}",
            'sharpe_ratio': f"{self.sharpe_ratio:.2f}",
            'max_drawdown': f"{self.max_drawdown:.2%}",
            'calmar_ratio': f"{self.calmar_ratio:.2f}",
            'win_rate': f"{self.win_rate:.1%}",
            'profit_factor': f"{self.profit_factor:.2f}" if self.profit_factor else "N/A",
            'skewness': f"{self.skewness:.2f}",
            'kurtosis': f"{self.kurtosis:.2f}"
        }


class MetricsCalculator:
    """Calculate risk and performance metrics from trade results."""

    def __init__(self, risk_free_rate: float = 0.04):
        """
        Initialize calculator.

        Args:
            risk_free_rate: Annual risk-free rate (e.g., 0.04 = 4%)
        """
        self.risk_free_rate = risk_free_rate

    def calculate_sharpe_ratio(
        self,
        returns: List[float],
        holding_days: int
    ) -> float:
        """
        Calculate annualized Sharpe ratio.

        Args:
            returns: List of trade returns (as decimals, e.g., 0.05 = 5%)
            holding_days: Holding period in trading days

        Returns:
            Annualized Sharpe ratio
        """
        if not returns or len(returns) < 2:
            return 0.0

        avg_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)

        if std_return == 0:
            return 0.0

        # Annualize both metrics (assuming 252 trading days per year)
        periods_per_year = 252 / holding_days
        annualized_return = avg_return * periods_per_year
        annualized_std = std_return * np.sqrt(periods_per_year)

        # Sharpe = (Return - Risk-free rate) / Std
        sharpe = (annualized_return - self.risk_free_rate) / annualized_std
        return sharpe

    def calculate_max_drawdown(self, returns: List[float]) -> float:
        """
        Calculate maximum drawdown from cumulative returns.

        Args:
            returns: List of trade returns

        Returns:
            Maximum drawdown as a positive percentage (e.g., 0.25 = 25% drawdown)
        """
        if not returns:
            return 0.0

        # Calculate cumulative returns
        cumulative = np.cumprod([1 + r for r in returns])

        # Calculate running maximum
        running_max = np.maximum.accumulate(cumulative)

        # Calculate drawdown at each point
        drawdowns = (running_max - cumulative) / running_max

        return float(np.max(drawdowns))

    def calculate_calmar_ratio(
        self,
        returns: List[float],
        holding_days: int
    ) -> float:
        """
        Calculate Calmar ratio (annualized return / max drawdown).

        Args:
            returns: List of trade returns
            holding_days: Holding period in trading days

        Returns:
            Calmar ratio (higher is better)
        """
        if not returns:
            return 0.0

        avg_return = np.mean(returns)
        periods_per_year = 252 / holding_days
        annualized_return = avg_return * periods_per_year

        max_dd = self.calculate_max_drawdown(returns)

        if max_dd == 0:
            return float('inf') if annualized_return > 0 else 0.0

        return annualized_return / max_dd

    def calculate_profit_factor(self, returns: List[float]) -> Optional[float]:
        """
        Calculate profit factor (sum of wins / sum of losses).

        Args:
            returns: List of trade returns

        Returns:
            Profit factor or None if no losing trades
        """
        if not returns:
            return None

        wins = [r for r in returns if r > 0]
        losses = [abs(r) for r in returns if r < 0]

        if not losses:
            return None  # Can't calculate if no losses

        total_wins = sum(wins)
        total_losses = sum(losses)

        if total_losses == 0:
            return None

        return total_wins / total_losses

    def calculate_metrics(
        self,
        returns: List[float],
        holding_days: int
    ) -> RiskMetrics:
        """
        Calculate all risk metrics.

        Args:
            returns: List of trade returns
            holding_days: Holding period in trading days

        Returns:
            RiskMetrics object with all calculated metrics
        """
        if not returns:
            return RiskMetrics(
                total_return=0.0,
                avg_return=0.0,
                median_return=0.0,
                std_return=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                calmar_ratio=0.0,
                win_rate=0.0,
                profit_factor=None,
                skewness=0.0,
                kurtosis=0.0
            )

        returns_array = np.array(returns)

        # Return metrics
        total_return = np.sum(returns_array)
        avg_return = np.mean(returns_array)
        median_return = np.median(returns_array)
        std_return = np.std(returns_array, ddof=1) if len(returns) > 1 else 0.0

        # Risk metrics
        sharpe_ratio = self.calculate_sharpe_ratio(returns, holding_days)
        max_drawdown = self.calculate_max_drawdown(returns)
        calmar_ratio = self.calculate_calmar_ratio(returns, holding_days)

        # Trade statistics
        win_rate = len([r for r in returns if r > 0]) / len(returns)
        profit_factor = self.calculate_profit_factor(returns)

        # Distribution metrics
        from scipy.stats import skew, kurtosis
        skewness = float(skew(returns_array)) if len(returns) > 2 else 0.0
        kurt = float(kurtosis(returns_array)) if len(returns) > 3 else 0.0

        return RiskMetrics(
            total_return=total_return,
            avg_return=avg_return,
            median_return=median_return,
            std_return=std_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            calmar_ratio=calmar_ratio,
            win_rate=win_rate,
            profit_factor=profit_factor,
            skewness=skewness,
            kurtosis=kurt
        )


def compare_to_benchmark(
    strategy_metrics: RiskMetrics,
    benchmark_metrics: RiskMetrics
) -> dict:
    """
    Compare strategy metrics to benchmark.

    Args:
        strategy_metrics: Metrics for the strategy
        benchmark_metrics: Metrics for the benchmark

    Returns:
        Dictionary with comparison results
    """
    return {
        'alpha': strategy_metrics.avg_return - benchmark_metrics.avg_return,
        'sharpe_diff': strategy_metrics.sharpe_ratio - benchmark_metrics.sharpe_ratio,
        'drawdown_diff': strategy_metrics.max_drawdown - benchmark_metrics.max_drawdown,
        'calmar_diff': strategy_metrics.calmar_ratio - benchmark_metrics.calmar_ratio,
        'win_rate_diff': strategy_metrics.win_rate - benchmark_metrics.win_rate
    }
