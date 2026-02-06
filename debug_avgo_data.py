import yfinance as yf
import pandas as pd
import numpy as np

def debug_data():
    ticker = "AVGO"
    print(f"Fetching data for {ticker}...")
    
    # Fetch wider range to ensure 22-day lookback is valid
    start_date = "2025-10-01"
    end_date = "2026-01-01"
    
    df = yf.download([ticker], start=start_date, end=end_date, group_by='ticker')
    # Use ticker level if present
    if ticker in df.columns.levels[0]:
        df = df[ticker]
    
    df = df.dropna()
    
    # Calculate WVF manually
    period = 22
    # Highest Close in past 22 days
    df['HighestClose'] = df['Close'].rolling(window=period).max()
    df['WVF'] = ((df['HighestClose'] - df['Low']) / df['HighestClose']) * 100
    
    # Calculate BB
    bb_length = 20
    bb_std = 2.0
    df['WVF_SMA'] = df['WVF'].rolling(window=bb_length).mean()
    df['WVF_STD'] = df['WVF'].rolling(window=bb_length).std()
    df['UpperBB'] = df['WVF_SMA'] + (bb_std * df['WVF_STD'])
    
    df['Signal'] = df['WVF'] > df['UpperBB']
    
    # Focus on target window
    target_date = pd.to_datetime("2025-12-22")
    start_window = target_date - pd.Timedelta(days=5)
    end_window = target_date + pd.Timedelta(days=5)
    
    window = df[(df.index >= start_window) & (df.index <= end_window)]
    
    print(f"\nDetailed Data for {ticker}:")
    print("-" * 150)
    headers = ['Date', 'Open', 'High', 'Low', 'Close', 'HighestClose', 'WVF', 'WVF_SMA', 'WVF_STD', 'UpperBB', 'Signal']
    print(f"{headers[0]:<12} | " + " | ".join([f"{h:<10}" for h in headers[1:]]))
    print("-" * 150)
    
    for date, row in window.iterrows():
        d_str = date.strftime('%Y-%m-%d')
        vals = [
            f"{row['Open']:.2f}", f"{row['High']:.2f}", f"{row['Low']:.2f}", f"{row['Close']:.2f}",
            f"{row['HighestClose']:.2f}", f"{row['WVF']:.2f}", 
            f"{row['WVF_SMA']:.2f}", f"{row['WVF_STD']:.2f}", f"{row['UpperBB']:.2f}",
            str(row['Signal'])
        ]
        print(f"{d_str:<12} | " + " | ".join([f"{v:<10}" for v in vals]))

if __name__ == "__main__":
    debug_data()
