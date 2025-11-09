"""
Database schema for Open Insider Trader

SQLAlchemy ORM models for storing insider trading data from OpenInsider.com
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Index,
    UniqueConstraint, CheckConstraint, Enum
)
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


class TransactionSource(enum.Enum):
    """Source of transaction data."""
    OPENINSIDER = "openinsider"
    SEC = "sec"


class TransactionCode(enum.Enum):
    """Transaction type codes."""
    P = "P"  # Purchase
    S = "S"  # Sale
    M = "M"  # Option Exercise
    A = "A"  # Award
    D = "D"  # Disposition


class ThresholdCategory(enum.Enum):
    """Signal threshold categories."""
    IGNORE = "ignore"        # Score <3
    WEAK = "weak"            # Score 3-4
    WATCH = "watch"          # Score 5-6
    STRONG_BUY = "strong_buy"  # Score ≥7


class Company(Base):
    """Company information (issuers)."""

    __tablename__ = 'companies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    cik = Column(String(10), nullable=True, index=True)  # Optional for OpenInsider data
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    insiders = relationship('Insider', back_populates='company')
    transactions = relationship('InsiderTransaction', back_populates='company')

    def __repr__(self):
        return f"<Company(ticker='{self.ticker}', name='{self.name}')>"


class Insider(Base):
    """Insider (reporting owner) information."""

    __tablename__ = 'insiders'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)

    # Title/relationship to company
    title = Column(String(200), nullable=True)
    is_director = Column(Boolean, default=False)
    is_officer = Column(Boolean, default=False)
    is_ten_percent_owner = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    company = relationship('Company', back_populates='insiders')
    transactions = relationship('InsiderTransaction', back_populates='insider')
    performance = relationship('InsiderPerformance', back_populates='insider', uselist=False)

    # Unique constraint: one insider per company by name
    __table_args__ = (
        UniqueConstraint('name', 'company_id', name='uix_insider_name_company'),
        Index('ix_insider_company', 'company_id'),
    )

    def __repr__(self):
        return f"<Insider(name='{self.name}', title='{self.title}')>"


class InsiderTransaction(Base):
    """Individual insider transaction."""

    __tablename__ = 'insider_transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    insider_id = Column(Integer, ForeignKey('insiders.id'), nullable=False)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)

    # Transaction details
    trade_date = Column(DateTime, nullable=False, index=True)
    filing_date = Column(DateTime, nullable=False, index=True)
    transaction_code = Column(Enum(TransactionCode), nullable=False)

    # Amounts
    shares = Column(Float, nullable=False)
    price_per_share = Column(Float, nullable=True)
    total_value = Column(Float, nullable=True)

    # Source tracking
    source = Column(Enum(TransactionSource), nullable=False, default=TransactionSource.OPENINSIDER)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    insider = relationship('Insider', back_populates='transactions')
    company = relationship('Company', back_populates='transactions')
    signal = relationship('Signal', back_populates='transaction', uselist=False)

    # Indexes for common queries
    __table_args__ = (
        Index('ix_transaction_dates', 'filing_date', 'trade_date'),
        Index('ix_transaction_company_date', 'company_id', 'filing_date'),
        Index('ix_transaction_insider_date', 'insider_id', 'trade_date'),
        Index('ix_transaction_code', 'transaction_code'),
        CheckConstraint('shares > 0', name='check_shares_positive'),
        # Prevent duplicate transactions
        UniqueConstraint('insider_id', 'company_id', 'trade_date', 'transaction_code', 'shares',
                        name='uix_transaction_unique'),
    )

    def __repr__(self):
        return (f"<InsiderTransaction(ticker={self.company.ticker if self.company else 'N/A'}, "
                f"code='{self.transaction_code.value}', shares={self.shares}, value={self.total_value})>")


class InsiderPerformance(Base):
    """Historical performance metrics for an insider."""

    __tablename__ = 'insider_performance'

    id = Column(Integer, primary_key=True, autoincrement=True)
    insider_id = Column(Integer, ForeignKey('insiders.id'), nullable=False, unique=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)

    # Win rates by holding period
    win_rate_1w = Column(Float, nullable=True)  # 1 week
    win_rate_1m = Column(Float, nullable=True)  # 1 month
    win_rate_3m = Column(Float, nullable=True)  # 3 months
    win_rate_6m = Column(Float, nullable=True)  # 6 months

    # Average returns
    avg_return = Column(Float, nullable=True)

    # Alpha vs SPY
    alpha_vs_spy = Column(Float, nullable=True)

    # Trade counts
    total_buys = Column(Integer, nullable=False, default=0)
    total_sells = Column(Integer, nullable=False, default=0)

    # Metadata
    last_calculated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    insider = relationship('Insider', back_populates='performance')

    # Indexes
    __table_args__ = (
        Index('ix_performance_win_rate', 'win_rate_3m'),
        Index('ix_performance_alpha', 'alpha_vs_spy'),
    )

    def __repr__(self):
        return (f"<InsiderPerformance(insider_id={self.insider_id}, "
                f"win_rate={self.win_rate_3m:.1%} if self.win_rate_3m else 'N/A', "
                f"alpha={self.alpha_vs_spy:.2%} if self.alpha_vs_spy else 'N/A')>")


class Signal(Base):
    """High-conviction signals after scoring."""

    __tablename__ = 'signals'

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(Integer, ForeignKey('insider_transactions.id'), nullable=False, unique=True)

    # Score components
    conviction_score = Column(Integer, nullable=False)  # 0-3
    track_record_score = Column(Integer, nullable=False)  # 0-5
    total_score = Column(Integer, nullable=False, index=True)  # 0-8

    # Threshold category
    threshold_category = Column(Enum(ThresholdCategory), nullable=False, index=True)

    # Alert tracking
    alert_sent = Column(Boolean, nullable=False, default=False)
    alert_sent_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    transaction = relationship('InsiderTransaction', back_populates='signal')

    # Indexes
    __table_args__ = (
        Index('ix_signal_score', 'total_score'),
        Index('ix_signal_category', 'threshold_category'),
        Index('ix_signal_alert', 'alert_sent', 'threshold_category'),
    )

    def __repr__(self):
        return (f"<Signal(score={self.total_score}, "
                f"category={self.threshold_category.value}, alert_sent={self.alert_sent})>")
