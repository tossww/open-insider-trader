"""
Conviction Scorer - Calculate conviction score (0-3 points) for insider transactions

Scoring criteria:
- Trade value >$1M: +1 point
- Multiple buys within 30 days: +1 point
- C-Suite executive: +1 point
"""

from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from ..database.schema import InsiderTransaction, Insider, TransactionCode


class ConvictionScorer:
    """Calculate conviction score based on trade characteristics."""

    # C-Suite titles to look for
    C_SUITE_KEYWORDS = [
        'ceo', 'chief executive',
        'cfo', 'chief financial',
        'coo', 'chief operating',
        'cto', 'chief technology',
        'president', 'pres',
        'chairman', 'chair'
    ]

    @classmethod
    def score_transaction(
        cls,
        transaction: InsiderTransaction,
        session: Session
    ) -> int:
        """
        Calculate conviction score for a single transaction.

        Args:
            transaction: InsiderTransaction to score
            session: SQLAlchemy session for database queries

        Returns:
            int: Conviction score (0-3)
        """
        score = 0

        # Criterion 1: Trade value >$1M (+1 point)
        if transaction.total_value and transaction.total_value > 1_000_000:
            score += 1

        # Criterion 2: Multiple buys within 30 days (+1 point)
        if cls._has_clustered_buys(transaction, session):
            score += 1

        # Criterion 3: C-Suite executive (+1 point)
        if cls._is_c_suite(transaction.insider):
            score += 1

        return score

    @classmethod
    def _has_clustered_buys(
        cls,
        transaction: InsiderTransaction,
        session: Session,
        window_days: int = 30
    ) -> bool:
        """
        Check if insider has multiple buy transactions within window_days.

        Args:
            transaction: Current transaction
            session: Database session
            window_days: Time window to check for clustering (default: 30 days)

        Returns:
            bool: True if ≥2 buys within window (including current transaction)
        """
        # Get date range
        trade_date = transaction.trade_date
        start_date = trade_date - timedelta(days=window_days)
        end_date = trade_date + timedelta(days=window_days)

        # Query for buy transactions by same insider within window
        buy_count = session.query(InsiderTransaction).filter(
            InsiderTransaction.insider_id == transaction.insider_id,
            InsiderTransaction.transaction_code == TransactionCode.P,
            InsiderTransaction.trade_date >= start_date,
            InsiderTransaction.trade_date <= end_date
        ).count()

        # Need at least 2 buys (including current)
        return buy_count >= 2

    @classmethod
    def _is_c_suite(cls, insider: Insider) -> bool:
        """
        Check if insider holds a C-Suite position.

        Args:
            insider: Insider object with title

        Returns:
            bool: True if C-Suite executive
        """
        if not insider.title:
            return False

        # Normalize title to lowercase for matching
        title_lower = insider.title.lower()

        # Check for C-Suite keywords
        return any(keyword in title_lower for keyword in cls.C_SUITE_KEYWORDS)

    @classmethod
    def score_batch(
        cls,
        transactions: List[InsiderTransaction],
        session: Session
    ) -> dict[int, int]:
        """
        Score multiple transactions efficiently.

        Args:
            transactions: List of transactions to score
            session: Database session

        Returns:
            dict: Mapping of transaction_id -> conviction_score
        """
        scores = {}
        for transaction in transactions:
            scores[transaction.id] = cls.score_transaction(transaction, session)
        return scores
