"""
Track Record Scorer - Calculate track record score (0-5 points) for insider transactions

Scoring criteria based on insider's historical performance:
- Win Rate: >70% (+3), 60-70% (+2), 50-60% (+1), <50% (0)
- Alpha vs SPY: >10% (+2), 5-10% (+1), <5% (0)

If insider has no historical data, use company-wide insider average.
"""

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database.schema import InsiderTransaction, InsiderPerformance, Insider


class TrackRecordScorer:
    """Calculate track record score based on historical performance."""

    @classmethod
    def score_transaction(
        cls,
        transaction: InsiderTransaction,
        session: Session,
        holding_period: str = '3m'
    ) -> int:
        """
        Calculate track record score for a transaction.

        Args:
            transaction: InsiderTransaction to score
            session: SQLAlchemy session for database queries
            holding_period: Which holding period to use ('1w', '1m', '3m', '6m')

        Returns:
            int: Track record score (0-5)
        """
        # Get insider's performance metrics
        performance = cls._get_performance_metrics(
            transaction.insider_id,
            transaction.company_id,
            session,
            holding_period
        )

        if not performance:
            # No data available - use default (no track record)
            return 0

        win_rate, alpha = performance

        # Calculate score components
        win_rate_score = cls._score_win_rate(win_rate)
        alpha_score = cls._score_alpha(alpha)

        return win_rate_score + alpha_score

    @classmethod
    def _get_performance_metrics(
        cls,
        insider_id: int,
        company_id: int,
        session: Session,
        holding_period: str
    ) -> Optional[tuple[float, float]]:
        """
        Get win rate and alpha for an insider, falling back to company average.

        Args:
            insider_id: Insider's ID
            company_id: Company's ID (for fallback)
            session: Database session
            holding_period: '1w', '1m', '3m', or '6m'

        Returns:
            tuple: (win_rate, alpha) or None if no data available
        """
        # Try to get insider's own performance
        perf = session.query(InsiderPerformance).filter(
            InsiderPerformance.insider_id == insider_id
        ).first()

        # Select the correct win rate column
        win_rate_col = f'win_rate_{holding_period}'

        if perf and hasattr(perf, win_rate_col):
            win_rate = getattr(perf, win_rate_col)
            alpha = perf.alpha_vs_spy

            # If insider has data, use it
            if win_rate is not None and alpha is not None:
                return (win_rate, alpha)

        # Fallback: Calculate company-wide insider average
        return cls._get_company_average(company_id, session, holding_period)

    @classmethod
    def _get_company_average(
        cls,
        company_id: int,
        session: Session,
        holding_period: str
    ) -> Optional[tuple[float, float]]:
        """
        Calculate average win rate and alpha for all insiders at a company.

        Args:
            company_id: Company's ID
            session: Database session
            holding_period: '1w', '1m', '3m', or '6m'

        Returns:
            tuple: (avg_win_rate, avg_alpha) or None
        """
        win_rate_col = f'win_rate_{holding_period}'

        # Get all insiders for this company
        insider_ids = session.query(Insider.id).filter(
            Insider.company_id == company_id
        ).all()

        if not insider_ids:
            return None

        insider_ids = [i[0] for i in insider_ids]

        # Calculate averages across company insiders
        result = session.query(
            func.avg(getattr(InsiderPerformance, win_rate_col)).label('avg_win_rate'),
            func.avg(InsiderPerformance.alpha_vs_spy).label('avg_alpha')
        ).filter(
            InsiderPerformance.insider_id.in_(insider_ids),
            getattr(InsiderPerformance, win_rate_col).isnot(None),
            InsiderPerformance.alpha_vs_spy.isnot(None)
        ).first()

        if result and result.avg_win_rate is not None:
            return (result.avg_win_rate, result.avg_alpha or 0.0)

        return None

    @classmethod
    def _score_win_rate(cls, win_rate: float) -> int:
        """
        Score win rate (0-3 points).

        Args:
            win_rate: Win rate as decimal (0.0 to 1.0)

        Returns:
            int: 0-3 points
        """
        if win_rate > 0.70:
            return 3
        elif win_rate > 0.60:
            return 2
        elif win_rate > 0.50:
            return 1
        else:
            return 0

    @classmethod
    def _score_alpha(cls, alpha: float) -> int:
        """
        Score alpha vs SPY (0-2 points).

        Args:
            alpha: Alpha as decimal (e.g., 0.10 = 10%)

        Returns:
            int: 0-2 points
        """
        if alpha > 0.10:
            return 2
        elif alpha > 0.05:
            return 1
        else:
            return 0
