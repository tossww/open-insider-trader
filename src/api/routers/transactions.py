"""Transaction feed API endpoints."""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ...database.connection import get_session
from ...database.schema import (
    InsiderTransaction, Company, Insider, Signal, TransactionCode, ThresholdCategory
)

router = APIRouter()


# Response models
class TransactionFeedItem(BaseModel):
    """Single transaction in the feed."""
    id: int
    ticker: str
    company_name: str
    insider_name: str
    insider_title: Optional[str]
    trade_date: datetime
    filing_date: datetime
    transaction_code: str
    shares: float
    price_per_share: Optional[float]
    total_value: Optional[float]
    signal_score: Optional[int]
    threshold_category: Optional[str]

    class Config:
        from_attributes = True


@router.get("/feed", response_model=List[TransactionFeedItem])
async def get_transaction_feed(
    min_score: Optional[int] = Query(None, ge=0, le=8, description="Minimum signal score"),
    min_value: Optional[float] = Query(None, ge=0, description="Minimum trade value"),
    limit: int = Query(50, ge=1, le=500, description="Number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    """
    Get transaction feed with optional filters.

    Args:
        min_score: Minimum signal score (0-8)
        min_value: Minimum trade value in dollars
        limit: Max number of results
        offset: Pagination offset

    Returns:
        List of recent buy transactions with signal scores
    """
    session = get_session()

    try:
        # Base query: buy transactions only
        query = session.query(
            InsiderTransaction,
            Signal.total_score,
            Signal.threshold_category
        ).outerjoin(
            Signal, Signal.transaction_id == InsiderTransaction.id
        ).filter(
            InsiderTransaction.transaction_code == TransactionCode.P
        )

        # Apply filters
        if min_score is not None:
            query = query.filter(Signal.total_score >= min_score)

        if min_value is not None:
            query = query.filter(InsiderTransaction.total_value >= min_value)

        # Order by most recent
        query = query.order_by(InsiderTransaction.trade_date.desc())

        # Pagination
        query = query.offset(offset).limit(limit)

        results = query.all()

        # Build response
        feed_items = []
        for txn, score, category in results:
            feed_items.append(TransactionFeedItem(
                id=txn.id,
                ticker=txn.company.ticker,
                company_name=txn.company.name,
                insider_name=txn.insider.name,
                insider_title=txn.insider.title,
                trade_date=txn.trade_date,
                filing_date=txn.filing_date,
                transaction_code=txn.transaction_code.value,
                shares=txn.shares,
                price_per_share=txn.price_per_share,
                total_value=txn.total_value,
                signal_score=score,
                threshold_category=category.value if category else None
            ))

        return feed_items

    finally:
        session.close()


@router.get("/stats")
async def get_transaction_stats():
    """Get overall transaction statistics."""
    session = get_session()

    try:
        from sqlalchemy import func
        from datetime import timedelta

        # Total counts
        total_buys = session.query(InsiderTransaction).filter(
            InsiderTransaction.transaction_code == TransactionCode.P
        ).count()

        total_sells = session.query(InsiderTransaction).filter(
            InsiderTransaction.transaction_code == TransactionCode.S
        ).count()

        # Recent activity (last 30 days)
        cutoff = datetime.utcnow() - timedelta(days=30)

        recent_buys = session.query(InsiderTransaction).filter(
            InsiderTransaction.transaction_code == TransactionCode.P,
            InsiderTransaction.trade_date >= cutoff
        ).count()

        # Signal stats
        signal_counts = session.query(
            Signal.threshold_category,
            func.count(Signal.id)
        ).group_by(Signal.threshold_category).all()

        category_counts = {cat.value: count for cat, count in signal_counts}

        # Total value
        total_buy_value = session.query(
            func.sum(InsiderTransaction.total_value)
        ).filter(
            InsiderTransaction.transaction_code == TransactionCode.P,
            InsiderTransaction.total_value.isnot(None)
        ).scalar() or 0

        return {
            "total_buys": total_buys,
            "total_sells": total_sells,
            "recent_buys_30d": recent_buys,
            "total_buy_value": total_buy_value,
            "signal_distribution": category_counts
        }

    finally:
        session.close()
