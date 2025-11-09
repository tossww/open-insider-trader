"""
Historical price data fetcher for backtesting.

Uses yfinance to get OHLCV data with robust error handling.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import yfinance as yf
import pandas as pd
from dataclasses import dataclass
import time


@dataclass
class PriceData:
    """Container for historical price data."""
    ticker: str
    dates: pd.DatetimeIndex
    open: pd.Series
    high: pd.Series
    low: pd.Series
    close: pd.Series
    volume: pd.Series

    def get_price_on_date(self, date: datetime, price_type: str = 'open') -> Optional[float]:
        """
        Get price on specific date, handling missing data.

        Args:
            date: Target date
            price_type: 'open', 'close', 'high', 'low'

        Returns:
            Price if available, None if date not found
        """
        date_normalized = pd.Timestamp(date).normalize()

        # Make timezone-aware if index is timezone-aware
        if hasattr(self.dates, 'tz') and self.dates.tz is not None:
            if date_normalized.tz is None:
                date_normalized = date_normalized.tz_localize(self.dates.tz)

        if price_type == 'open':
            series = self.open
        elif price_type == 'close':
            series = self.close
        elif price_type == 'high':
            series = self.high
        elif price_type == 'low':
            series = self.low
        else:
            raise ValueError(f"Invalid price_type: {price_type}")

        # Try exact match
        if date_normalized in series.index:
            return float(series.loc[date_normalized])

        # Try forward fill (next available trading day)
        future_dates = series.index[series.index >= date_normalized]
        if len(future_dates) > 0:
            return float(series.loc[future_dates[0]])

        return None

    def get_return_over_period(
        self,
        start_date: datetime,
        holding_days: int,
        entry_price_type: str = 'open',
        exit_price_type: str = 'close'
    ) -> Optional[float]:
        """
        Calculate return over holding period.

        Args:
            start_date: Entry date
            holding_days: Number of trading days to hold (-1 = hold to end)
            entry_price_type: Price type for entry
            exit_price_type: Price type for exit

        Returns:
            Percentage return (e.g., 0.05 = 5%) or None if data unavailable
        """
        entry_price = self.get_price_on_date(start_date, entry_price_type)
        if entry_price is None:
            return None

        # Calculate exit date
        start_normalized = pd.Timestamp(start_date).normalize()

        # Make timezone-aware if index is timezone-aware
        if hasattr(self.dates, 'tz') and self.dates.tz is not None:
            if start_normalized.tz is None:
                start_normalized = start_normalized.tz_localize(self.dates.tz)

        future_dates = self.dates[self.dates >= start_normalized]

        if len(future_dates) == 0:
            return None

        if holding_days == -1:
            # Hold until end of data
            exit_date = future_dates[-1]
        else:
            # Find Nth trading day after entry
            if len(future_dates) <= holding_days:
                # Not enough data for full holding period
                return None
            exit_date = future_dates[holding_days]

        exit_price = self.get_price_on_date(exit_date, exit_price_type)
        if exit_price is None:
            return None

        # Calculate simple return
        return (exit_price - entry_price) / entry_price


class PriceDataFetcher:
    """Fetches and caches historical price data."""

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize fetcher.

        Args:
            cache_dir: Directory to cache price data (optional)
        """
        self.cache_dir = cache_dir
        self._cache: Dict[str, PriceData] = {}

    def fetch(
        self,
        ticker: str,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        retry_attempts: int = 3,
        retry_delay: float = 1.0
    ) -> Optional[PriceData]:
        """
        Fetch historical price data for a ticker.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date for data
            end_date: End date for data (None = today)
            retry_attempts: Number of retry attempts on failure
            retry_delay: Delay between retries in seconds

        Returns:
            PriceData object or None if fetch fails
        """
        # Check cache
        cache_key = f"{ticker}_{start_date.date()}_{end_date.date() if end_date else 'now'}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Fetch from yfinance with retry logic
        for attempt in range(retry_attempts):
            try:
                # Add buffer to start date to ensure we have data
                buffered_start = start_date - timedelta(days=30)

                yf_ticker = yf.Ticker(ticker)
                df = yf_ticker.history(
                    start=buffered_start,
                    end=end_date,
                    actions=False,  # Don't include dividends/splits
                    auto_adjust=True  # Adjust for splits
                )

                if df.empty:
                    print(f"Warning: No data returned for {ticker}")
                    return None

                # Create PriceData object
                price_data = PriceData(
                    ticker=ticker,
                    dates=df.index,
                    open=df['Open'],
                    high=df['High'],
                    low=df['Low'],
                    close=df['Close'],
                    volume=df['Volume']
                )

                # Cache result
                self._cache[cache_key] = price_data
                return price_data

            except Exception as e:
                if attempt < retry_attempts - 1:
                    print(f"Warning: Error fetching {ticker} (attempt {attempt+1}/{retry_attempts}): {e}")
                    time.sleep(retry_delay)
                else:
                    print(f"Error: Failed to fetch {ticker} after {retry_attempts} attempts: {e}")
                    return None

        return None

    def fetch_batch(
        self,
        tickers: List[str],
        start_date: datetime,
        end_date: Optional[datetime] = None
    ) -> Dict[str, PriceData]:
        """
        Fetch price data for multiple tickers.

        Args:
            tickers: List of ticker symbols
            start_date: Start date for data
            end_date: End date for data (None = today)

        Returns:
            Dictionary mapping ticker to PriceData (excludes failed fetches)
        """
        results = {}

        for ticker in tickers:
            print(f"Fetching price data for {ticker}...")
            price_data = self.fetch(ticker, start_date, end_date)
            if price_data:
                results[ticker] = price_data

            # Rate limiting (yfinance has limits)
            time.sleep(0.5)

        return results
