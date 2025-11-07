"""Detailed debug of SEC API response"""

import requests
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

headers = {
    'User-Agent': 'OpenInsiderTrader research@example.com'
}

cik = '0001318605'  # TSLA
url = 'https://www.sec.gov/cgi-bin/browse-edgar'
end_date = datetime.now()

params = {
    'action': 'getcompany',
    'CIK': cik,
    'type': '4',
    'dateb': end_date.strftime('%Y%m%d'),
    'owner': 'include',
    'count': '10',
    'output': 'xml'
}

print("Fetching Form 4s for TSLA...")
response = requests.get(url, params=params, headers=headers)

print(f"Status: {response.status_code}")
print("\nFirst 2000 chars of response:")
print("=" * 80)
print(response.text[:2000])
print("=" * 80)

# Parse and show structure
root = ET.fromstring(response.text)
print("\nXML Structure:")
for filing in root.findall('.//filing')[:3]:  # First 3 filings
    print("\nFiling:")
    for child in filing:
        print(f"  <{child.tag}>: {child.text}")
