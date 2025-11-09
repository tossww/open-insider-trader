"""Signal-related API endpoints."""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ...database.connection import get_session
from ...database.schema import Signal, InsiderTransaction, ThresholdCategory

router = APIRouter()


# Response models
class SignalDetail(BaseModel):
    """Detailed signal information."""
    id: int
    ticker: str
    company_name: str
    insider_name: str
    insider_title: Optional[str]
    trade_date: datetime
    total_value: Optional[float]
    conviction_score: int
    track_record_score: int
    total_score: int
    threshold_category: str
    alert_sent: bool

    class Config:
        from_attributes = True


@router.get("/strong-buys", response_model=List[SignalDetail])
async def get_strong_buy_signals(
    unsent_only: bool = Query(False, description="Only return unsent alerts"),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get strong buy signals (score ≥7) for email alerts.

    Args:
        unsent_only: Only return signals where alert hasn't been sent
        limit: Max number of results

    Returns:
        List of strong buy signals
    """
    session = get_session()

    try:
        query = session.query(Signal).filter(
            Signal.threshold_category == ThresholdCategory.STRONG_BUY
        )

        if unsent_only:
            query = query.filter(Signal.alert_sent == False)

        query = query.order_by(Signal.created_at.desc()).limit(limit)

        signals = query.all()

        # Build response
        signal_details = []
        for sig in signals:
            txn = sig.transaction
            signal_details.append(SignalDetail(
                id=sig.id,
                ticker=txn.company.ticker,
                company_name=txn.company.name,
                insider_name=txn.insider.name,
                insider_title=txn.insider.title,
                trade_date=txn.trade_date,
                total_value=txn.total_value,
                conviction_score=sig.conviction_score,
                track_record_score=sig.track_record_score,
                total_score=sig.total_score,
                threshold_category=sig.threshold_category.value,
                alert_sent=sig.alert_sent
            ))

        return signal_details

    finally:
        session.close()


@router.post("/{signal_id}/mark-sent")
async def mark_signal_sent(signal_id: int):
    """
    Mark a signal's alert as sent.

    Args:
        signal_id: Signal ID

    Returns:
        Updated signal status
    """
    session = get_session()

    try:
        signal = session.query(Signal).filter(Signal.id == signal_id).first()

        if not signal:
            raise HTTPException(status_code=404, detail="Signal not found")

        signal.alert_sent = True
        signal.alert_sent_at = datetime.utcnow()
        session.commit()

        return {
            "signal_id": signal_id,
            "alert_sent": True,
            "alert_sent_at": signal.alert_sent_at
        }

    finally:
        session.close()
