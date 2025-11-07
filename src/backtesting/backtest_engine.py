"""
VectorBT-based backtesting engine for insider trading signals.

Handles multiple holding periods, transaction costs, and benchmark comparison.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np
from .price_data import PriceDataFetcher, PriceData


@dataclass
class Signal:
    """Insider trading signal to backtest."""
    ticker: str
    filing_date: datetime
    trade_date: datetime
    insider_name: str
    officer_title: str
    total_value: float
    composite_score: float
    cluster_size: int


@dataclass
class TradeResult:
    """Result of a single trade."""
    ticker: str
    entry_date: datetime
    exit_date: datetime
    holding_days: int
    entry_price: float
    exit_price: float
    gross_return: float  # Before costs
    net_return: float    # After costs
    signal_score: float


@dataclass
class BacktestResult:
    """Complete backtest results for a holding period."""
    holding_period_days: int
    trades: List[TradeResult]

    # Aggregate metrics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float

    avg_gross_return: float
    avg_net_return: float
    median_net_return: float

    total_gross_return: float
    total_net_return: float

    max_win: float
    max_loss: float

    # Benchmark comparison
    avg_spy_return: Optional[float] = None
    alpha: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for easy display."""
        return {
            'holding_period_days': self.holding_period_days,
            'total_trades': self.total_trades,
            'win_rate': f"{self.win_rate:.1%}",
            'avg_net_return': f"{self.avg_net_return:.2%}",
            'median_net_return': f"{self.median_net_return:.2%}",
            'total_net_return': f"{self.total_net_return:.2%}",
            'max_win': f"{self.max_win:.2%}",
            'max_loss': f"{self.max_loss:.2%}",
            'avg_spy_return': f"{self.avg_spy_return:.2%}" if self.avg_spy_return else "N/A",
            'alpha': f"{self.alpha:.2%}" if self.alpha else "N/A"
        }


