"""Check what's in the index page"""

import requests

url = "https://www.sec.gov/Archives/edgar/data/1318605/000110465925090923/0001104659-25-090923-index.htm"
headers = {'User-Agent': 'OpenInsiderTrader research@example.com'}

response = requests.get(url, headers=headers)
content = response.text

print("Index page content:")
print("=" * 80)

# Find all links
import re
all_links = re.findall(r'href="([^"]+)"', content)

print("All links in index page:")
for link in all_links:
    print(f"  {link}")

print("\n" + "=" * 80)
print("\nLooking for documents table...")

# Look for the documents table section
if 'Document and Entity Information' in content:
    print("Found 'Document and Entity Information'")

# SEC index pages usually have a list of files in the filing
# Look for common Form 4 filenames
for line in content.split('\n'):
    if '.xml' in line.lower() or 'form4' in line.lower() or 'wf-form4' in line:
        print(line.strip())
