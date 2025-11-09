"""
Insider Performance Calculator

Calculates historical performance metrics for individual insiders.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
from sqlalchemy.orm import Session

from ..database.schema import (
    Insider, InsiderTransaction, InsiderPerformance,
    TransactionCode, Company
)
from .backtest_engine import BacktestEngine, Signal
from .price_data import PriceDataFetcher

logger = logging.getLogger(__name__)


def calculate_insider_performance(
    insider_id: int,
    session: Session,
    holding_periods: List[int] = [5, 21, 63, 126]  # 1w, 1m, 3m, 6m trading days
) -> Optional[Dict]:
    """
    Calculate performance metrics for an insider.

    Args:
        insider_id: Insider ID to analyze
        session: SQLAlchemy session
        holding_periods: List of holding periods in trading days

    Returns:
        Dictionary with performance metrics or None if insufficient data
    """
    # Fetch insider and their buy transactions
    insider = session.query(Insider).filter_by(id=insider_id).first()
    if not insider:
        logger.error(f"Insider {insider_id} not found")
        return None

    # Get all buy transactions
    buy_transactions = session.query(InsiderTransaction).filter_by(
        insider_id=insider_id,
        transaction_code=TransactionCode.P
    ).all()

    if not buy_transactions:
        logger.warning(f"No buy transactions found for insider {insider_id}")
        return None

    # Convert to Signal objects for backtest engine
    signals = []
    for txn in buy_transactions:
        signal = Signal(
            ticker=txn.company.ticker,
            filing_date=txn.filing_date,
            trade_date=txn.trade_date,
            insider_name=insider.name,
            officer_title=insider.title or "Unknown",
            total_value=txn.total_value or 0,
            composite_score=0,  # Not used for performance calc
            cluster_size=1
        )
        signals.append(signal)

    logger.info(f"Calculating performance for {insider.name} ({len(signals)} trades)")

    # Initialize backtest engine
    engine = BacktestEngine()

    # Run backtests for each holding period
    results = {}
    for holding_days in holding_periods:
        try:
            result = engine.backtest_signals(signals, holding_days)

            # Map holding days to period names
            period_map = {
                5: '1w',
                21: '1m',
                63: '3m',
                126: '6m'
            }
            period_name = period_map.get(holding_days, f'{holding_days}d')

            results[period_name] = {
                'win_rate': result.win_rate,
                'avg_return': result.avg_net_return,
                'alpha': result.alpha,
                'total_trades': result.total_trades
            }

            logger.info(f"  {period_name}: {result.win_rate:.1%} win rate, "
                       f"{result.avg_net_return:+.2%} avg return, "
                       f"{result.alpha:+.2%} alpha" if result.alpha else "N/A")

        except Exception as e:
            logger.error(f"Failed to backtest {holding_days}d period: {e}")
            continue

    if not results:
        logger.warning(f"No valid backtest results for insider {insider_id}")
        return None

    # Calculate aggregate metrics
    # Use 3-month as default for overall metrics
    primary_period = results.get('3m', results.get('1m', results.get('6m')))

    metrics = {
        'win_rate_1w': results.get('1w', {}).get('win_rate'),
        'win_rate_1m': results.get('1m', {}).get('win_rate'),
        'win_rate_3m': results.get('3m', {}).get('win_rate'),
        'win_rate_6m': results.get('6m', {}).get('win_rate'),
        'avg_return': primary_period.get('avg_return') if primary_period else None,
        'alpha_vs_spy': primary_period.get('alpha') if primary_period else None,
        'total_buys': len([t for t in buy_transactions if t.transaction_code == TransactionCode.P]),
        'total_sells': len([t for t in session.query(InsiderTransaction).filter_by(
            insider_id=insider_id,
            transaction_code=TransactionCode.S
        ).all()])
    }

    return metrics


def update_insider_performance(
    insider_id: int,
    session: Session,
    force_recalc: bool = False
) -> bool:
    """
    Calculate and update insider performance in database.

    Args:
        insider_id: Insider ID to update
        session: SQLAlchemy session
        force_recalc: Force recalculation even if recently updated

    Returns:
        True if updated successfully
    """
    # Check if we need to recalculate
    perf = session.query(InsiderPerformance).filter_by(insider_id=insider_id).first()

    if perf and not force_recalc:
        # Only recalculate if older than 7 days
        if perf.last_calculated_at:
            age = datetime.utcnow() - perf.last_calculated_at
            if age.days < 7:
                logger.debug(f"Performance for insider {insider_id} is recent, skipping")
                return True

    # Calculate metrics
    metrics = calculate_insider_performance(insider_id, session)
    if not metrics:
        return False

    # Get insider to get company_id
    insider = session.query(Insider).filter_by(id=insider_id).first()
    if not insider:
        return False

    # Update or create performance record
    if perf:
        for key, value in metrics.items():
            setattr(perf, key, value)
        perf.last_calculated_at = datetime.utcnow()
    else:
        perf = InsiderPerformance(
            insider_id=insider_id,
            company_id=insider.company_id,
            last_calculated_at=datetime.utcnow(),
            **metrics
        )
        session.add(perf)

    try:
        session.commit()
        logger.info(f"Updated performance for insider {insider_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to update performance: {e}")
        session.rollback()
        return False


def update_all_insider_performance(
    session: Session,
    min_trades: int = 3,
    force_recalc: bool = False
) -> int:
    """
    Update performance metrics for all insiders with sufficient trades.

    Args:
        session: SQLAlchemy session
        min_trades: Minimum number of buy transactions required
        force_recalc: Force recalculation for all insiders

    Returns:
        Number of insiders updated
    """
    # Find insiders with enough trades
    insiders_with_trades = session.query(
        Insider.id,
        Insider.name,
        session.query(InsiderTransaction).filter_by(
            insider_id=Insider.id,
            transaction_code=TransactionCode.P
        ).count().label('trade_count')
    ).having(
        session.query(InsiderTransaction).filter_by(
            insider_id=Insider.id,
            transaction_code=TransactionCode.P
        ).count() >= min_trades
    ).all()

    logger.info(f"Found {len(insiders_with_trades)} insiders with ≥{min_trades} trades")

    updated_count = 0
    for insider_id, name, trade_count in insiders_with_trades:
        logger.info(f"Processing {name} ({trade_count} trades)")
        if update_insider_performance(insider_id, session, force_recalc):
            updated_count += 1

    logger.info(f"Updated performance for {updated_count} insiders")
    return updated_count
