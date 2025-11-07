"""
Form 4 XML Parser

This module parses SEC Form 4 XML filings to extract insider trading transactions.
Handles complex XML structure, derivative securities, and amendments.
"""

import logging
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)


@dataclass
class OwnerInfo:
    """Information about the insider making the trade."""
    name: str
    cik: Optional[str] = None
    is_director: bool = False
    is_officer: bool = False
    is_ten_percent_owner: bool = False
    officer_title: Optional[str] = None


@dataclass
class Transaction:
    """Single transaction within a Form 4 filing."""
    transaction_date: str  # YYYY-MM-DD
    transaction_code: str  # P=purchase, S=sale, etc.
    shares: float
    price_per_share: Optional[float]
    total_value: Optional[float]
    is_derivative: bool
    security_title: str
    acquisition_or_disposition: str  # A=acquisition, D=disposition


@dataclass
class InsiderTrade:
    """Complete insider trade information from Form 4."""
    filing_url: str
    filing_date: str  # YYYY-MM-DD
    is_amendment: bool
    owner_info: OwnerInfo
    transactions: List[Transaction]
    issuer_cik: Optional[str] = None
    issuer_name: Optional[str] = None


class Form4Parser:
    """
    Parser for SEC Form 4 XML filings.

    Extracts owner information and transaction details from complex XML structure.
    """

    # Transaction codes we care about
    PURCHASE_CODES = {'P', 'M'}  # P=Open market purchase, M=Exercise of options
    SALE_CODES = {'S', 'F'}  # S=Open market sale, F=Payment of exercise price or tax

    def __init__(self):
        """Initialize Form 4 parser."""
        self.namespaces = {}  # XML namespaces if needed

    def parse_form4_xml(self, xml_content: str, filing_url: str, filing_date: str) -> Optional[InsiderTrade]:
        """
        Parse Form 4 XML content into InsiderTrade object.

        Args:
            xml_content: Raw XML string from SEC
            filing_url: URL of the filing
            filing_date: Date of filing (YYYY-MM-DD)

        Returns:
            InsiderTrade object or None if parsing fails
        """
        try:
            root = ET.fromstring(xml_content)

            # Check if amendment
            is_amendment = self._is_amendment(root)

            # Extract issuer (company) info
            issuer_cik, issuer_name = self._extract_issuer_info(root)

            # Extract owner info
            owner_info = self._extract_owner_info(root)
            if not owner_info:
                logger.warning(f"No owner info found in filing {filing_url}")
                return None

            # Extract transactions
            transactions = self._extract_transactions(root)
            if not transactions:
                logger.debug(f"No transactions found in filing {filing_url}")
                return None

            return InsiderTrade(
                filing_url=filing_url,
                filing_date=filing_date,
                is_amendment=is_amendment,
                owner_info=owner_info,
                transactions=transactions,
                issuer_cik=issuer_cik,
                issuer_name=issuer_name
            )

        except ET.ParseError as e:
            logger.error(f"XML parsing error for {filing_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing {filing_url}: {e}")
            return None

    def _is_amendment(self, root: ET.Element) -> bool:
        """Check if this is an amendment filing."""
        not_subject_elem = root.find('.//notSubjectToSection16')
        if not_subject_elem is not None and not_subject_elem.text:
            return not_subject_elem.text.strip() == '1'
        return False

    def _extract_issuer_info(self, root: ET.Element) -> tuple[Optional[str], Optional[str]]:
        """Extract issuer (company) CIK and name."""
        issuer_cik = None
        issuer_name = None

        issuer = root.find('.//issuer')
        if issuer is not None:
            cik_elem = issuer.find('.//issuerCik')
            name_elem = issuer.find('.//issuerName')

            if cik_elem is not None and cik_elem.text:
                issuer_cik = cik_elem.text.strip()

            if name_elem is not None and name_elem.text:
                issuer_name = name_elem.text.strip()

        return issuer_cik, issuer_name

    def _extract_owner_info(self, root: ET.Element) -> Optional[OwnerInfo]:
        """Extract reporting owner information."""
        owner_elem = root.find('.//reportingOwner')
        if owner_elem is None:
            return None

        # Owner ID
        owner_id = owner_elem.find('.//reportingOwnerId')
        name = None
        cik = None

        if owner_id is not None:
            name_elem = owner_id.find('.//rptOwnerName')
            cik_elem = owner_id.find('.//rptOwnerCik')

            if name_elem is not None and name_elem.text:
                name = name_elem.text.strip()

            if cik_elem is not None and cik_elem.text:
                cik = cik_elem.text.strip()

        if not name:
            return None

        # Relationship to company
        relationship = owner_elem.find('.//reportingOwnerRelationship')
        is_director = False
        is_officer = False
        is_ten_percent = False
        officer_title = None

        if relationship is not None:
            director_elem = relationship.find('.//isDirector')
            officer_elem = relationship.find('.//isOfficer')
            ten_percent_elem = relationship.find('.//isTenPercentOwner')
            title_elem = relationship.find('.//officerTitle')

            if director_elem is not None and director_elem.text:
                is_director = director_elem.text.strip() == '1'

            if officer_elem is not None and officer_elem.text:
                is_officer = officer_elem.text.strip() == '1'

            if ten_percent_elem is not None and ten_percent_elem.text:
                is_ten_percent = ten_percent_elem.text.strip() == '1'

            if title_elem is not None and title_elem.text:
                officer_title = title_elem.text.strip()

        return OwnerInfo(
            name=name,
            cik=cik,
            is_director=is_director,
            is_officer=is_officer,
            is_ten_percent_owner=is_ten_percent,
            officer_title=officer_title
        )

    def _extract_transactions(self, root: ET.Element) -> List[Transaction]:
        """Extract all transactions from the filing."""
        transactions = []

        # Non-derivative transactions
        non_deriv_table = root.find('.//nonDerivativeTable')
        if non_deriv_table is not None:
            for tx in non_deriv_table.findall('.//nonDerivativeTransaction'):
                parsed = self._parse_transaction(tx, is_derivative=False)
                if parsed:
                    transactions.append(parsed)

        # Derivative transactions
        deriv_table = root.find('.//derivativeTable')
        if deriv_table is not None:
            for tx in deriv_table.findall('.//derivativeTransaction'):
                parsed = self._parse_transaction(tx, is_derivative=True)
                if parsed:
                    transactions.append(parsed)

        return transactions

    def _parse_transaction(self, tx_elem: ET.Element, is_derivative: bool) -> Optional[Transaction]:
        """Parse a single transaction element."""
        try:
            # Security title
            security_elem = tx_elem.find('.//securityTitle/value')
            security_title = security_elem.text.strip() if security_elem is not None and security_elem.text else 'Unknown'

            # Transaction date
            date_elem = tx_elem.find('.//transactionDate/value')
            if date_elem is None or not date_elem.text:
                return None
            transaction_date = date_elem.text.strip()

            # Transaction code
            code_elem = tx_elem.find('.//transactionCoding/transactionCode')
            if code_elem is None or not code_elem.text:
                return None
            transaction_code = code_elem.text.strip()

            # Acquisition or disposition
            acq_disp_elem = tx_elem.find('.//transactionAmounts/transactionAcquiredDisposedCode/value')
            acquisition_or_disposition = acq_disp_elem.text.strip() if acq_disp_elem is not None and acq_disp_elem.text else 'A'

            # Shares
            shares_elem = tx_elem.find('.//transactionAmounts/transactionShares/value')
            if shares_elem is None or not shares_elem.text:
                return None

            try:
                shares = float(shares_elem.text.strip())
            except (ValueError, AttributeError):
                return None

            # Price per share
            price_elem = tx_elem.find('.//transactionAmounts/transactionPricePerShare/value')
            price_per_share = None
            if price_elem is not None and price_elem.text:
                try:
                    price_per_share = float(price_elem.text.strip())
                except (ValueError, AttributeError):
                    pass

            # Calculate total value
            total_value = None
            if price_per_share is not None:
                total_value = shares * price_per_share

            return Transaction(
                transaction_date=transaction_date,
                transaction_code=transaction_code,
                shares=shares,
                price_per_share=price_per_share,
                total_value=total_value,
                is_derivative=is_derivative,
                security_title=security_title,
                acquisition_or_disposition=acquisition_or_disposition
            )

        except Exception as e:
            logger.warning(f"Failed to parse transaction: {e}")
            return None

    def is_purchase_transaction(self, transaction_code: str) -> bool:
        """
        Check if transaction code represents a purchase.

        Args:
            transaction_code: Single letter code from Form 4

        Returns:
            True if purchase, False otherwise
        """
        return transaction_code in self.PURCHASE_CODES

    def filter_purchases_only(self, insider_trade: InsiderTrade) -> InsiderTrade:
        """
        Filter InsiderTrade to include only purchase transactions.

        Args:
            insider_trade: Original InsiderTrade object

        Returns:
            New InsiderTrade with only purchase transactions
        """
        purchase_transactions = [
            tx for tx in insider_trade.transactions
            if self.is_purchase_transaction(tx.transaction_code)
            and tx.acquisition_or_disposition == 'A'  # Acquired, not disposed
        ]

        return InsiderTrade(
            filing_url=insider_trade.filing_url,
            filing_date=insider_trade.filing_date,
            is_amendment=insider_trade.is_amendment,
            owner_info=insider_trade.owner_info,
            transactions=purchase_transactions,
            issuer_cik=insider_trade.issuer_cik,
            issuer_name=insider_trade.issuer_name
        )
