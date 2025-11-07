"""
Signal Filters

Multi-stage filtering to identify high-conviction insider trading signals.
Filters: purchases only → $100K+ → executive weight > 0 → market cap %
"""

import yaml
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.database.connection import get_session
from src.processors.executive_classifier import ExecutiveClassifier


class SignalFilters:
    """Apply multi-stage filters to identify high-conviction signals."""

    def __init__(self, config_path: str = 'config.yaml'):
        """
        Initialize filters with configuration.

        Args:
            config_path: Path to configuration file
        """
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        self.min_trade_value = config['filtering']['min_trade_value']
        self.min_market_cap_pct = config['filtering']['min_market_cap_pct']
        self.max_market_cap_billions = config['filtering'].get('max_market_cap_billions')

        self.executive_classifier = ExecutiveClassifier(config_path)

    def load_transactions(self, session: Optional[Session] = None) -> List[Dict[str, Any]]:
        """
        Load all transactions from database with JOINs.

        Args:
            session: Optional database session (will create one if not provided)

        Returns:
            List of transaction dictionaries with all needed fields
        """
        # Create session if not provided
        close_session = False
        if session is None:
            session = get_session()
            close_session = True

        try:
            # SQL query with all JOINs
            query = text("""
                SELECT
                    it.id,
                    it.trade_date,
                    it.filing_date,
                    it.transaction_code,
                    it.shares,
                    it.price_per_share,
                    it.total_value,
                    c.ticker,
                    c.name as company_name,
                    i.name as insider_name,
                    i.officer_title,
                    mc.market_cap_usd
                FROM insider_transactions it
                JOIN companies c ON it.company_id = c.id
                JOIN insiders i ON it.insider_id = i.id
                LEFT JOIN market_caps mc ON (
                    mc.company_id = c.id
                    AND DATE(mc.date) = DATE(it.filing_date)
                )
                ORDER BY it.filing_date DESC
            """)

            result = session.execute(query)
            rows = result.fetchall()

            # Convert to list of dicts
            transactions = []
            for row in rows:
                transactions.append({
                    'id': row.id,
                    'trade_date': row.trade_date,
                    'filing_date': row.filing_date,
                    'transaction_code': row.transaction_code,
                    'shares': row.shares,
                    'price_per_share': row.price_per_share,
                    'total_value': row.total_value,
                    'ticker': row.ticker,
                    'company_name': row.company_name,
                    'insider_name': row.insider_name,
                    'officer_title': row.officer_title,
                    'market_cap_usd': row.market_cap_usd
                })

            return transactions

        finally:
            if close_session:
                session.close()

    def apply_filters(self, transactions: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Apply multi-stage filters to transactions.

        Filter stages:
            1. Purchases only (transaction_code = 'P')
            2. Minimum trade value ($100K+)
            3. Executive weight > 0 (exclude non-executives)
            4. Trade/market_cap >= min threshold (if market cap available)

        Args:
            transactions: List of transaction dictionaries

        Returns:
            Tuple of (filtered_transactions, statistics)
        """
        stats = {
            'total_input': len(transactions),
            'stage_1_purchases': 0,
            'stage_2_min_value': 0,
            'stage_3_executive': 0,
            'stage_4_market_cap_pct': 0,
            'final_filtered': 0,
            'missing_market_cap': 0,
            'missing_total_value': 0
        }

        # Stage 1: Purchases only
        filtered = [t for t in transactions if t['transaction_code'] == 'P']
        stats['stage_1_purchases'] = len(filtered)

        # Stage 2: Minimum trade value
        # Filter out transactions with missing total_value
        filtered_with_value = [t for t in filtered if t['total_value'] is not None]
        stats['missing_total_value'] = len(filtered) - len(filtered_with_value)

        filtered = [t for t in filtered_with_value if t['total_value'] >= self.min_trade_value]
        stats['stage_2_min_value'] = len(filtered)

        # Stage 3: Executive weight > 0
        # Add executive weight to each transaction
        for t in filtered:
            t['executive_weight'] = self.executive_classifier.get_weight(t['officer_title'])

        filtered = [t for t in filtered if t['executive_weight'] > 0]
        stats['stage_3_executive'] = len(filtered)

        # Stage 4: Market cap percentage filter (if enabled and data available)
        if self.min_market_cap_pct > 0:
            # Count how many are missing market cap
            with_market_cap = [t for t in filtered if t['market_cap_usd'] is not None]
            stats['missing_market_cap'] = len(filtered) - len(with_market_cap)

            # Apply market cap percentage filter
            filtered_by_pct = []
            for t in with_market_cap:
                trade_pct = (t['total_value'] / t['market_cap_usd']) if t['market_cap_usd'] > 0 else 0
                t['trade_pct_of_market_cap'] = trade_pct

                if trade_pct >= self.min_market_cap_pct:
                    filtered_by_pct.append(t)

            # For transactions without market cap, include them but flag
            for t in filtered:
                if t['market_cap_usd'] is None:
                    t['trade_pct_of_market_cap'] = None
                    filtered_by_pct.append(t)  # Include but without market cap filter

            filtered = filtered_by_pct
            stats['stage_4_market_cap_pct'] = len(filtered)
        else:
            # Market cap filtering disabled
            for t in filtered:
                trade_pct = (t['total_value'] / t['market_cap_usd']) if (
                    t['market_cap_usd'] is not None and t['market_cap_usd'] > 0
                ) else None
                t['trade_pct_of_market_cap'] = trade_pct
            stats['stage_4_market_cap_pct'] = len(filtered)

        # Optional: Max market cap filter (exclude mega-caps)
        if self.max_market_cap_billions is not None:
            max_market_cap = self.max_market_cap_billions * 1_000_000_000  # Convert to USD
            filtered = [
                t for t in filtered
                if t['market_cap_usd'] is None or t['market_cap_usd'] <= max_market_cap
            ]

        stats['final_filtered'] = len(filtered)

        return filtered, stats

    def filter_transactions(
        self,
        session: Optional[Session] = None
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Load and filter transactions in one call.

        Args:
            session: Optional database session

        Returns:
            Tuple of (filtered_transactions, statistics)
        """
        transactions = self.load_transactions(session)
        return self.apply_filters(transactions)


# Convenience function
def filter_signals(config_path: str = 'config.yaml') -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Quick function to filter signals without creating filter instance.

    Args:
        config_path: Path to configuration file

    Returns:
        Tuple of (filtered_transactions, statistics)
    """
    filters = SignalFilters(config_path)
    return filters.filter_transactions()
