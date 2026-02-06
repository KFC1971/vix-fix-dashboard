
import pandas as pd
import requests

def get_nasdaq100_tickers():
    print("[INFO] Scraping Nasdaq 100 constituents from Wikipedia...")
    try:
        url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers)
        tables = pd.read_html(response.text)
        
        df_tickers = None
        for table in tables:
            if 'Ticker' in table.columns or 'Symbol' in table.columns:
                df_tickers = table
                break
        
        if df_tickers is not None:
            # Normalize columns
            rename_map = {
                'Symbol': 'Ticker',
                'Company': 'Name',
                'GICS Sector': 'Sector',
                'GICS Sub-Industry': 'Industry'
            }
            df_tickers = df_tickers.rename(columns={k: v for k, v in rename_map.items() if k in df_tickers.columns})
            
            if 'Symbol' in df_tickers.columns and 'Ticker' not in df_tickers.columns:
                df_tickers = df_tickers.rename(columns={'Symbol': 'Ticker'})
            
            tickers = df_tickers['Ticker'].apply(lambda x: x.replace('.', '-')).tolist()
            print(f"Retrieved {len(tickers)} tickers.")
            return tickers
        else:
            print("Could not find ticker table")
            return []
            
    except Exception as e:
        print(f"Failed: {e}")
        return []

tickers = get_nasdaq100_tickers()
print("Tickers found:", tickers)
for t in tickers:
    if not t.replace('-','').isalnum():
        print(f"SUSPICIOUS TICKER: '{t}'")
