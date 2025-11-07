"""Debug script to check SEC API responses"""

import requests
from datetime import datetime, timedelta

# SEC requires User-Agent
headers = {
    'User-Agent': 'OpenInsiderTrader research@example.com'
}

# Get TSLA CIK first
cik = '0001318605'

# Try different API approaches
print("Testing SEC EDGAR API for TSLA Form 4s")
print("=" * 80)

# Approach 1: Basic search
url1 = 'https://www.sec.gov/cgi-bin/browse-edgar'
end_date = datetime.now()
start_date = end_date - timedelta(days=365)  # Try 1 year

params1 = {
    'action': 'getcompany',
    'CIK': cik,
    'type': '4',
    'dateb': end_date.strftime('%Y%m%d'),
    'owner': 'include',
    'count': '10',
    'output': 'xml'
}

print(f"\n1. Trying: {url1}")
print(f"   Params: {params1}")

response1 = requests.get(url1, params=params1, headers=headers)
print(f"   Status: {response1.status_code}")
print(f"   Response length: {len(response1.text)} bytes")

if '<filing>' in response1.text:
    print("   ✅ Found <filing> tags")
    # Count filings
    count = response1.text.count('<filing>')
    print(f"   Found {count} filings")
else:
    print("   ❌ No <filing> tags found")
    print("\n   First 1000 chars of response:")
    print(response1.text[:1000])
