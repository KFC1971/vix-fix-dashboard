# ==============================================================================
# PROJECT:   DEEP VALUE REGIME SWITCH (DVRS) - INDUSTRIAL GRADE IMPLEMENTATION
# AUTHOR:    Portfolio Manager
# PLATFORM:  Google Colab / Jupyter
# DATA:      FinMind (Raw Factual Data)
# ==============================================================================

import subprocess
import sys
import time
import warnings

# --- 1. DEPENDENCY MANAGEMENT (Auto-Install) ---
def install_dependencies():
    packages = ['finmind', 'tqdm', 'pandas', 'numpy', 'matplotlib']
    for package in packages:
        try:
            __import__(package)
        except ImportError:
            print(f"Installing system dependency: {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# install_dependencies()

# --- IMPORTS ---
from FinMind.data import DataLoader
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
import os

# Suppress pandas fragmentation warnings for clean output
warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)

# ==============================================================================
# CLASS 1: DATA INGESTION ENGINE
# Purpose: robustly fetch, clean, and standardize raw API data.
# ==============================================================================
class DataEngine:
    def __init__(self, token=None):
        self.loader = DataLoader()
        if token:
            self.loader.login_by_token(api_token=token)
            print("API Token: Authenticated.")
        else:
            print("API Token: None (Using Free Tier - Limited Speed).")

    def get_universe(self):
        """
        Returns a list of liquid stocks (Taiwan 50 + MidCap 100 constituents).
        Using a representative list to ensure Colab memory stability.
        """
        # A static list of major liquid stocks across sectors (Tech, Finance, raw mats)
        # This acts as our "Market Proxy".
        universe = [
            '2330', '2317', '2454', '2308', '2412', '2303', '2881', '2882', '2891', '2002',
            '1101', '1102', '1216', '1301', '1303', '1326', '2105', '2207', '2327', '2357',
            '2603', '2609', '2615', '2884', '2886', '2892', '2912', '3008', '3045', '4904',
            '4938', '5871', '5880', '6505', '9910', '2382', '2395', '2408', '2409', '3231',
            '2344', '2353', '2356', '2379', '2474', '2492', '3034', '3037', '3105', '3711',
            '5347', '5483', '6147', '6274', '6488', '8046', '8069', '8299', '8436', '9914'
        ]
        return list(set(universe)) # Dedup

    def fetch_market_data(self, stocks, start_date, end_date):
        cache_file = "market_data_cache.csv"
        if os.path.exists(cache_file):
            print(f"--> Loading Market Data from Cache ({cache_file})...")
            df_merge = pd.read_csv(cache_file)
            df_merge['date'] = pd.to_datetime(df_merge['date'])
            # Filter by date range in case cache is larger or different
            mask = (df_merge['date'] >= pd.to_datetime(start_date)) & (df_merge['date'] <= pd.to_datetime(end_date))
            return df_merge.loc[mask].sort_values('date')

        print(f"--> Fetching Price & Valuation Data ({len(stocks)} stocks)...")
        # Price Data
        df_price = self.loader.taiwan_stock_daily(stock_id=stocks, start_date=start_date, end_date=end_date)
        df_price['date'] = pd.to_datetime(df_price['date'])
        df_price['close'] = pd.to_numeric(df_price['close'], errors='coerce')
        
        # Valuation Data (P/E, P/B)
        df_val = self.loader.taiwan_stock_per_pbr(stock_id=stocks, start_date=start_date, end_date=end_date)
        df_val.columns = [c.lower() for c in df_val.columns]
        print(f"DEBUG: df_val columns: {df_val.columns.tolist()}")
        df_val['date'] = pd.to_datetime(df_val['date'])
        df_val['pbr'] = pd.to_numeric(df_val['pbr'], errors='coerce')
        df_val['per'] = pd.to_numeric(df_val['per'], errors='coerce')
        
        # Merge
        df_merge = pd.merge(df_price, df_val[['date', 'stock_id', 'pbr', 'per']], on=['date', 'stock_id'], how='inner')
        df_merge = df_merge.sort_values('date')
        
        print(f"--> Saving Market Data to Cache ({cache_file})...")
        df_merge.to_csv(cache_file, index=False)
        return df_merge

    def fetch_financials(self, stocks, start_date, end_date):
        cache_file = "financials_data_cache.csv"
        if os.path.exists(cache_file):
            print(f"--> Loading Financial Data from Cache ({cache_file})...")
            df_pivot = pd.read_csv(cache_file)
            df_pivot['date'] = pd.to_datetime(df_pivot['date'])
            # Filter by date range
            # Note: Financials have a lag, so we might need a buffer, but here we just filter strictly or trust the cache?
            # To be safe, let's just use the cache if it exists, assuming the user aims for the same 20 years.
            # Or better, filter.
            mask = (df_pivot['date'] >= pd.to_datetime(start_date)) & (df_pivot['date'] <= pd.to_datetime(end_date))
            return df_pivot.loc[mask].sort_values(['stock_id', 'date'])

        print(f"--> Fetching Raw Financial Statements (Accountant Mode)...")
        all_dfs = []
        
        # Batching to avoid timeouts
        batch_size = 10
        for i in tqdm(range(0, len(stocks), batch_size)):
            batch = stocks[i:i+batch_size]
            for stock in batch:
                try:
                    # Fetch Income Statement
                    df_is = self.loader.taiwan_stock_financial_statement(
                        stock_id=stock, start_date=start_date, end_date=end_date
                    )
                    if not df_is.empty: all_dfs.append(df_is)
                    
                    # Fetch Balance Sheet
                    df_bs = self.loader.taiwan_stock_balance_sheet(
                        stock_id=stock, start_date=start_date, end_date=end_date
                    )
                    if not df_bs.empty: all_dfs.append(df_bs)
                    
                    # Fetch Cash Flow
                    df_cf = self.loader.taiwan_stock_cash_flows_statement(
                        stock_id=stock, start_date=start_date, end_date=end_date
                    )
                    if not df_cf.empty: all_dfs.append(df_cf)
                    
                except Exception as e:
                    print(f"Error fetching stock {stock}: {e}")
                    continue 
        
        if not all_dfs:
            raise ValueError("Data Fetch Failed. The API might be busy. Try reducing the date range.")
            
        df_raw = pd.concat(all_dfs)
        
        # DEBUG: Print unique origin_name values to find the correct keys
        unique_keys = df_raw['origin_name'].unique()
        print(f"DEBUG: Found {len(unique_keys)} unique origin_name values.")
        print(f"DEBUG: First 50 keys: {unique_keys[:50]}")
        # Save unique keys to a file for review
        with open("debug_origin_names.txt", "w", encoding="utf-8") as f:
            for k in unique_keys:
                f.write(f"{k}\n")

        # PIVOT LOGIC (The Hardest Part: Mapping Chinese Keys)
        # We filter only for the specific rows we need to calculate F-Score
        target_keys = [
            '資產總額', '負債總額', '流動資產', '流動負債', '非流動負債',
            '營業收入合計', '營業成本合計', '本期淨利（淨損）', 
            '營業活動之淨現金流入（流出）', '股本',
            # Variants found in debug or common in FinMind
            '營業收入', '營業成本', '本期淨利(淨損)', '營業活動之淨現金流入(流出)',
            '稅後淨利', '流動資產合計', '流動負債合計', '非流動負債合計', '權益總額', '基本每股盈餘(元)'
        ]
        
        df_filtered = df_raw[df_raw['origin_name'].isin(target_keys)].copy()
        
        if df_filtered.empty:
            print("WARNING: df_filtered is empty! Check target_keys vs debug_origin_names.txt")
        
        # Pivot: Rows=Date/Stock, Cols=Metric
        df_pivot = df_filtered.pivot_table(
            index=['date', 'stock_id'], columns='origin_name', values='value'
        ).reset_index()
        
        # English Rename for Code Safety
        mapper = {
            '資產總額': 'TotalAssets', '負債總額': 'TotalLiabilities',
            '流動資產': 'CurrentAssets', '流動資產合計': 'CurrentAssets',
            '流動負債': 'CurrentLiabilities', '流動負債合計': 'CurrentLiabilities',
            '非流動負債': 'LongTermDebt', '非流動負債合計': 'LongTermDebt',
            '營業收入合計': 'Revenue', '營業收入': 'Revenue',
            '營業成本合計': 'COGS', '營業成本': 'COGS',
            '本期淨利（淨損）': 'NetIncome', '本期淨利(淨損)': 'NetIncome', '稅後淨利': 'NetIncome',
            '營業活動之淨現金流入（流出）': 'CFO', '營業活動之淨現金流入(流出)': 'CFO',
            '股本': 'Shares'
        }
        df_pivot = df_pivot.rename(columns=mapper)
        df_pivot['date'] = pd.to_datetime(df_pivot['date'])
        
        # FIX: LOOKAHEAD BIAS
        # Financial statements are NOT available on the period end date.
        # We must lag them by ~45 days (legal deadline for Q1-Q3).
        print("--> Applying 45-day Reporting Lag (Fixing Lookahead Bias)...")
        df_pivot['date'] = df_pivot['date'] + pd.Timedelta(days=45)
        
        df_pivot = df_pivot.fillna(0).sort_values(['stock_id', 'date'])

        print(f"--> Saving Financial Data to Cache ({cache_file})...")
        df_pivot.to_csv(cache_file, index=False)
        return df_pivot

