"""Debug XML content extraction"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import yaml
from collectors.sec_edgar import SECEdgarClient
from datetime import datetime, timedelta

# Load config
config_path = Path(__file__).parent.parent / 'config.yaml'
with open(config_path) as f:
    config = yaml.safe_load(f)

sec_config = config['data_sources']['sec_api']
client = SECEdgarClient(sec_config)

# Get TSLA filings
cik = '0001318605'
end_date = datetime.now()
start_date = end_date - timedelta(days=90)

filings = client.get_form4_filings(cik, start_date, end_date)
print(f"Found {len(filings)} filings")

if filings:
    first_filing = filings[0]
    print(f"\nFetching: {first_filing['filing_url']}")

    xml_content = client.get_form4_xml(first_filing['filing_url'])

    print(f"\nXML Content ({len(xml_content)} bytes):")
    print("=" * 80)
    print(xml_content[:2000])  # First 2000 chars
    print("=" * 80)

    # Try to parse it
    from xml.etree import ElementTree as ET
    try:
        root = ET.fromstring(xml_content)
        print(f"\n✅ XML parsed successfully!")
        print(f"Root tag: {root.tag}")
    except ET.ParseError as e:
        print(f"\n❌ XML parsing failed: {e}")
        print(f"\nTrying to clean XML...")

        # Sometimes there's XML declaration with encoding issues
        if '<?xml' in xml_content:
            # Remove XML declaration
            xml_content_clean = xml_content.split('?>', 1)[1].strip()
            print(f"Removed declaration, trying again...")
            try:
                root = ET.fromstring(xml_content_clean)
                print(f"✅ Parsed after removing declaration!")
            except ET.ParseError as e2:
                print(f"❌ Still failed: {e2}")
