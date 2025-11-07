"""
Market Cap Data Fetcher

Fetches historical market capitalization data using Yahoo Finance (yfinance).
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import yfinance as yf
from functools import lru_cache

logger = logging.getLogger(__name__)


class MarketCapFetcher:
    """
    Fetches market capitalization data for companies.

    Uses yfinance to get historical market cap data. Implements caching
    to avoid redundant API calls.
    """

    def __init__(self):
        """Initialize market cap fetcher."""
        self.cache: Dict[str, Dict[str, float]] = {}  # {ticker: {date_str: market_cap}}
        logger.info("Initialized MarketCapFetcher")

    @lru_cache(maxsize=1000)
    def _get_ticker_info(self, ticker: str) -> Optional[yf.Ticker]:
        """
        Get yfinance Ticker object (cached).

        Args:
            ticker: Stock ticker symbol

        Returns:
            yfinance Ticker object or None if failed
        """
        try:
            return yf.Ticker(ticker)
        except Exception as e:
            logger.error(f"Failed to get ticker info for {ticker}: {e}")
            return None

    def get_market_cap_at_date(self, ticker: str, date: datetime) -> Optional[float]:
        """
        Get market capitalization for a ticker at a specific date.

        Args:
            ticker: Stock ticker symbol
            date: Date to fetch market cap for

        Returns:
            Market cap in USD or None if unavailable
        """
        ticker = ticker.upper()
        date_str = date.strftime('%Y-%m-%d')

        # Check cache
        if ticker in self.cache and date_str in self.cache[ticker]:
            logger.debug(f"Cache hit for {ticker} on {date_str}")
            return self.cache[ticker][date_str]

        # Try primary method: get historical data around the date
        market_cap = self._fetch_market_cap_from_history(ticker, date)

        # Fallback: try to calculate from shares outstanding × price
        if market_cap is None:
            market_cap = self._calculate_market_cap_from_price(ticker, date)

        # Cache result (even if None to avoid repeated failures)
        if ticker not in self.cache:
            self.cache[ticker] = {}
        self.cache[ticker][date_str] = market_cap

        if market_cap:
            logger.info(f"Fetched market cap for {ticker} on {date_str}: ${market_cap:,.0f}")
        else:
            logger.warning(f"Could not fetch market cap for {ticker} on {date_str}")

        return market_cap

    def _fetch_market_cap_from_history(self, ticker: str, date: datetime) -> Optional[float]:
        """
        Fetch market cap from yfinance historical data.

        Args:
            ticker: Stock ticker
            date: Target date

        Returns:
            Market cap in USD or None
        """
        try:
            ticker_obj = self._get_ticker_info(ticker)
            if not ticker_obj:
                return None

            # Get historical data for a window around the target date
            # (in case target date is weekend/holiday)
            start_date = date - timedelta(days=7)
            end_date = date + timedelta(days=1)

            hist = ticker_obj.history(start=start_date, end=end_date)

            if hist.empty:
                logger.warning(f"No historical data for {ticker} around {date}")
                return None

            # Get closest date to target
            hist.index = hist.index.tz_localize(None)  # Remove timezone
            closest_date = min(hist.index, key=lambda d: abs((d - date).days))

            # Try to get market cap from info (this is current market cap)
            info = ticker_obj.info
            if 'marketCap' in info and info['marketCap']:
                # If we have current market cap, scale it by price ratio
                current_price = hist.loc[closest_date, 'Close']
                latest_price = info.get('currentPrice') or info.get('regularMarketPrice')

                if latest_price and current_price:
                    current_market_cap = info['marketCap']
                    historical_market_cap = current_market_cap * (current_price / latest_price)
                    return float(historical_market_cap)

            # Fallback: calculate from shares outstanding if available
            shares_outstanding = info.get('sharesOutstanding')
            if shares_outstanding:
                close_price = hist.loc[closest_date, 'Close']
                market_cap = shares_outstanding * close_price
                return float(market_cap)

            return None

        except Exception as e:
            logger.error(f"Error fetching market cap for {ticker} from history: {e}")
            return None

    def _calculate_market_cap_from_price(self, ticker: str, date: datetime) -> Optional[float]:
        """
        Calculate market cap from shares outstanding × price.

        Args:
            ticker: Stock ticker
            date: Target date

        Returns:
            Market cap in USD or None
        """
        try:
            ticker_obj = self._get_ticker_info(ticker)
            if not ticker_obj:
                return None

            # Get shares outstanding
            info = ticker_obj.info
            shares_outstanding = info.get('sharesOutstanding')

            if not shares_outstanding:
                return None

            # Get historical price
            start_date = date - timedelta(days=7)
            end_date = date + timedelta(days=1)
            hist = ticker_obj.history(start=start_date, end=end_date)

            if hist.empty:
                return None

            hist.index = hist.index.tz_localize(None)
            closest_date = min(hist.index, key=lambda d: abs((d - date).days))
            price = hist.loc[closest_date, 'Close']

            market_cap = shares_outstanding * price
            return float(market_cap)

        except Exception as e:
            logger.error(f"Error calculating market cap for {ticker}: {e}")
            return None

    def get_bulk_market_caps(self, ticker_date_pairs: List[tuple]) -> Dict[tuple, Optional[float]]:
        """
        Fetch market caps for multiple ticker-date pairs.

        Args:
            ticker_date_pairs: List of (ticker, date) tuples

        Returns:
            Dictionary mapping (ticker, date) to market cap
        """
        results = {}

        for ticker, date in ticker_date_pairs:
            market_cap = self.get_market_cap_at_date(ticker, date)
            results[(ticker, date)] = market_cap

        return results

    def clear_cache(self):
        """Clear the market cap cache."""
        self.cache.clear()
        logger.info("Market cap cache cleared")
