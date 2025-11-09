"""Company-related API endpoints."""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ...database.connection import get_session
from ...database.schema import Company, Insider, InsiderTransaction, InsiderPerformance, TransactionCode

router = APIRouter()


# Response models
class InsiderSummary(BaseModel):
    """Insider summary for company view."""
    id: int
    name: str
    title: Optional[str]
    total_buys: int
    total_sells: int
    win_rate_3m: Optional[float]
    avg_return: Optional[float]
    alpha_vs_spy: Optional[float]
    latest_trade_date: Optional[datetime]
    latest_filing_date: Optional[datetime]
    latest_trade_value: Optional[float]
    latest_trade_type: str

    class Config:
        from_attributes = True


class CompanyDeepDive(BaseModel):
    """Company deep dive response."""
    ticker: str
    name: str
    total_insiders: int
    total_transactions: int
    recent_buy_value: float
    recent_sell_value: float
    insiders: List[InsiderSummary]

    class Config:
        from_attributes = True


@router.get("/{ticker}", response_model=CompanyDeepDive)
async def get_company_deep_dive(ticker: str):
    """
    Get company deep dive data including insider performance table.

    Args:
        ticker: Company ticker symbol (e.g., 'AAPL')

    Returns:
        CompanyDeepDive with insiders ranked by win rate
    """
    session = get_session()

    try:
        # Get company
        company = session.query(Company).filter(
            Company.ticker == ticker.upper()
        ).first()

        if not company:
            raise HTTPException(status_code=404, detail=f"Company {ticker} not found")

        # Get all insiders for this company
        insiders = session.query(Insider).filter(
            Insider.company_id == company.id
        ).all()

        if not insiders:
            raise HTTPException(status_code=404, detail=f"No insider data for {ticker}")

        # Build insider summaries
        insider_summaries = []
        for insider in insiders:
            # Get transaction counts
            buys = session.query(InsiderTransaction).filter(
                InsiderTransaction.insider_id == insider.id,
                InsiderTransaction.transaction_code == TransactionCode.P
            ).count()

            sells = session.query(InsiderTransaction).filter(
                InsiderTransaction.insider_id == insider.id,
                InsiderTransaction.transaction_code == TransactionCode.S
            ).count()

            # Get performance metrics
            perf = session.query(InsiderPerformance).filter(
                InsiderPerformance.insider_id == insider.id
            ).first()

            # Get latest transaction (order by filing_date to get most recent)
            latest_txn = session.query(InsiderTransaction).filter(
                InsiderTransaction.insider_id == insider.id
            ).order_by(InsiderTransaction.filing_date.desc()).first()

            insider_summaries.append(InsiderSummary(
                id=insider.id,
                name=insider.name,
                title=insider.title,
                total_buys=buys,
                total_sells=sells,
                win_rate_3m=perf.win_rate_3m if perf else None,
                avg_return=perf.avg_return if perf else None,
                alpha_vs_spy=perf.alpha_vs_spy if perf else None,
                latest_trade_date=latest_txn.trade_date if latest_txn else None,
                latest_filing_date=latest_txn.filing_date if latest_txn else None,
                latest_trade_value=latest_txn.total_value if latest_txn else None,
                latest_trade_type=latest_txn.transaction_code.value if latest_txn else "N/A"
            ))

        # Sort by win rate (nulls last)
        insider_summaries.sort(
            key=lambda x: (x.win_rate_3m is None, -(x.win_rate_3m or 0))
        )

        # Calculate recent activity (last 90 days)
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=90)

        recent_buys = session.query(InsiderTransaction).filter(
            InsiderTransaction.company_id == company.id,
            InsiderTransaction.transaction_code == TransactionCode.P,
            InsiderTransaction.trade_date >= cutoff,
            InsiderTransaction.total_value.isnot(None)
        ).all()

        recent_sells = session.query(InsiderTransaction).filter(
            InsiderTransaction.company_id == company.id,
            InsiderTransaction.transaction_code == TransactionCode.S,
            InsiderTransaction.trade_date >= cutoff,
            InsiderTransaction.total_value.isnot(None)
        ).all()

        buy_value = sum(t.total_value for t in recent_buys)
        sell_value = sum(t.total_value for t in recent_sells)

        return CompanyDeepDive(
            ticker=company.ticker,
            name=company.name,
            total_insiders=len(insiders),
            total_transactions=len(insiders),
            recent_buy_value=buy_value,
            recent_sell_value=sell_value,
            insiders=insider_summaries
        )

    finally:
        session.close()


@router.get("/{ticker}/insider/{insider_id}/history")
async def get_insider_history(ticker: str, insider_id: int):
    """
    Get trade history timeline for a specific insider.

    Args:
        ticker: Company ticker
        insider_id: Insider ID

    Returns:
        List of transactions with details
    """
    session = get_session()

    try:
        # Verify insider belongs to company
        insider = session.query(Insider).filter(
            Insider.id == insider_id
        ).first()

        if not insider or insider.company.ticker != ticker.upper():
            raise HTTPException(status_code=404, detail="Insider not found")

        # Get all transactions
        transactions = session.query(InsiderTransaction).filter(
            InsiderTransaction.insider_id == insider_id
        ).order_by(InsiderTransaction.trade_date.desc()).all()

        return {
            "insider_name": insider.name,
            "insider_title": insider.title,
            "total_transactions": len(transactions),
            "transactions": [
                {
                    "id": txn.id,
                    "trade_date": txn.trade_date,
                    "filing_date": txn.filing_date,
                    "transaction_code": txn.transaction_code.value,
                    "shares": txn.shares,
                    "price_per_share": txn.price_per_share,
                    "total_value": txn.total_value
                }
                for txn in transactions
            ]
        }

    finally:
        session.close()