# ==============================================================================
# CLASS 2: SIGNAL GENERATOR (The "Brain")
# Purpose: Calculate Piotroski F-Score and Regime Signals
# ==============================================================================
class AlphaModel:
    @staticmethod
    def calculate_f_score(df_fin):
        """
        Calculates the 0-9 Piotroski F-Score based on raw financial columns.
        """
        print("--> Computing Piotroski F-Scores...")
        df = df_fin.copy()
        g = df.groupby('stock_id')
        
        # --- 1. Profitability ---
        df['ROA'] = df['NetIncome'] / df['TotalAssets'].replace(0, np.nan)
        s1 = (df['ROA'] > 0).astype(int)
        s2 = (df['CFO'] > 0).astype(int)
        s3 = (df['ROA'] > g['ROA'].shift(1)).astype(int) # Delta ROA
        s4 = (df['CFO'] > df['NetIncome']).astype(int)   # Accruals
        
        # --- 2. Leverage/Liquidity ---
        # Long Term Debt Ratio (proxy using non-current liabilities)
        df['LTD_Ratio'] = df['LongTermDebt'] / df['TotalAssets'].replace(0, np.nan)
        s5 = (df['LTD_Ratio'] < g['LTD_Ratio'].shift(1)).astype(int)
        
        df['CurrentRatio'] = df['CurrentAssets'] / df['CurrentLiabilities'].replace(0, np.nan)
        s6 = (df['CurrentRatio'] > g['CurrentRatio'].shift(1)).astype(int)
        
        s7 = (df['Shares'] <= g['Shares'].shift(1)).astype(int) # No Dilution
        
        # --- 3. Efficiency ---
        df['GrossMargin'] = (df['Revenue'] - df['COGS']) / df['Revenue'].replace(0, np.nan)
        s8 = (df['GrossMargin'] > g['GrossMargin'].shift(1)).astype(int)
        
        df['AssetTurnover'] = df['Revenue'] / df['TotalAssets'].replace(0, np.nan)
        s9 = (df['AssetTurnover'] > g['AssetTurnover'].shift(1)).astype(int)
        
        df['F_Score'] = s1 + s2 + s3 + s4 + s5 + s6 + s7 + s8 + s9
        return df[['date', 'stock_id', 'F_Score']]

    @staticmethod
    def generate_signals(df_price, df_scores):
        print("--> Merging Data & Generating Signals...")
        
        # Strict alignment: Match Daily Price with LATEST PAST Quarterly Score
        df_full = pd.merge_asof(
            df_price.sort_values('date'),
            df_scores.sort_values('date'),
            on='date',
            by='stock_id',
            direction='backward' # No lookahead bias
        )
        
        # Signal 1: Deep Value (P/B < 0.7 AND P/E < 13)
        # Updated to "Industrial Grade" specs from reference
        df_full['is_value'] = (df_full['pbr'] < 0.7) & (df_full['per'] < 13)
        
        # Signal 2: Quality (F-Score >= 5)
        df_full['is_quality'] = df_full['F_Score'] >= 5
        
        # Signal 3: Regime (Market Thermometer)
        # Count total cheap stocks in universe per day
        # We pivot first to count easily across the day
        daily_counts = df_full[df_full['is_value']].groupby('date')['stock_id'].count()
        df_full['market_cheap_count'] = df_full['date'].map(daily_counts).fillna(0)
        
        # Safety Threshold: If < 5 stocks are cheap in this universe, Exit Market.
        # (In a full 1700 stock universe, use 100. Here 5-10 is proportional).
        df_full['is_safe_regime'] = df_full['market_cheap_count'] > 5
        
        # Final Signal: Value + Quality + Safe Regime
        df_full['signal'] = (df_full['is_value'] & df_full['is_quality'] & df_full['is_safe_regime'])
        
        return df_full

