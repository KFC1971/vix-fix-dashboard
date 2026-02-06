import yfinance as yf
import pandas as pd
import datetime
import os

def reproduction_test():
    print("Starting reproduction test...")
    
    # List of tickers from the "Top ETFs" section of cm_williams_vix_fix.py
    tickers = [
        'SPY', 'IVV', 'VOO', 'QQQ', 'IWM', 'EFA', 'VEA', 'VWO',
        'AGG', 'BND', 'TLT', 'IEF', 'LQD', 'HYG', 'JNK', 'SHY',
        'GLD', 'IAU', 'SLV', 'USO', 'UNG',
        'XLE', 'XLF', 'XLK', 'XLV', 'XLI', 'XLP', 'XLU', 'XLY', 'XLB', 'XLRE', 'XLC',
        'SMH', 'SOXX', 'IBB', 'XBI', 'KRE', 'KBE', 'VNQ', 'GDX', 'GDXJ',
        'TQQQ', 'SQQQ', 'SOXL', 'SOXS', 'SPXL', 'SPXS', 'UPRO', 'TNA', 'TZA', 'LABU',
        'ARKK', 'JEPI', 'SCHD', 'VIG', 'VYM'
    ]
    
    print(f"Testing download for {len(tickers)} tickers...")
    
    start_date = (datetime.datetime.now() - datetime.timedelta(days=1825)).strftime('%Y-%m-%d')
    end_date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    print(f"Date range: {start_date} to {end_date}")
    
    try:
        # Mimic the call in cm_williams_vix_fix.py
        # new_data = yf.download(self.tickers, start=start_date, end=end_date, group_by='ticker', progress=True, threads=False)
        print("Attempting yf.download(threads=False)...")
        data = yf.download(tickers, start=start_date, end=end_date, group_by='ticker', progress=True, threads=False)
        
        if data is None or data.empty:
            print("Download returned empty or None.")
        else:
            print(f"Download successful. Shape: {data.shape}")
            
    except Exception as e:
        print(f"CAUGHT EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    reproduction_test()
