"""
Proof of Concept Test - Phase 1

Fetch and parse one Form 4 filing from SEC to verify:
1. SEC API client works
2. Form 4 parser works
3. End-to-end flow is functional
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import logging
from datetime import datetime, timedelta
import yaml
from collectors.sec_edgar import SECEdgarClient
from processors.form4_parser import Form4Parser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Run proof of concept test."""
    print("=" * 80)
    print("PHASE 1: PROOF OF CONCEPT TEST")
    print("=" * 80)
    print()

    # Load config
    config_path = Path(__file__).parent.parent / 'config.yaml'
    with open(config_path) as f:
        config = yaml.safe_load(f)

    sec_config = config['data_sources']['sec_api']

    # Initialize clients
    print("Initializing SEC EDGAR client...")
    sec_client = SECEdgarClient(sec_config)
    parser = Form4Parser()

    # Test ticker: Try TSLA (Tesla often has insider activity)
    ticker = 'TSLA'
    print(f"\nTesting with ticker: {ticker}")

    # Step 1: Get CIK
    print(f"\n[1/4] Looking up CIK for {ticker}...")
    cik = sec_client.get_company_cik(ticker)

    if not cik:
        print(f"❌ Failed to find CIK for {ticker}")
        return 1

    print(f"✅ Found CIK: {cik}")

    # Step 2: Get Form 4 filings from last 30 days
    print(f"\n[2/4] Fetching Form 4 filings from last 30 days...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    filings = sec_client.get_form4_filings(cik, start_date, end_date)

    if not filings:
        print(f"⚠️  No Form 4 filings found for {ticker} in last 30 days")
        print("This is normal - trying longer date range...")

        # Try 90 days
        start_date = end_date - timedelta(days=90)
        filings = sec_client.get_form4_filings(cik, start_date, end_date)

        if not filings:
            print(f"❌ No filings found in last 90 days")
            return 1

    print(f"✅ Found {len(filings)} filings")
    print(f"   First filing: {filings[0]['filing_date']}")

    # Step 3: Download first filing XML
    first_filing = filings[0]
    print(f"\n[3/4] Downloading Form 4 XML...")
    print(f"   URL: {first_filing['filing_url']}")

    xml_content = sec_client.get_form4_xml(first_filing['filing_url'])

    if not xml_content:
        print(f"❌ Failed to download XML")
        return 1

    print(f"✅ Downloaded XML ({len(xml_content)} bytes)")

    # Step 4: Parse Form 4
    print(f"\n[4/4] Parsing Form 4...")
    insider_trade = parser.parse_form4_xml(
        xml_content,
        first_filing['filing_url'],
        first_filing['filing_date']
    )

    if not insider_trade:
        print(f"❌ Failed to parse Form 4")
        return 1

    print(f"✅ Successfully parsed Form 4")
    print()
    print("=" * 80)
    print("INSIDER TRADE DETAILS")
    print("=" * 80)
    print(f"Filing Date:     {insider_trade.filing_date}")
    print(f"Is Amendment:    {insider_trade.is_amendment}")
    print(f"Issuer:          {insider_trade.issuer_name} (CIK: {insider_trade.issuer_cik})")
    print()
    print(f"Insider:         {insider_trade.owner_info.name}")
    print(f"Title:           {insider_trade.owner_info.officer_title}")
    print(f"Is Director:     {insider_trade.owner_info.is_director}")
    print(f"Is Officer:      {insider_trade.owner_info.is_officer}")
    print()
    print(f"Transactions:    {len(insider_trade.transactions)}")
    print()

    for i, tx in enumerate(insider_trade.transactions, 1):
        print(f"Transaction {i}:")
        print(f"  Date:          {tx.transaction_date}")
        print(f"  Code:          {tx.transaction_code}")
        print(f"  Type:          {'Purchase' if parser.is_purchase_transaction(tx.transaction_code) else 'Sale/Other'}")
        print(f"  Shares:        {tx.shares:,.0f}")
        print(f"  Price/Share:   ${tx.price_per_share:.2f}" if tx.price_per_share else "  Price/Share:   N/A")
        print(f"  Total Value:   ${tx.total_value:,.2f}" if tx.total_value else "  Total Value:   N/A")
        print(f"  Security:      {tx.security_title}")
        print(f"  Is Derivative: {tx.is_derivative}")
        print()

    # Filter purchases only
    purchase_trade = parser.filter_purchases_only(insider_trade)
    print(f"Purchase Transactions Only: {len(purchase_trade.transactions)}")

    print()
    print("=" * 80)
    print("✅ PROOF OF CONCEPT TEST PASSED")
    print("=" * 80)
    print()
    print("Phase 1 is complete. SEC API client and Form 4 parser are working.")

    return 0


if __name__ == '__main__':
    sys.exit(main())
