"""
OpenInsider.com Scraper

Scrapes insider transaction data from OpenInsider.com HTML tables.
"""

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import requests
from bs4 import BeautifulSoup
import yfinance as yf
from sqlalchemy.orm import Session

from ..database.schema import Company, Insider, InsiderTransaction, TransactionCode, TransactionSource

logger = logging.getLogger(__name__)


class OpenInsiderScraper:
    """
    Scrapes insider purchase data from OpenInsider.com.

    Features:
    - Rate limiting (1 request per 2 seconds)
    - Response caching (6 hours)
    - Ticker validation via yfinance
    - Automatic filtering (buys only, min value threshold)
    """

    BASE_URL = "http://openinsider.com/screener"

    def __init__(
        self,
        cache_dir: str = "./data/cache",
        rate_limit_seconds: float = 2.0,
        cache_hours: int = 6
    ):
        """
        Initialize OpenInsider scraper.

        Args:
            cache_dir: Directory for caching responses
            rate_limit_seconds: Minimum seconds between requests
            cache_hours: Hours to cache responses
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.rate_limit = rate_limit_seconds
        self.cache_duration = timedelta(hours=cache_hours)

        self.last_request_time = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

        logger.info(f"OpenInsider scraper initialized (rate limit: {rate_limit_seconds}s)")

    def _make_request(self, url: str, params: Dict) -> Optional[str]:
        """
        Make HTTP request with rate limiting and caching.

        Args:
            url: URL to request
            params: Query parameters

        Returns:
            HTML content or None on error
        """
        # Generate cache key from params
        cache_key = "_".join(f"{k}={v}" for k, v in sorted(params.items()))
        cache_file = self.cache_dir / f"openinsider_{cache_key}.html"

        # Check cache
        if cache_file.exists():
            cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if cache_age < self.cache_duration:
                logger.debug(f"Using cached response (age: {cache_age})")
                return cache_file.read_text()

        # Rate limiting
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            sleep_time = self.rate_limit - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)

        # Make request
        try:
            logger.info(f"Fetching {url} with params {params}")
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            self.last_request_time = time.time()

            # Cache response
            cache_file.write_text(response.text)

            return response.text

        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None

    def _parse_table_row(self, row) -> Optional[Dict]:
        """
        Parse a single table row from OpenInsider HTML.

        Args:
            row: BeautifulSoup <tr> element

        Returns:
            Dictionary with transaction data or None if parsing fails
        """
        try:
            cells = row.find_all('td')
            if len(cells) < 11:
                return None

            # Extract data from cells
            # Column indices based on OpenInsider table structure:
            # 0: X (filing date)
            # 1: Filing Date
            # 2: Trade Date
            # 3: Ticker
            # 4: Company Name
            # 5: Insider Name
            # 6: Title
            # 7: Trade Type
            # 8: Price
            # 9: Qty (shares)
            # 10: Owned
            # 11: ΔOwn
            # 12: Value

            filing_date_str = cells[1].text.strip()
            trade_date_str = cells[2].text.strip()
            ticker = cells[3].text.strip()
            company_name = cells[4].text.strip()
            insider_name = cells[5].text.strip()
            title = cells[6].text.strip()
            trade_type = cells[7].text.strip()
            price_str = cells[8].text.strip().replace('$', '').replace(',', '')
            shares_str = cells[9].text.strip().replace(',', '')
            value_str = cells[12].text.strip().replace('$', '').replace(',', '') if len(cells) > 12 else "0"

            # Parse dates
            filing_date = datetime.strptime(filing_date_str, '%Y-%m-%d %H:%M:%S')
            trade_date = datetime.strptime(trade_date_str, '%Y-%m-%d')

            # Parse trade type (extract first letter: "P - Purchase" -> "P")
            trade_code = trade_type.split('-')[0].strip() if '-' in trade_type else trade_type.strip()

            # Parse numeric values
            # Handle negative values for sales
            price_str = price_str.replace('-', '')
            shares_str = shares_str.replace('-', '')
            value_str = value_str.replace('-', '')

            price = float(price_str) if price_str and price_str != '-' else None
            shares = float(shares_str) if shares_str else 0
            value = float(value_str) if value_str else 0

            # If value is 0 but we have price and shares, calculate it
            if value == 0 and price and shares > 0:
                value = price * shares

            return {
                'filing_date': filing_date,
                'trade_date': trade_date,
                'ticker': ticker,
                'company_name': company_name,
                'insider_name': insider_name,
                'title': title,
                'trade_type': trade_code,  # Use extracted code
                'price': price,
                'shares': shares,
                'value': value
            }

        except (ValueError, IndexError, AttributeError) as e:
            logger.warning(f"Failed to parse row: {e}")
            return None

    def _validate_ticker(self, ticker: str) -> bool:
        """
        Validate that ticker exists and has data in yfinance.

        Args:
            ticker: Stock ticker symbol

        Returns:
            True if ticker is valid
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # Check if we got valid data
            if not info or 'symbol' not in info:
                logger.warning(f"Ticker {ticker} not found in yfinance")
                return False

            return True

        except Exception as e:
            logger.warning(f"Ticker validation failed for {ticker}: {e}")
            return False

    def fetch_latest_purchases(
        self,
        days_back: int = 30,
        min_value: float = 50000,
        max_pages: int = 10
    ) -> pd.DataFrame:
        """
        Fetch latest insider purchases from OpenInsider.

        Args:
            days_back: How many days back to fetch
            min_value: Minimum transaction value to include
            max_pages: Maximum number of pages to fetch

        Returns:
            DataFrame with transaction data
        """
        logger.info(f"Fetching purchases from last {days_back} days (min value: ${min_value:,.0f})")

        all_transactions = []

        for page in range(1, max_pages + 1):
            params = {
                's': '',           # Ticker (blank = all)
                'o': '',           # Use default sorting
                'pl': '',          # Price low
                'ph': '',          # Price high
                'll': '',          # Shares low
                'lh': '',          # Shares high
                'fd': '0',         # Filing date (0 = any)
                'fdr': '',         # Filing date range
                'td': '0',         # Trade date (0 = any)
                'tdr': '',         # Trade date range
                'fdlyl': '',       # Filing delay low
                'fdlyh': '',       # Filing delay high
                'daysago': str(days_back),
                'xp': '1',         # Exclude option exercises
                'xs': '1',         # Exclude small trades
                'vl': '',          # Value low
                'vh': '',          # Value high
                'ocl': '',         # Owned change low
                'och': '',         # Owned change high
                'sic1': '-1',      # SIC code
                'sicl': '100',     # SIC low
                'sich': '9999',    # SIC high
                'grp': '0',        # Grouping
                'nfl': '',         # Filing count low
                'nfh': '',         # Filing count high
                'nil': '',         # Insider count low
                'nih': '',         # Insider count high
                'nol': '',         # Owner count low
                'noh': '',         # Owner count high
                'v2l': '',         # Value 2 low
                'v2h': '',         # Value 2 high
                'oc2l': '',        # Owned change 2 low
                'oc2h': '',        # Owned change 2 high
                'sortcol': '0',    # Sort column
                'cnt': '100',      # Results per page
                'page': str(page)
            }

            html = self._make_request(self.BASE_URL, params)
            if not html:
                logger.error(f"Failed to fetch page {page}")
                break

            # Parse HTML
            soup = BeautifulSoup(html, 'html.parser')
            table = soup.find('table', {'class': 'tinytable'})

            if not table:
                logger.warning(f"No table found on page {page}")
                break

            rows = table.find_all('tr')[1:]  # Skip header row

            if not rows:
                logger.info(f"No more rows on page {page}")
                break

            logger.info(f"Processing page {page} ({len(rows)} rows)")

            for row in rows:
                data = self._parse_table_row(row)
                if not data:
                    continue

                # Filter: only purchases
                if data['trade_type'] != 'P':
                    continue

                # Filter: minimum value
                if data['value'] < min_value:
                    continue

                all_transactions.append(data)

            # If we got fewer than 100 rows, we've reached the end
            if len(rows) < 100:
                break

        if not all_transactions:
            logger.warning("No transactions found")
            return pd.DataFrame()

        df = pd.DataFrame(all_transactions)

        logger.info(f"Fetched {len(df)} transactions")

        # Validate tickers (cache results to avoid repeated calls)
        validated_tickers = set()
        invalid_tickers = set()

        def is_valid(ticker):
            if ticker in validated_tickers:
                return True
            if ticker in invalid_tickers:
                return False

            if self._validate_ticker(ticker):
                validated_tickers.add(ticker)
                return True
            else:
                invalid_tickers.add(ticker)
                return False

        df['ticker_valid'] = df['ticker'].apply(is_valid)

        invalid_count = (~df['ticker_valid']).sum()
        if invalid_count > 0:
            logger.warning(f"Removing {invalid_count} transactions with invalid tickers")
            df = df[df['ticker_valid']]

        df = df.drop(columns=['ticker_valid'])

        logger.info(f"Final dataset: {len(df)} transactions")

        return df

    def save_to_database(self, df: pd.DataFrame, session: Session) -> int:
        """
        Save transactions to database.

        Args:
            df: DataFrame with transaction data
            session: SQLAlchemy session

        Returns:
            Number of transactions saved
        """
        if df.empty:
            logger.warning("No data to save")
            return 0

        saved_count = 0

        for _, row in df.iterrows():
            try:
                # Get or create company
                company = session.query(Company).filter_by(ticker=row['ticker']).first()
                if not company:
                    company = Company(
                        ticker=row['ticker'],
                        name=row['company_name']
                    )
                    session.add(company)
                    session.flush()

                # Get or create insider
                insider = session.query(Insider).filter_by(
                    name=row['insider_name'],
                    company_id=company.id
                ).first()

                if not insider:
                    insider = Insider(
                        name=row['insider_name'],
                        company_id=company.id,
                        title=row['title']
                    )
                    session.add(insider)
                    session.flush()

                # Check if transaction already exists
                existing = session.query(InsiderTransaction).filter_by(
                    insider_id=insider.id,
                    company_id=company.id,
                    trade_date=row['trade_date'],
                    transaction_code=TransactionCode.P,
                    shares=row['shares']
                ).first()

                if existing:
                    logger.debug(f"Transaction already exists: {row['ticker']} - {row['insider_name']}")
                    continue

                # Create transaction
                transaction = InsiderTransaction(
                    insider_id=insider.id,
                    company_id=company.id,
                    trade_date=row['trade_date'],
                    filing_date=row['filing_date'],
                    transaction_code=TransactionCode.P,
                    shares=row['shares'],
                    price_per_share=row['price'],
                    total_value=row['value'],
                    source=TransactionSource.OPENINSIDER
                )
                session.add(transaction)

                # Commit immediately to avoid batch failures on duplicates
                try:
                    session.commit()
                    saved_count += 1
                except Exception as commit_error:
                    session.rollback()
                    # Check if it's a duplicate error (expected) or something else
                    if 'UNIQUE constraint failed' in str(commit_error):
                        logger.debug(f"Duplicate transaction detected (already in DB): {row['ticker']}")
                    else:
                        logger.error(f"Failed to commit transaction: {commit_error}")
                    continue

            except Exception as e:
                logger.error(f"Failed to save transaction: {e}")
                session.rollback()
                continue

        logger.info(f"Saved {saved_count} transactions to database")
        return saved_count
