"""
SEC EDGAR API Client for Form 4 Filing Retrieval

This module provides a client for fetching insider trading Form 4 filings from
the SEC EDGAR database with rate limiting and error handling.
"""

import time
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import requests
from xml.etree import ElementTree as ET
from pathlib import Path
import hashlib
import json

logger = logging.getLogger(__name__)


class SECEdgarClient:
    """
    Client for interacting with SEC EDGAR API to retrieve Form 4 filings.

    Features:
    - Rate limiting (10 requests/second per SEC rules)
    - CIK lookup by ticker symbol
    - Form 4 filing retrieval with date ranges
    - XML content fetching
    - Response caching to avoid redundant requests
    - Exponential backoff retry logic
    """

    def __init__(self, config: Dict):
        """
        Initialize SEC EDGAR client with configuration.

        Args:
            config: Dictionary containing SEC API configuration
                - base_url: SEC EDGAR base URL
                - user_agent: Required user agent string
                - rate_limit_per_second: Max requests per second
        """
        self.base_url = config.get('base_url', 'https://www.sec.gov/cgi-bin/browse-edgar')
        self.user_agent = config.get('user_agent', 'OpenInsiderTrader research@example.com')
        self.rate_limit = config.get('rate_limit_per_second', 10)
        self.min_request_interval = 1.0 / self.rate_limit
        self.last_request_time = 0.0

        # Cache directory for responses
        self.cache_dir = Path('./data/cache/sec_edgar')
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept-Encoding': 'gzip, deflate',
            'Host': 'www.sec.gov'
        })

        logger.info(f"Initialized SEC EDGAR client with rate limit {self.rate_limit} req/s")

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _make_request(self, url: str, params: Dict = None, max_retries: int = 3) -> Optional[requests.Response]:
        """
        Make HTTP request with rate limiting and retry logic.

        Args:
            url: URL to request
            params: Query parameters
            max_retries: Maximum number of retry attempts

        Returns:
            Response object or None if all retries failed
        """
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                response = self.session.get(url, params=params, timeout=30)

                if response.status_code == 200:
                    return response
                elif response.status_code == 429:  # Rate limit exceeded
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Rate limit hit, waiting {wait_time}s before retry")
                    time.sleep(wait_time)
                else:
                    logger.error(f"HTTP {response.status_code} for {url}")
                    return None

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return None

        return None

    def _get_cache_key(self, data: str) -> str:
        """Generate cache key from data string."""
        return hashlib.md5(data.encode()).hexdigest()

    def _get_cached(self, cache_key: str) -> Optional[str]:
        """Retrieve cached response if available."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cached = json.load(f)
                    # Check if cache is less than 7 days old
                    cache_time = datetime.fromisoformat(cached['timestamp'])
                    if datetime.now() - cache_time < timedelta(days=7):
                        logger.debug(f"Cache hit: {cache_key}")
                        return cached['data']
            except (json.JSONDecodeError, KeyError, ValueError):
                pass
        return None

    def _save_cache(self, cache_key: str, data: str):
        """Save response to cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'data': data
            }, f)

    def get_company_cik(self, ticker: str) -> Optional[str]:
        """
        Convert ticker symbol to CIK (Central Index Key).

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')

        Returns:
            CIK string (zero-padded to 10 digits) or None if not found
        """
        ticker = ticker.upper().strip()
        cache_key = self._get_cache_key(f"cik_{ticker}")

        # Check cache
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # Query SEC for CIK
        params = {
            'action': 'getcompany',
            'CIK': ticker,
            'type': '4',
            'dateb': '',
            'owner': 'only',
            'count': '1',
            'output': 'xml'
        }

        response = self._make_request(self.base_url, params)
        if not response:
            logger.error(f"Failed to retrieve CIK for ticker {ticker}")
            return None

        try:
            # Parse XML to extract CIK
            root = ET.fromstring(response.text)
            cik_elem = root.find('.//CIK')

            if cik_elem is not None and cik_elem.text:
                cik = cik_elem.text.strip().zfill(10)  # Zero-pad to 10 digits
                logger.info(f"Found CIK {cik} for ticker {ticker}")
                self._save_cache(cache_key, cik)
                return cik
            else:
                logger.warning(f"No CIK found for ticker {ticker}")
                return None

        except ET.ParseError as e:
            logger.error(f"Failed to parse CIK response for {ticker}: {e}")
            return None

    def get_form4_filings(self, cik: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Retrieve Form 4 filing URLs for a company within a date range.

        Args:
            cik: Company CIK (10-digit string)
            start_date: Start date for filing search
            end_date: End date for filing search

        Returns:
            List of dictionaries containing filing metadata:
                - filing_url: URL to Form 4 XML
                - filing_date: Date of filing
                - accession_number: SEC accession number
        """
        cache_key = self._get_cache_key(f"form4_{cik}_{start_date.date()}_{end_date.date()}")

        # Check cache
        cached = self._get_cached(cache_key)
        if cached:
            return json.loads(cached)

        params = {
            'action': 'getcompany',
            'CIK': cik,
            'type': '4',
            'dateb': end_date.strftime('%Y%m%d'),
            'owner': 'only',  # Only return insider transaction filings (Form 4)
            'count': '100',  # Max per request
            'output': 'xml'
        }

        response = self._make_request(self.base_url, params)
        if not response:
            logger.error(f"Failed to retrieve Form 4 filings for CIK {cik}")
            return []

        try:
            root = ET.fromstring(response.text)
            filings = []

            for filing in root.findall('.//filing'):
                filing_date_elem = filing.find('dateFiled')  # Capital F!
                filing_href_elem = filing.find('filingHREF')

                if filing_date_elem is not None and filing_href_elem is not None:
                    filing_date_str = filing_date_elem.text
                    filing_href = filing_href_elem.text

                    # Filter by start_date in post-processing (SEC API doesn't handle date ranges well)
                    try:
                        filing_date_obj = datetime.strptime(filing_date_str, '%Y-%m-%d')
                        if filing_date_obj < start_date:
                            continue  # Skip filings before start date
                    except ValueError:
                        pass  # If date parsing fails, include it anyway

                    # Extract accession number from HREF
                    # Example: https://www.sec.gov/Archives/edgar/data/1318605/000110465925090923/0001104659-25-090923-index.htm
                    # Accession: 0001104659-25-090923
                    try:
                        href_parts = filing_href.split('/')
                        accession_part = href_parts[-1].replace('-index.htm', '')
                        accession = accession_part
                        accession_dir = href_parts[-2]
                    except (IndexError, AttributeError):
                        logger.warning(f"Could not parse accession from {filing_href}")
                        continue

                    # Construct URL to the Form 4 XML
                    # We need to get the primary doc, usually ends in .xml
                    # For now, use the index page and we'll extract XML from it
                    filing_url = filing_href

                    filings.append({
                        'filing_url': filing_url,
                        'filing_date': filing_date_str,
                        'accession_number': accession
                    })

            logger.info(f"Found {len(filings)} Form 4 filings for CIK {cik} between {start_date.date()} and {end_date.date()}")

            # Cache results
            self._save_cache(cache_key, json.dumps(filings))

            return filings

        except ET.ParseError as e:
            logger.error(f"Failed to parse Form 4 filings for CIK {cik}: {e}")
            return []

    def get_form4_xml(self, filing_url: str) -> Optional[str]:
        """
        Download Form 4 XML content from SEC.

        Args:
            filing_url: URL to Form 4 filing (can be index page or direct XML)

        Returns:
            XML content as string or None if failed
        """
        cache_key = self._get_cache_key(f"xml_{filing_url}")

        # Check cache
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # If it's an index page, we need to find the actual XML file
        if '-index.htm' in filing_url:
            # Fetch index page to find XML file
            response = self._make_request(filing_url)
            if not response:
                logger.error(f"Failed to download index page {filing_url}")
                return None

            # Look for link to .xml file (usually primary document)
            # The XML file typically has same name as accession number
            # Example: /Archives/edgar/data/1318605/000110465925090923/tm2526179-1_4seq1.xml
            import re

            # Match href="/Archives/edgar/data/.../.../*.xml"
            xml_links = re.findall(r'href="(/Archives/edgar/data/[^"]*\.xml)"', response.text, re.IGNORECASE)

            if not xml_links:
                # Try alternative pattern
                xml_links = re.findall(r'<a\s+href="([^"]*\.xml)"', response.text, re.IGNORECASE)

            if not xml_links:
                logger.error(f"No XML file found in index page {filing_url}")
                return None

            # Get the first XML file (usually the Form 4)
            # Filter out any XSL transformation files
            xml_links = [link for link in xml_links if 'xsl' not in link.lower()]

            if not xml_links:
                logger.error(f"No non-XSL XML file found in index page {filing_url}")
                return None

            xml_filename = xml_links[0]

            # Construct full URL
            base_url = filing_url.rsplit('/', 1)[0]
            xml_url = f"{base_url}/{xml_filename}" if not xml_filename.startswith('http') else xml_filename

            # If relative path, make it absolute
            if xml_filename.startswith('/'):
                xml_url = f"https://www.sec.gov{xml_filename}"
            elif not xml_filename.startswith('http'):
                xml_url = f"{base_url}/{xml_filename}"
            else:
                xml_url = xml_filename

            logger.debug(f"Found XML file: {xml_url}")
            filing_url = xml_url

        # Now fetch the actual XML
        response = self._make_request(filing_url)
        if not response:
            logger.error(f"Failed to download Form 4 XML from {filing_url}")
            return None

        # SEC sometimes wraps XML in SGML format, extract XML portion
        content = response.text

        # Look for <XML> tags (SGML wrapper)
        xml_start = content.find('<XML>')
        xml_end = content.find('</XML>')

        if xml_start != -1 and xml_end != -1:
            xml_content = content[xml_start + 5:xml_end].strip()
        else:
            # No SGML wrapper, treat entire content as XML
            xml_content = content

        # Cache XML content
        self._save_cache(cache_key, xml_content)

        return xml_content