class BacktestEngine:
    """
    Backtesting engine for insider trading signals.

    Uses simple position-by-position backtesting rather than portfolio simulation.
    Each signal is traded independently with fixed position size.
    """

    def __init__(
        self,
        commission_pct: float = 0.002,
        slippage_pct: float = 0.001,
        price_fetcher: Optional[PriceDataFetcher] = None
    ):
        """
        Initialize backtest engine.

        Args:
            commission_pct: Commission per side (e.g., 0.002 = 0.2%)
            slippage_pct: Slippage per side (e.g., 0.001 = 0.1%)
            price_fetcher: Price data fetcher (creates new one if None)
        """
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct
        self.cost_per_side = commission_pct + slippage_pct
        self.total_cost = self.cost_per_side * 2  # Round-trip

        self.price_fetcher = price_fetcher or PriceDataFetcher()

    def backtest_signal(
        self,
        signal: Signal,
        holding_days: int,
        price_data: PriceData
    ) -> Optional[TradeResult]:
        """
        Backtest a single signal.

        Args:
            signal: Signal to trade
            holding_days: Number of trading days to hold (-1 = hold to end)
            price_data: Historical price data for ticker

        Returns:
            TradeResult or None if trade couldn't be executed
        """
        # Entry: Next trading day after filing date, at open
        entry_date = signal.filing_date + timedelta(days=1)
        entry_price = price_data.get_price_on_date(entry_date, 'open')

        if entry_price is None:
            return None

        # Calculate exit date
        entry_normalized = pd.Timestamp(entry_date).normalize()

        # Make timezone-aware if index is timezone-aware
        if hasattr(price_data.dates, 'tz') and price_data.dates.tz is not None:
            if entry_normalized.tz is None:
                entry_normalized = entry_normalized.tz_localize(price_data.dates.tz)

        future_dates = price_data.dates[price_data.dates >= entry_normalized]

        if len(future_dates) == 0:
            return None

        if holding_days == -1:
            # Hold until end of data
            exit_date_idx = len(future_dates) - 1
        else:
            # Hold for N trading days
            exit_date_idx = min(holding_days, len(future_dates) - 1)

        if exit_date_idx == 0:
            # Not enough data
            return None

        exit_date = future_dates[exit_date_idx]
        exit_price = price_data.get_price_on_date(exit_date, 'close')

        if exit_price is None:
            return None

        # Calculate returns
        gross_return = (exit_price - entry_price) / entry_price
        net_return = gross_return - self.total_cost

        actual_holding_days = exit_date_idx

        return TradeResult(
            ticker=signal.ticker,
            entry_date=entry_date,
            exit_date=exit_date.to_pydatetime(),
            holding_days=actual_holding_days,
            entry_price=entry_price,
            exit_price=exit_price,
            gross_return=gross_return,
            net_return=net_return,
            signal_score=signal.composite_score
        )

    def backtest_signals(
        self,
        signals: List[Signal],
        holding_days: int
    ) -> BacktestResult:
        """
        Backtest multiple signals for a single holding period.

        Args:
            signals: List of signals to trade
            holding_days: Number of trading days to hold

        Returns:
            Aggregated backtest results
        """
        # Fetch price data for all unique tickers
        tickers = list(set(s.ticker for s in signals))
        min_date = min(s.filing_date for s in signals)

        print(f"\nBacktesting {len(signals)} signals for {holding_days} day holding period...")
        print(f"Fetching price data for {len(tickers)} tickers from {min_date.date()}...")

        price_data_map = self.price_fetcher.fetch_batch(
            tickers,
            start_date=min_date,
            end_date=None
        )

        # Backtest each signal
        trade_results: List[TradeResult] = []

        for signal in signals:
            if signal.ticker not in price_data_map:
                print(f"Warning: No price data for {signal.ticker}, skipping")
                continue

            result = self.backtest_signal(
                signal,
                holding_days,
                price_data_map[signal.ticker]
            )

            if result:
                trade_results.append(result)

        # Calculate aggregate metrics
        if not trade_results:
            print(f"Warning: No valid trades for {holding_days} day period")
            return BacktestResult(
                holding_period_days=holding_days,
                trades=[],
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                avg_gross_return=0.0,
                avg_net_return=0.0,
                median_net_return=0.0,
                total_gross_return=0.0,
                total_net_return=0.0,
                max_win=0.0,
                max_loss=0.0
            )

        net_returns = [t.net_return for t in trade_results]
        gross_returns = [t.gross_return for t in trade_results]

        winning_trades = len([r for r in net_returns if r > 0])
        losing_trades = len([r for r in net_returns if r < 0])

        return BacktestResult(
            holding_period_days=holding_days,
            trades=trade_results,
            total_trades=len(trade_results),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=winning_trades / len(trade_results) if trade_results else 0.0,
            avg_gross_return=np.mean(gross_returns),
            avg_net_return=np.mean(net_returns),
            median_net_return=np.median(net_returns),
            total_gross_return=np.sum(gross_returns),
            total_net_return=np.sum(net_returns),
            max_win=max(net_returns),
            max_loss=min(net_returns)
        )

    def backtest_multiple_periods(
        self,
        signals: List[Signal],
        holding_periods: List[int]
    ) -> Dict[int, BacktestResult]:
        """
        Backtest signals across multiple holding periods.

        Args:
            signals: List of signals to trade
            holding_periods: List of holding periods in trading days

        Returns:
            Dictionary mapping holding period to BacktestResult
        """
        results = {}

        for period in holding_periods:
            period_label = f"{period}d" if period != -1 else "max"
            print(f"\n{'='*60}")
            print(f"Testing holding period: {period_label}")
            print(f"{'='*60}")

            result = self.backtest_signals(signals, period)
            results[period] = result

            # Print summary
            if result.total_trades > 0:
                print(f"\nResults for {period_label} holding period:")
                print(f"  Total trades: {result.total_trades}")
                print(f"  Win rate: {result.win_rate:.1%}")
                print(f"  Avg net return: {result.avg_net_return:.2%}")
                print(f"  Total net return: {result.total_net_return:.2%}")
                print(f"  Max win: {result.max_win:.2%}")
                print(f"  Max loss: {result.max_loss:.2%}")

        return results

    def add_benchmark_comparison(
        self,
        result: BacktestResult,
        benchmark_ticker: str = '^GSPC'
    ) -> BacktestResult:
        """
        Add S&P 500 benchmark comparison to backtest result.

        Args:
            result: Backtest result to enhance
            benchmark_ticker: Benchmark ticker (default: ^GSPC for S&P 500)

        Returns:
            Enhanced BacktestResult with benchmark metrics
        """
        if not result.trades:
            return result

        # Fetch SPY data for same date range
        min_date = min(t.entry_date for t in result.trades)
        max_date = max(t.exit_date for t in result.trades)

        spy_data = self.price_fetcher.fetch(
            benchmark_ticker,
            start_date=min_date,
            end_date=max_date
        )

        if not spy_data:
            print(f"Warning: Could not fetch benchmark data for {benchmark_ticker}")
            return result

        # Calculate SPY returns for same periods
        spy_returns = []

        for trade in result.trades:
            spy_return = spy_data.get_return_over_period(
                start_date=trade.entry_date,
                holding_days=trade.holding_days,
                entry_price_type='open',
                exit_price_type='close'
            )

            if spy_return is not None:
                # Apply same transaction costs to benchmark
                spy_return_net = spy_return - self.total_cost
                spy_returns.append(spy_return_net)

        if spy_returns:
            avg_spy_return = np.mean(spy_returns)
            alpha = result.avg_net_return - avg_spy_return

            result.avg_spy_return = avg_spy_return
            result.alpha = alpha

            print(f"  Benchmark (SPY) avg return: {avg_spy_return:.2%}")
            print(f"  Alpha: {alpha:.2%}")

        return result
