from cm_williams_vix_fix import CMWilliamsVixFixScanner
import pandas as pd

def debug_ticker_signal(ticker, target_date_str):
    scanner = CMWilliamsVixFixScanner()
    scanner.tickers = [ticker]
    
    print(f"Fetching data for {ticker}...")
    scanner.fetch_data()
    
    if ticker not in scanner.data.columns.levels[0]:
        print(f"Error: {ticker} not found in downloaded data.")
        return

    df = scanner.data[ticker].dropna()
    indicators = scanner.calculate_indicators(df)
    
    # Focus on a window around the target date
    target_date = pd.to_datetime(target_date_str)
    start_window = target_date - pd.Timedelta(days=10)
    end_window = target_date + pd.Timedelta(days=5)
    
    window = indicators[(indicators.index >= start_window) & (indicators.index <= end_window)]
    
    print(f"\nAnalysis for {ticker} around {target_date_str}:")
    print("-" * 120)
    print(f"{'Date':<12} | {'Close':<8} | {'SMA200':<8} | {'Regime (>SMA)':<15} | {'WVF':<8} | {'UpperBB':<8} | {'Signal (WVF>BB)':<15}")
    print("-" * 120)
    
    for date, row in window.iterrows():
        regime = row['Close'] > row['SMA200']
        signal = row['WVF'] > row['UpperBB']
        date_str = date.strftime('%Y-%m-%d')
        print(f"{date_str:<12} | {row['Close']:.2f}     | {row['SMA200']:.2f}     | {str(regime):<15} | {row['WVF']:.2f}     | {row['UpperBB']:.2f}     | {str(signal):<15}")

if __name__ == "__main__":
    debug_ticker_signal("QQQ", "2025-11-25")