# ==============================================================================
# CLASS 3: BACKTESTING ENGINE (Vectorized)
# Purpose: Simulate execution with fees and equal weighting.
# ==============================================================================
class Backtester:
    @staticmethod
    def run(df_signals, initial_capital=1_000_000):
        print("--> Running Historical Simulation (Quarterly Rebalancing)...")
        
        # Copy to avoid warnings
        data = df_signals.copy()
        data = data.sort_values(['date', 'stock_id'])
        
        # Pivot everything for vectorized backtesting
        prices = data.pivot(index='date', columns='stock_id', values='close').ffill()
        signals = data.pivot(index='date', columns='stock_id', values='signal').fillna(False).astype(int)
        
        # --- QUARTERLY REBALANCING LOGIC ---
        # We only want to change positions on specific dates (e.g., end of Q).
        # We can resample the signal dataframe to Quarter Ends, then reindex back to Daily.
        
        # 1. Resample signals to Quarterly (taking the last signal of the quarter)
        q_signals = signals.resample('Q').last()
        
        # 2. Reindex back to daily (forward fill the quarterly decision)
        # This means if we decided to buy on Q1 (Mar 31), we hold until Q2 (Jun 30).
        daily_target_positions = q_signals.reindex(prices.index).ffill()
        
        # 3. Shift by 1 day to trade on the NEXT Open/Close after the signal
        held_positions = daily_target_positions.shift(1).fillna(0)
        
        # --- PORTFOLIO CALCULATIONS ---
        
        # Equal Weighting
        stock_counts = held_positions.sum(axis=1)
        weights = held_positions.div(stock_counts.replace(0, 1), axis=0)
        
        # Daily Returns of stocks
        daily_stock_rets = prices.pct_change().fillna(0)
        
        # Gross Portfolio Return
        gross_rets = (weights * daily_stock_rets).sum(axis=1)
        
        # --- TRANSACTION COSTS ---
        # Cost = Turnover * Fee
        # Turnover = Sum of absolute change in weights
        weight_change = weights.diff().abs().sum(axis=1).fillna(0)
        costs = weight_change * 0.002 # 0.2% total slippage+fee
        
        # Net Return
        net_rets = gross_rets - costs
        
        # Equity Curve
        equity = (1 + net_rets).cumprod() * initial_capital
        
        # Drawdown
        running_max = equity.cummax()
        drawdown = (equity - running_max) / running_max
        
        return equity, drawdown, data['market_cheap_count'].groupby('date').first()

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # CONFIGURATION
    TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0yMCAyMzo1OToxOCIsInVzZXJfaWQiOiJyYXBoZWFsY2hhbiIsImVtYWlsIjoicmFwaGVhbGNoYW5AZ21haWwuY29tIiwiaXAiOiI2MS42NC4xNDUuMTUxIn0.8lYXMaqfKzmLJqTtEnHlRYaxST60Dip9eAu-Lp2Jzvk"  # Put your FinMind Token here if you have one
    START = "2005-01-01" 
    END = "2025-01-01"
    
    # 1. Init Data
    bot = DataEngine(token=TOKEN)
    universe = bot.get_universe()
    
    # 2. Fetch
    df_market = bot.fetch_market_data(universe, START, END)
    df_financials = bot.fetch_financials(universe, START, END)
    
    # 3. Model
    df_scores = AlphaModel.calculate_f_score(df_financials)
    df_final = AlphaModel.generate_signals(df_market, df_scores)
    
    # 4. Backtest
    equity, dd, regime_data = Backtester.run(df_final)
    
    # 5. Reporting
    total_ret = ((equity.iloc[-1] / equity.iloc[0]) - 1) * 100
    max_dd = dd.min() * 100
    
    print("\n" + "="*40)
    print(f"STRATEGY RESULTS ({START} to {END})")
    print("="*40)
    print(f"Total Return: {total_ret:.2f}%")
    print(f"Max Drawdown: {max_dd:.2f}%")
    print(f"Final Capital: ${equity.iloc[-1]:,.0f}")
    
    # Yearly Calculation
    print("\n" + "-"*40)
    print("YEARLY PERFORMANCE")
    print("-"*40)
    yearly_equity = equity.resample('YE').last() # 'YE' is the updated panda alias for YearEnd, avoiding warnings
    if yearly_equity.empty or yearly_equity.index[0] > equity.index[0]:
         # Prepend start capital if first year is incomplete or checks needed
         initial = pd.Series([initial_capital], index=[pd.to_datetime(START)])
         # This logic can be tricky depending on data availability, simpler to just use pct_change on resampled
         pass
         
    yearly_rets = yearly_equity.pct_change()
    # Handle first year
    first_year_ret = (yearly_equity.iloc[0] / initial_capital) - 1
    yearly_rets.iloc[0] = first_year_ret
    
    for date, ret in yearly_rets.items():
        print(f"{date.year}: {ret*100:6.2f}%")

    
    # 6. Visualization
    plt.figure(figsize=(12, 10))
    
    # Equity Curve
    plt.subplot(3, 1, 1)
    plt.plot(equity, color='#1f77b4', linewidth=2)
    plt.title("Portfolio Equity Curve (Deep Value + Quality)", fontsize=12, fontweight='bold')
    plt.grid(True, alpha=0.3)
    
    # Drawdown Area
    plt.subplot(3, 1, 2)
    plt.fill_between(dd.index, dd, 0, color='red', alpha=0.3)
    plt.title("Drawdown Profile (Risk Control)", fontsize=12, fontweight='bold')
    plt.grid(True, alpha=0.3)
    
    # Regime Thermometer
    plt.subplot(3, 1, 3)
    plt.bar(regime_data.index, regime_data, color='gray', label='Cheap Stock Count', width=2)
    plt.axhline(y=5, color='green', linestyle='--', linewidth=2, label='Safety Threshold (5)')
    plt.fill_between(regime_data.index, 0, 100, where=(regime_data < 5), color='red', alpha=0.1, label='CASH MODE')
    plt.title("Market Thermometer (Regime Switch)", fontsize=12, fontweight='bold')
    plt.legend(loc='upper right')
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()