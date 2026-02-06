import requests
from bs4 import BeautifulSoup
import json

def parse_wantgoo():
    # Attempt to fetch the main page
    url = "https://www.wantgoo.com/stock/dividend-yield"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://www.wantgoo.com/"
    }
    
    try:
        print(f"Fetching {url}...")
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check for table
            tables = soup.find_all('table')
            print(f"Found {len(tables)} tables.")
            
            found_data = False
            for tbl in tables:
                rows = tbl.find_all('tr')
                if len(rows) > 10:
                    print(f"Potential data table with {len(rows)} rows found.")
                    # Try to find header "五年平均"
                    header_row = rows[0]
                    headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
                    print(f"Headers: {headers}")
                    
                    found_data = True
                    break
            
            if not found_data:
                print("No HTML table found. Checking for embedded JSON...")
                # Sometimes data is in a <script> tag
                scripts = soup.find_all('script')
                for s in scripts:
                    if s.string and "dividend" in s.string[:1000]: # simplistic check
                       print("Found script referencing 'dividend'")

        else:
            print(f"Failed with status {response.status_code}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    parse_wantgoo()
