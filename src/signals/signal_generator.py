"""
Signal Generator - Combine conviction and track record scores to generate signals

Generates Signal records with threshold categories:
- Score <3: IGNORE
- Score 3-4: WEAK
- Score 5-6: WATCH
- Score ≥7: STRONG_BUY (triggers email alert)
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..database.schema import (
    InsiderTransaction, Signal, ThresholdCategory, TransactionCode
)
from .conviction_scorer import ConvictionScorer
from .track_record_scorer import TrackRecordScorer


class SignalGenerator:
    """Generate scored signals from insider transactions."""

    @classmethod
    def generate_signals(
        cls,
        session: Session,
        transaction_ids: Optional[List[int]] = None,
        min_value: float = 50_000,
        holding_period: str = '3m'
    ) -> List[Signal]:
        """
        Generate signals for transactions.

        Args:
            session: Database session
            transaction_ids: List of specific transaction IDs to score (None = all unscored)
            min_value: Minimum transaction value to consider (default: $50K)
            holding_period: Holding period for track record scoring (default: 3m)

        Returns:
            List of created Signal objects
        """
        # Get transactions to score
        query = session.query(InsiderTransaction).filter(
            InsiderTransaction.transaction_code == TransactionCode.P,  # Buys only
        )

        # Filter by minimum value
        if min_value > 0:
            query = query.filter(
                InsiderTransaction.total_value >= min_value
            )

        # Filter by specific IDs or get unscored transactions
        if transaction_ids:
            query = query.filter(InsiderTransaction.id.in_(transaction_ids))
        else:
            # Get transactions that don't have signals yet
            existing_signal_txn_ids = session.query(Signal.transaction_id).all()
            existing_ids = [s[0] for s in existing_signal_txn_ids]
            if existing_ids:
                query = query.filter(~InsiderTransaction.id.in_(existing_ids))

        transactions = query.all()

        if not transactions:
            return []

        # Generate signals
        signals = []
        for txn in transactions:
            signal = cls._score_and_create_signal(txn, session, holding_period)
            if signal:
                signals.append(signal)

        # Commit signals to database
        session.add_all(signals)
        session.commit()

        return signals

    @classmethod
    def _score_and_create_signal(
        cls,
        transaction: InsiderTransaction,
        session: Session,
        holding_period: str
    ) -> Optional[Signal]:
        """
        Score a transaction and create a Signal record.

        Args:
            transaction: InsiderTransaction to score
            session: Database session
            holding_period: Holding period for track record

        Returns:
            Signal object or None if scoring fails
        """
        try:
            # Calculate scores
            conviction = ConvictionScorer.score_transaction(transaction, session)
            track_record = TrackRecordScorer.score_transaction(
                transaction, session, holding_period
            )
            total = conviction + track_record

            # Determine threshold category
            category = cls._categorize_score(total)

            # Create signal
            signal = Signal(
                transaction_id=transaction.id,
                conviction_score=conviction,
                track_record_score=track_record,
                total_score=total,
                threshold_category=category,
                alert_sent=False
            )

            return signal

        except Exception as e:
            print(f"Error scoring transaction {transaction.id}: {e}")
            return None

    @classmethod
    def _categorize_score(cls, score: int) -> ThresholdCategory:
        """
        Map total score to threshold category.

        Args:
            score: Total score (0-8)

        Returns:
            ThresholdCategory enum
        """
        if score >= 7:
            return ThresholdCategory.STRONG_BUY
        elif score >= 5:
            return ThresholdCategory.WATCH
        elif score >= 3:
            return ThresholdCategory.WEAK
        else:
            return ThresholdCategory.IGNORE

    @classmethod
    def get_strong_signals(
        cls,
        session: Session,
        unsent_only: bool = True
    ) -> List[Signal]:
        """
        Get strong buy signals (score ≥7) for email alerts.

        Args:
            session: Database session
            unsent_only: Only return signals where alert hasn't been sent

        Returns:
            List of Signal objects with category STRONG_BUY
        """
        query = session.query(Signal).filter(
            Signal.threshold_category == ThresholdCategory.STRONG_BUY
        )

        if unsent_only:
            query = query.filter(Signal.alert_sent == False)

        return query.order_by(Signal.created_at.desc()).all()

    @classmethod
    def mark_alert_sent(cls, signal: Signal, session: Session) -> None:
        """
        Mark a signal's alert as sent.

        Args:
            signal: Signal to update
            session: Database session
        """
        signal.alert_sent = True
        signal.alert_sent_at = datetime.utcnow()
        session.commit()
