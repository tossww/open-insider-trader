"""
Database schema for Open InsiderTrader

SQLAlchemy ORM models for storing insider trading data.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Index,
    UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Company(Base):
    """Company information (issuers)."""

    __tablename__ = 'companies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    cik = Column(String(10), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    insiders = relationship('Insider', back_populates='company')
    transactions = relationship('InsiderTransaction', back_populates='company')
    market_caps = relationship('MarketCap', back_populates='company')

    def __repr__(self):
        return f"<Company(ticker='{self.ticker}', name='{self.name}')>"


class Insider(Base):
    """Insider (reporting owner) information."""

    __tablename__ = 'insiders'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, index=True)
    cik = Column(String(10), nullable=True, index=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)

    # Relationship to company
    is_director = Column(Boolean, default=False)
    is_officer = Column(Boolean, default=False)
    is_ten_percent_owner = Column(Boolean, default=False)
    officer_title = Column(String(200), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    company = relationship('Company', back_populates='insiders')
    transactions = relationship('InsiderTransaction', back_populates='insider')

    # Unique constraint: one insider per company (by name + CIK)
    __table_args__ = (
        UniqueConstraint('name', 'cik', 'company_id', name='uix_insider_name_cik_company'),
        Index('ix_insider_company', 'company_id'),
    )

    def __repr__(self):
        return f"<Insider(name='{self.name}', title='{self.officer_title}')>"


class RawForm4Filing(Base):
    """Raw Form 4 filing data (for audit trail)."""

    __tablename__ = 'raw_form4_filings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    filing_url = Column(String(500), nullable=False, unique=True)
    accession_number = Column(String(50), nullable=False, unique=True, index=True)
    filing_date = Column(DateTime, nullable=False, index=True)
    xml_content = Column(Text, nullable=False)
    is_amendment = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    transactions = relationship('InsiderTransaction', back_populates='form4_filing')

    def __repr__(self):
        return f"<RawForm4Filing(accession='{self.accession_number}', date='{self.filing_date}')>"


class InsiderTransaction(Base):
    """Individual insider transaction from Form 4."""

    __tablename__ = 'insider_transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    form4_filing_id = Column(Integer, ForeignKey('raw_form4_filings.id'), nullable=False)
    insider_id = Column(Integer, ForeignKey('insiders.id'), nullable=False)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)

    # Transaction details
    trade_date = Column(DateTime, nullable=False, index=True)
    filing_date = Column(DateTime, nullable=False, index=True)
    transaction_code = Column(String(5), nullable=False)  # P=purchase, S=sale, etc.
    acquisition_or_disposition = Column(String(1), nullable=False)  # A=acquired, D=disposed

    # Amounts
    shares = Column(Float, nullable=False)
    price_per_share = Column(Float, nullable=True)
    total_value = Column(Float, nullable=True)

    # Security info
    security_title = Column(String(200), nullable=False)
    is_derivative = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    form4_filing = relationship('RawForm4Filing', back_populates='transactions')
    insider = relationship('Insider', back_populates='transactions')
    company = relationship('Company', back_populates='transactions')

    # Indexes for common queries
    __table_args__ = (
        Index('ix_transaction_dates', 'filing_date', 'trade_date'),
        Index('ix_transaction_company_date', 'company_id', 'filing_date'),
        Index('ix_transaction_insider_date', 'insider_id', 'trade_date'),
        CheckConstraint('shares > 0', name='check_shares_positive'),
    )

    def __repr__(self):
        return (f"<InsiderTransaction(code='{self.transaction_code}', "
                f"shares={self.shares}, value={self.total_value})>")


class MarketCap(Base):
    """Historical market capitalization data."""

    __tablename__ = 'market_caps'

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    market_cap_usd = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    company = relationship('Company', back_populates='market_caps')

    # Unique constraint: one market cap per company per day
    __table_args__ = (
        UniqueConstraint('company_id', 'date', name='uix_market_cap_company_date'),
        Index('ix_market_cap_company_date', 'company_id', 'date'),
        CheckConstraint('market_cap_usd > 0', name='check_market_cap_positive'),
    )

    def __repr__(self):
        return f"<MarketCap(company_id={self.company_id}, date='{self.date}', cap={self.market_cap_usd})>"


class FilteredSignal(Base):
    """High-conviction signals after filtering and scoring."""

    __tablename__ = 'filtered_signals'

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(Integer, ForeignKey('insider_transactions.id'), nullable=False)

    # Scoring components
    executive_weight = Column(Float, nullable=False)
    dollar_weight = Column(Float, nullable=False)
    cluster_weight = Column(Float, nullable=False)
    market_cap_weight = Column(Float, nullable=False)
    composite_score = Column(Float, nullable=False, index=True)

    # Cluster info
    cluster_id = Column(String(100), nullable=True)
    cluster_size = Column(Integer, nullable=False, default=1)

    # Metadata
    is_actionable = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    transaction = relationship('InsiderTransaction')

    # Indexes for common queries
    __table_args__ = (
        Index('ix_signal_score', 'composite_score'),
        Index('ix_signal_actionable', 'is_actionable', 'composite_score'),
    )

    def __repr__(self):
        return (f"<FilteredSignal(score={self.composite_score:.2f}, "
                f"actionable={self.is_actionable})>")
