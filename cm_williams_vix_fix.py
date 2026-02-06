import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import warnings
import json
import os

# Suppress warnings
warnings.filterwarnings('ignore')

class CMWilliamsVixFixScanner:
    def __init__(self, lookback_period=22, bb_length=20, bb_std=2.0, sma_filter=200, top_n_volume=100, logger_callback=None):
        self.lookback_period = lookback_period
        self.bb_length = bb_length
        self.bb_std = bb_std
        self.sma_filter = sma_filter
        self.top_n_volume = top_n_volume
        self.logger_callback = logger_callback
        self.tickers = []
        self.data = {}
        self.universe_df = None
        self.current_universe = "sp500" # Default universe state

    def log(self, message):
        if self.logger_callback:
            self.logger_callback(message)
        print(message)

    def get_sp500_tickers(self):
        self.log("[INFO] Scraping S&P 500 constituents from Wikipedia...")
        try:
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            import requests
            response = requests.get(url, headers=headers)
            tables = pd.read_html(response.text)
            df_tickers = tables[0]
            
            # Normalize columns
            rename_map = {
                'Symbol': 'Ticker',
                'Security': 'Name',
                'GICS Sector': 'Sector',
                'GICS Sub-Industry': 'Industry'
            }
            # Only rename columns that exist
            df_tickers = df_tickers.rename(columns={k: v for k, v in rename_map.items() if k in df_tickers.columns})
            
            # Ensure required columns exist
            if 'Sector' not in df_tickers.columns:
                df_tickers['Sector'] = 'Unknown'
            
            self.universe_df = df_tickers
            
            # Replace dots with dashes for YFinance compatibility
            self.tickers = df_tickers['Ticker'].apply(lambda x: x.replace('.', '-')).tolist()
            self.log(f"  Retrieved {len(self.tickers)} tickers.")
            return self.tickers
        except Exception as e:
            self.log(f"  Failed to retrieve tickers: {e}")
            self.tickers = []
            self.universe_df = None
            return []

    def get_nasdaq100_tickers(self):
        self.log("[INFO] Scraping Nasdaq 100 constituents from Wikipedia...")
        try:
            url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            import requests
            response = requests.get(url, headers=headers)
            tables = pd.read_html(response.text)
            
            df_tickers = None
            for table in tables:
                if 'Ticker' in table.columns or 'Symbol' in table.columns:
                    df_tickers = table
                    break
            
            if df_tickers is not None:
                # Normalize columns. Wiki table usually has "Ticker", "Company", "GICS Sector", "GICS Sub-Industry"
                rename_map = {
                    'Symbol': 'Ticker',
                    'Company': 'Name',
                    'GICS Sector': 'Sector',
                    'GICS Sub-Industry': 'Industry'
                }
                df_tickers = df_tickers.rename(columns={k: v for k, v in rename_map.items() if k in df_tickers.columns})
                
                # Ensure Ticker column name is consistent
                if 'Symbol' in df_tickers.columns and 'Ticker' not in df_tickers.columns:
                    df_tickers = df_tickers.rename(columns={'Symbol': 'Ticker'})
                
                if 'Sector' not in df_tickers.columns:
                     df_tickers['Sector'] = 'Technology' # Fallback for now, usually it exists

                self.universe_df = df_tickers
                self.tickers = df_tickers['Ticker'].apply(lambda x: x.replace('.', '-')).tolist()
                self.log(f"  Retrieved {len(self.tickers)} tickers.")
                return self.tickers
            else:
                raise ValueError("Could not find ticker table in Wikipedia page")
                
        except Exception as e:
            self.log(f"  Failed to retrieve Nasdaq 100 tickers: {e}")
            self.tickers = []
            self.universe_df = None
            return []

    def get_top_etf_tickers(self):
        self.log("[INFO] Loading Top Liquid ETFs list...")
        # Structured Data for ETFs
        etf_data = [
            # Broad Market
            {'Ticker': 'SPY', 'Name': 'SPDR S&P 500', 'Sector': 'Equity: Large Cap'},
            {'Ticker': 'IVV', 'Name': 'iShares Core S&P 500', 'Sector': 'Equity: Large Cap'},
            {'Ticker': 'VOO', 'Name': 'Vanguard S&P 500', 'Sector': 'Equity: Large Cap'},
            {'Ticker': 'QQQ', 'Name': 'Invesco QQQ', 'Sector': 'Equity: Tech/Growth'},
            {'Ticker': 'IWM', 'Name': 'iShares Russell 2000', 'Sector': 'Equity: Small Cap'},
            {'Ticker': 'EFA', 'Name': 'iShares MSCI EAFE', 'Sector': 'Equity: Intl Developed'},
            {'Ticker': 'VEA', 'Name': 'Vanguard FTSE Developed', 'Sector': 'Equity: Intl Developed'},
            {'Ticker': 'VWO', 'Name': 'Vanguard Emerging Markets', 'Sector': 'Equity: Emerging Mkts'},
            
            # Bonds
            {'Ticker': 'AGG', 'Name': 'iShares Core US Aggregate Bond', 'Sector': 'Fixed Income: Broad'},
            {'Ticker': 'BND', 'Name': 'Vanguard Total Bond Market', 'Sector': 'Fixed Income: Broad'},
            {'Ticker': 'TLT', 'Name': 'iShares 20+ Year Treasury', 'Sector': 'Fixed Income: Long Gov'},
            {'Ticker': 'IEF', 'Name': 'iShares 7-10 Year Treasury', 'Sector': 'Fixed Income: Mid Gov'},
            {'Ticker': 'LQD', 'Name': 'iShares iBoxx $ Inv Grade Corp', 'Sector': 'Fixed Income: Corporate'},
            {'Ticker': 'HYG', 'Name': 'iShares iBoxx $ High Yield Corp', 'Sector': 'Fixed Income: High Yield'},
            {'Ticker': 'JNK', 'Name': 'SPDR Bloomberg High Yield Bond', 'Sector': 'Fixed Income: High Yield'},
            {'Ticker': 'SHY', 'Name': 'iShares 1-3 Year Treasury', 'Sector': 'Fixed Income: Short Gov'},

            # Commodities
            {'Ticker': 'GLD', 'Name': 'SPDR Gold Shares', 'Sector': 'Commodity: Precious Metals'},
            {'Ticker': 'IAU', 'Name': 'iShares Gold Trust', 'Sector': 'Commodity: Precious Metals'},
            {'Ticker': 'SLV', 'Name': 'iShares Silver Trust', 'Sector': 'Commodity: Precious Metals'},
            {'Ticker': 'USO', 'Name': 'United States Oil Fund', 'Sector': 'Commodity: Energy'},
            {'Ticker': 'UNG', 'Name': 'United States Natural Gas', 'Sector': 'Commodity: Energy'},

            # Sectors
            {'Ticker': 'XLE', 'Name': 'Energy Select Sector SPDR', 'Sector': 'Sector: Energy'},
            {'Ticker': 'XLF', 'Name': 'Financial Select Sector SPDR', 'Sector': 'Sector: Financials'},
            {'Ticker': 'XLK', 'Name': 'Technology Select Sector SPDR', 'Sector': 'Sector: Technology'},
            {'Ticker': 'XLV', 'Name': 'Health Care Select Sector SPDR', 'Sector': 'Sector: Health Care'},
            {'Ticker': 'XLI', 'Name': 'Industrial Select Sector SPDR', 'Sector': 'Sector: Industrials'},
            {'Ticker': 'XLP', 'Name': 'Consumer Staples Select Sector SPDR', 'Sector': 'Sector: Staples'},
            {'Ticker': 'XLU', 'Name': 'Utilities Select Sector SPDR', 'Sector': 'Sector: Utilities'},
            {'Ticker': 'XLY', 'Name': 'Consumer Discretionary Select Sector SPDR', 'Sector': 'Sector: Discretionary'},
            {'Ticker': 'XLB', 'Name': 'Materials Select Sector SPDR', 'Sector': 'Sector: Materials'},
            {'Ticker': 'XLRE', 'Name': 'Real Estate Select Sector SPDR', 'Sector': 'Sector: Real Estate'},
            {'Ticker': 'XLC', 'Name': 'Communication Services Select Sector SPDR', 'Sector': 'Sector: Comms'},

            # Industries / Thematic
            {'Ticker': 'SMH', 'Name': 'VanEck Semiconductor', 'Sector': 'Industry: Semi'},
            {'Ticker': 'SOXX', 'Name': 'iShares Semiconductor', 'Sector': 'Industry: Semi'},
            {'Ticker': 'IBB', 'Name': 'iShares Biotechnology', 'Sector': 'Industry: Biotech'},
            {'Ticker': 'XBI', 'Name': 'SPDR S&P Biotech', 'Sector': 'Industry: Biotech'},
            {'Ticker': 'KRE', 'Name': 'SPDR S&P Regional Banking', 'Sector': 'Industry: Banks'},
            {'Ticker': 'KBE', 'Name': 'SPDR S&P Bank', 'Sector': 'Industry: Banks'},
            {'Ticker': 'VNQ', 'Name': 'Vanguard Real Estate', 'Sector': 'Sector: Real Estate'},
            {'Ticker': 'GDX', 'Name': 'VanEck Gold Miners', 'Sector': 'Industry: Miners'},
            {'Ticker': 'GDXJ', 'Name': 'VanEck Junior Gold Miners', 'Sector': 'Industry: Miners'},

            # Leveraged
            {'Ticker': 'TQQQ', 'Name': 'ProShares UltraPro QQQ', 'Sector': 'Leveraged: Equity'},
            {'Ticker': 'SQQQ', 'Name': 'ProShares UltraPro Short QQQ', 'Sector': 'Leveraged: Equity Inverse'},
            {'Ticker': 'SOXL', 'Name': 'Direxion Daily Semi Bull 3X', 'Sector': 'Leveraged: Semi'},
            {'Ticker': 'SOXS', 'Name': 'Direxion Daily Semi Bear 3X', 'Sector': 'Leveraged: Semi Inverse'},
            {'Ticker': 'SPXL', 'Name': 'Direxion Daily S&P 500 Bull 3X', 'Sector': 'Leveraged: Equity'},
            {'Ticker': 'SPXS', 'Name': 'Direxion Daily S&P 500 Bear 3X', 'Sector': 'Leveraged: Equity Inverse'},
            {'Ticker': 'UPRO', 'Name': 'ProShares UltraPro S&P500', 'Sector': 'Leveraged: Equity'},
            {'Ticker': 'TNA', 'Name': 'Direxion Daily Small Cap Bull 3X', 'Sector': 'Leveraged: Small Cap'},
            {'Ticker': 'TZA', 'Name': 'Direxion Daily Small Cap Bear 3X', 'Sector': 'Leveraged: Small Cap Inverse'},
            {'Ticker': 'LABU', 'Name': 'Direxion Daily Biotech Bull 3X', 'Sector': 'Leveraged: Biotech'},
            
            # Other
            {'Ticker': 'ARKK', 'Name': 'ARK Innovation ETF', 'Sector': 'Active: Growth'},
            {'Ticker': 'JEPI', 'Name': 'JPMorgan Equity Premium Income', 'Sector': 'Active: Income'},
            {'Ticker': 'SCHD', 'Name': 'Schwab US Dividend Equity', 'Sector': 'Factor: Dividend'},
            {'Ticker': 'VIG', 'Name': 'Vanguard Dividend Appreciation', 'Sector': 'Factor: Dividend'},
            {'Ticker': 'VYM', 'Name': 'Vanguard High Dividend Yield', 'Sector': 'Factor: Dividend'},
        ]
        
        self.universe_df = pd.DataFrame(etf_data)
        self.tickers = self.universe_df['Ticker'].tolist()
        self.log(f"  Loaded {len(self.tickers)} ETFs.")
        return self.tickers

    def get_taiwan_top100_tickers(self):
        """
        Returns a DataFrame of Top Taiwan Stocks (High Trading Volume & Market Cap).
        Includes 0050/0056 Constituents and popular active stocks.
        Display Name includes Traditional Chinese.
        """
        data = [
            # Semiconductor (Wafer, IC Design, Packaging)
            {'Ticker': '2330.TW', 'Name': '台積電 (TSMC)', 'Sector': 'Semiconductors'},
            {'Ticker': '2454.TW', 'Name': '聯發科 (MediaTek)', 'Sector': 'Semiconductors'},
            {'Ticker': '2303.TW', 'Name': '聯電 (UMC)', 'Sector': 'Semiconductors'},
            {'Ticker': '3711.TW', 'Name': '日月光投控 (ASE)', 'Sector': 'Semiconductors'},
            {'Ticker': '3034.TW', 'Name': '聯詠 (Novatek)', 'Sector': 'Semiconductors'},
            {'Ticker': '2379.TW', 'Name': '瑞昱 (Realtek)', 'Sector': 'Semiconductors'},
            {'Ticker': '2408.TW', 'Name': '南亞科 (Nanya Tech)', 'Sector': 'Semiconductors'},
            {'Ticker': '6770.TW', 'Name': '力積電 (PSMC)', 'Sector': 'Semiconductors'},
            {'Ticker': '3443.TW', 'Name': '創意 (GUC)', 'Sector': 'Semiconductors'},
            {'Ticker': '3661.TW', 'Name': '世芯-KY (Alchip)', 'Sector': 'Semiconductors'},
            {'Ticker': '2449.TW', 'Name': '京元電子 (KYEC)', 'Sector': 'Semiconductors'},
            {'Ticker': '3231.TW', 'Name': '緯創 (Wistron)', 'Sector': 'Semiconductors'}, # AI Server
            
            # Electronics / Hardware / AI Server
            {'Ticker': '2317.TW', 'Name': '鴻海 (Foxconn)', 'Sector': 'Electronics'},
            {'Ticker': '2308.TW', 'Name': '台達電 (Delta)', 'Sector': 'Electronics'},
            {'Ticker': '2382.TW', 'Name': '廣達 (Quanta)', 'Sector': 'Computer'},
            {'Ticker': '2357.TW', 'Name': '華碩 (Asus)', 'Sector': 'Computer'},
            {'Ticker': '2353.TW', 'Name': '宏碁 (Acer)', 'Sector': 'Computer'},
            {'Ticker': '2324.TW', 'Name': '仁寶 (Compal)', 'Sector': 'Computer'},
            {'Ticker': '4938.TW', 'Name': '和碩 (Pegatron)', 'Sector': 'Computer'},
            {'Ticker': '2301.TW', 'Name': '光寶科 (Lite-On)', 'Sector': 'Electronics'},
            {'Ticker': '2356.TW', 'Name': '英業達 (Inventec)', 'Sector': 'Computer'},
            {'Ticker': '6669.TW', 'Name': '緯穎 (Wiwynn)', 'Sector': 'Computer'},
            {'Ticker': '2376.TW', 'Name': '技嘉 (Gigabyte)', 'Sector': 'Computer'},
            {'Ticker': '3017.TW', 'Name': '奇鋐 (AVC)', 'Sector': 'Electronics'},
            
            # Optoelectronics / Panel
            {'Ticker': '3481.TW', 'Name': '群創 (Innolux)', 'Sector': 'Electronics'},
            {'Ticker': '2409.TW', 'Name': '友達 (AUO)', 'Sector': 'Electronics'},
            {'Ticker': '6116.TW', 'Name': '彩晶 (HannStar)', 'Sector': 'Electronics'},
            
            # PCB / Components
            {'Ticker': '3037.TW', 'Name': '欣興 (Unimicron)', 'Sector': 'Components'},
            {'Ticker': '2313.TW', 'Name': '華通 (Compeq)', 'Sector': 'Components'},
            {'Ticker': '4958.TW', 'Name': '臻鼎-KY (Zhen Ding)', 'Sector': 'Components'},
            {'Ticker': '2327.TW', 'Name': '國巨 (Yageo)', 'Sector': 'Components'},
            
            # Financials
            {'Ticker': '2881.TW', 'Name': '富邦金 (Fubon)', 'Sector': 'Financials'},
            {'Ticker': '2882.TW', 'Name': '國泰金 (Cathay)', 'Sector': 'Financials'},
            {'Ticker': '2891.TW', 'Name': '中信金 (CTBC)', 'Sector': 'Financials'},
            {'Ticker': '2886.TW', 'Name': '兆豐金 (Mega)', 'Sector': 'Financials'},
            {'Ticker': '2884.TW', 'Name': '玉山金 (E.Sun)', 'Sector': 'Financials'},
            {'Ticker': '2885.TW', 'Name': '元大金 (Yuanta)', 'Sector': 'Financials'},
            {'Ticker': '5880.TW', 'Name': '合庫金 (Cooperative)', 'Sector': 'Financials'},
            {'Ticker': '2892.TW', 'Name': '第一金 (First)', 'Sector': 'Financials'},
            {'Ticker': '2880.TW', 'Name': '華南金 (Hua Nan)', 'Sector': 'Financials'},
            {'Ticker': '2883.TW', 'Name': '凱基金 (CDIB)', 'Sector': 'Financials'},
            {'Ticker': '2887.TW', 'Name': '台新金 (Taishin)', 'Sector': 'Financials'},
            {'Ticker': '2888.TW', 'Name': '新光金 (Shin Kong)', 'Sector': 'Financials'},
            {'Ticker': '5871.TW', 'Name': '中租-KY (Chailease)', 'Sector': 'Financials'},

            # Shipping / Transport
            {'Ticker': '2603.TW', 'Name': '長榮 (Evergreen)', 'Sector': 'Transportation'},
            {'Ticker': '2609.TW', 'Name': '陽明 (Yang Ming)', 'Sector': 'Transportation'},
            {'Ticker': '2615.TW', 'Name': '萬海 (Wan Hai)', 'Sector': 'Transportation'},
            {'Ticker': '2610.TW', 'Name': '華航 (China Air)', 'Sector': 'Transportation'},
            {'Ticker': '2618.TW', 'Name': '長榮航 (EVA Air)', 'Sector': 'Transportation'},

            # Old Economy / Materials / Cement
            {'Ticker': '2002.TW', 'Name': '中鋼 (CSC)', 'Sector': 'Materials'},
            {'Ticker': '1605.TW', 'Name': '華新 (Walsin)', 'Sector': 'Materials'},
            {'Ticker': '1101.TW', 'Name': '台泥 (Taiwan Cement)', 'Sector': 'Materials'},
            {'Ticker': '1102.TW', 'Name': '亞泥 (Asia Cement)', 'Sector': 'Materials'},
            {'Ticker': '1301.TW', 'Name': '台塑 (Formosa)', 'Sector': 'Materials'},
            {'Ticker': '1303.TW', 'Name': '南亞 (Nan Ya)', 'Sector': 'Materials'},
            {'Ticker': '1326.TW', 'Name': '台化 (Formosa Chem)', 'Sector': 'Materials'},
            {'Ticker': '6505.TW', 'Name': '台塑化 (Formosa Petro)', 'Sector': 'Materials'},
            {'Ticker': '1504.TW', 'Name': '東元 (TECO)', 'Sector': 'Industrial'},
            {'Ticker': '1216.TW', 'Name': '統一 (Uni-President)', 'Sector': 'Consumer Staples'},
            
            # Construction / Other Interest
            {'Ticker': '5519.TW', 'Name': '龍大 (Long Da)', 'Sector': 'Construction'}, 
            {'Ticker': '2546.TW', 'Name': '根基 (Kedge)', 'Sector': 'Construction'},
            {'Ticker': '9945.TW', 'Name': '潤泰新 (Ruentex)', 'Sector': 'Construction'},
            {'Ticker': '3045.TW', 'Name': '台灣大 (Taiwan Mobile)', 'Sector': 'Communication'},
            {'Ticker': '2412.TW', 'Name': '中華電 (Chunghwa)', 'Sector': 'Communication'},
            {'Ticker': '4904.TW', 'Name': '遠傳 (Far EasTone)', 'Sector': 'Communication'},
            
            # ETFs (for ref)
            {'Ticker': '0050.TW', 'Name': '元大台灣50', 'Sector': 'ETF'},
            {'Ticker': '0056.TW', 'Name': '元大高股息', 'Sector': 'ETF'},
        ]
        
        self.universe_df = pd.DataFrame(data)
        self.tickers = self.universe_df['Ticker'].tolist()
        self.log(f"[INFO] Loaded {len(self.universe_df)} Taiwan stocks/ETFs.")
        return self.universe_df

    def get_taiwan_high_yield_tickers(self):
        self.log("[INFO] Loading 'TW Dividend >5%' list (Static Source: Goodinfo)...")
        try:
            with open("taiwan_high_yield.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            self.universe_df = pd.DataFrame(data)
            self.tickers = self.universe_df['Ticker'].tolist()
            self.log(f"[INFO] Loaded {len(self.universe_df)} High Yield Stocks.")
            return self.universe_df
        except Exception as e:
            self.log(f"[ERROR] Failed to load 'taiwan_high_yield.json': {e}")
            self.tickers = []
            return pd.DataFrame(columns=['Ticker', 'Name', 'Sector'])

    def get_data_status(self, universe="sp500"):
        DATA_DIR = "data"
        csv_filename = f"{universe}_data.csv"
        csv_filename = "".join([c for c in csv_filename if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
        csv_path = os.path.join(DATA_DIR, csv_filename)
        
        if os.path.exists(csv_path):
            try:
                # Just read header to be fast? Or stats
                stats = os.stat(csv_path)
                last_mod = datetime.datetime.fromtimestamp(stats.st_mtime)
                
                # To get accurate ticker count and last date without reading full file efficiently:
                # We can just read the first few lines or headers.
                # But for now, let's load it if it's not too huge, or relies on 'self.data' if loaded.
                
                status = {
                    "exists": True,
                    "last_modified": last_mod,
                    "path": csv_path,
                    "size_mb": round(stats.st_size / (1024*1024), 2)
                }
                return status
            except Exception as e:
                 return {"exists": True, "error": str(e)}
        else:
            return {"exists": False}

    def fetch_data(self, universe="sp500", lookback_days=1825, force_refresh=False, local_only=False): # Added local_only
        if hasattr(self, 'logger_callback') and self.logger_callback:
            self.logger_callback(f"Fetching data for universe: {universe}")
        
        # Update State
        self.current_universe = universe

        if universe == "sp500":
            self.get_sp500_tickers()
        elif universe == "nasdaq100":
            self.get_nasdaq100_tickers()
        elif universe == "etf_top":
            self.get_top_etf_tickers()
        elif universe == "taiwan100":
            self.get_taiwan_top100_tickers()
        elif universe == "tw_high_yield":
            self.get_taiwan_high_yield_tickers()
        elif universe == "watchlist":
            self.log("[INFO] Using Custom/Watchlist Tickers...")
            # assumed self.tickers set
        else:
             self.get_sp500_tickers()
             
        # self.tickers is now set
            
        # --- DATA CACHING LOGIC ---
        DATA_DIR = "data"
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
            
        csv_filename = f"{universe}_data.csv"
        csv_filename = "".join([c for c in csv_filename if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
        csv_path = os.path.join(DATA_DIR, csv_filename)
        
        existing_data = None
        last_date = None
        
        # Try Loading Local
        if os.path.exists(csv_path):
            try:
                self.log(f"  Loading local database: {csv_path}...")
                existing_data = pd.read_csv(csv_path, header=[0, 1], index_col=0, parse_dates=True)
                if not existing_data.empty:
                    last_date = existing_data.index[-1]
                    self.log(f"  Database loaded. Last Date: {last_date.date()}. Rows: {len(existing_data)}")
            except Exception as e:
                self.log(f"  [ERROR] Corrupt database file: {e}")
                existing_data = None

        if local_only:
            if existing_data is not None:
                self.data = existing_data
                self.log("  [Mode] Offline: Using local data only.")
            else:
                self.log("  [Mode] Offline: No local data found! Please running 'Update Database' first.")
                self.data = None
            return

        # ... (Download Logic for Online Mode) ...
        
        # Calculate start date
        if existing_data is not None and last_date is not None and not force_refresh:
             # Start from next day
             start_date_ts = last_date + datetime.timedelta(days=1)
             start_date = start_date_ts.strftime('%Y-%m-%d')
             self.log(f"  [Mode] Update: Downloading new data from {start_date}...")
        else:
            # Full Download
            start_date = (datetime.datetime.now() - datetime.timedelta(days=lookback_days)).strftime('%Y-%m-%d')
            self.log(f"  [Mode] Full Download: Fetching start {start_date}...")


        end_date = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # Check if up to date
        if existing_data is not None and start_date >= end_date:
            self.log("  Data is up to date. Using cache.")
            self.data = existing_data
            return

        # Download new data
        try:
            # Chunking to avoid [Errno 22] and improve stability
            chunk_size = 10
            new_data_list = []
            
            for i in range(0, len(self.tickers), chunk_size):
                chunk = self.tickers[i:i + chunk_size]
                try:
                    self.log(f"  Downloading chunk {i//chunk_size + 1}/{len(self.tickers)//chunk_size + 1}: {chunk}")
                    # threads=False is CRITICAL on Windows to prevent [Errno 22] Invalid Argument
                    chunk_data = yf.download(chunk, start=start_date, end=end_date, group_by='ticker', progress=False, threads=False)
                    
                    if chunk_data is not None and not chunk_data.empty:
                         new_data_list.append(chunk_data)
                         
                except Exception as e:
                    self.log(f"  [WARNING] Failed to download chunk {chunk}: {e}")
                    continue

            if not new_data_list:
                self.log("  No new data downloaded (all chunks failed or empty).")
                self.data = existing_data
            else:
                # Concatenate all chunks along columns (axis=1) if they have different tickers?
                # yf.download(group_by='ticker') returns MultiIndex columns (Ticker, OHLC)
                # We need to concat carefully.
                # Actually, if we concat along axis=1, we merge tickers.
                
                try:
                    if len(new_data_list) == 1:
                        new_data = new_data_list[0]
                    else:
                        new_data = pd.concat(new_data_list, axis=1)
                    
                    self.log(f"  Downloaded total data shape: {new_data.shape}")
    
                    if existing_data is not None:
                        # Combine with existing
                        # Note: We need to handle overlapping columns if any.
                        # pd.combine_first or concat. 
                        # Simplest is to concat rows and drop duplicates, but tickers are columns.
                        
                        # We are fetching NEW rows (dates).
                        # But since we chunked the columns (tickers), 'new_data' has full width (all tickers)? 
                        # No, pd.concat(axis=1) joins columns.
                        
                        # If existing_data has tickers A,B and new_data has tickers A,B but new dates...
                        # Wait, we download ALL valid tickers for the new date range.
                        # So new_data has (NewDates, AllTickers).
                        
                        # So we append new_data to existing_data (axis=0).
                        combined_data = pd.concat([existing_data, new_data], axis=0) 
                        combined_data = combined_data[~combined_data.index.duplicated(keep='last')]
                        combined_data.sort_index(inplace=True)
                        self.data = combined_data
                    else:
                        self.data = new_data

                    # Save back to CSV
                    self.log(f"  Saving database to {csv_path}...")
                    self.data.to_csv(csv_path)

                except Exception as merge_e:
                    self.log(f"  [ERROR] Failed to merge/save data: {merge_e}")
                    self.data = existing_data # Fallback
                
        except Exception as e:
            self.log(f"  Failed to download/update data: {e}")
            self.data = existing_data # Fallback to what we have

    def calculate_indicators(self, df):
        # Ensure sufficient data
        if len(df) < self.sma_filter:
            return None
        
        # Calculate WVF
        # WVF = (Highest(Close, n) - Low) / Highest(Close, n) * 100
        period = self.lookback_period
        
        # We need to handle cases where 'Close' or 'Low' might be MultiIndex or Single Index depending on how yf returns it
        # When group_by='ticker', df is just the OHLC for that ticker
        
        try:
            close_prices = df['Close']
            low_prices = df['Low']
            
            # Highest Close over Lookback
            highest_close = close_prices.rolling(window=period).max()
            
            wvf = ((highest_close - low_prices) / highest_close) * 100
            
            # Bollinger Bands on WVF
            wvf_sma = wvf.rolling(window=self.bb_length).mean()
            wvf_std = wvf.rolling(window=self.bb_length).std()
            
            upper_band = wvf_sma + (self.bb_std * wvf_std)
            # lower_band = wvf_sma - (self.bb_std * wvf_std) # Not needed for signal
            
            # 200 SMA on Price
            sma200 = close_prices.rolling(window=self.sma_filter).mean()
            
            # Volume Moving Average (30 days) for liquidity check
            # Use Dollar Volume = Close * Volume
            # Note: yfinance Volume can be float
            dollar_vol = close_prices * df['Volume']
            avg_dollar_vol = dollar_vol.rolling(window=30).mean()
            
            # --- Supertrend (10, 3) Calculation ---
            high = df['High']
            low = df['Low']
            close = df['Close']
            
            # TR Calculation
            tr1 = high - low
            tr2 = (high - close.shift()).abs()
            tr3 = (low - close.shift()).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # ATR (10)
            atr = tr.rolling(window=10).mean()
            
            # Supertrend Logic
            factor = 3
            basic_upper = (high + low) / 2 + factor * atr
            basic_lower = (high + low) / 2 - factor * atr
            
            final_upper = pd.Series(index=df.index, dtype='float64')
            final_lower = pd.Series(index=df.index, dtype='float64')
            supertrend = pd.Series(index=df.index, dtype='float64')
            trend = pd.Series(index=df.index, dtype='int64') # 1 for Up, -1 for Down
            
            # Initialize (Iterative loop is necessary for Supertrend)
            # Use 0 for initial generic values to avoid errors, correct calculation starts after ATR exists
            curr_trend = 1
            last_final_upper = basic_upper.iloc[0]
            last_final_lower = basic_lower.iloc[0]
            last_close = close.iloc[0]
             
            for i in range(len(df)):
                if np.isnan(atr.iloc[i]):
                    final_upper.iloc[i] = np.nan
                    final_lower.iloc[i] = np.nan
                    supertrend.iloc[i] = np.nan
                    trend.iloc[i] = 1
                    continue
                
                curr_basic_upper = basic_upper.iloc[i]
                curr_basic_lower = basic_lower.iloc[i]
                curr_close = close.iloc[i]
                
                # Final Upper Band
                if (curr_basic_upper < last_final_upper) or (last_close > last_final_upper):
                    curr_final_upper = curr_basic_upper
                else:
                    curr_final_upper = last_final_upper
                
                # Final Lower Band
                if (curr_basic_lower > last_final_lower) or (last_close < last_final_lower):
                    curr_final_lower = curr_basic_lower
                else:
                    curr_final_lower = last_final_lower
                
                # Update Trend
                if curr_trend == 1:
                    if curr_close < curr_final_lower:
                        curr_trend = -1
                else:
                    if curr_close > curr_final_upper:
                        curr_trend = 1
                
                final_upper.iloc[i] = curr_final_upper
                final_lower.iloc[i] = curr_final_lower
                trend.iloc[i] = curr_trend
                
                if curr_trend == 1:
                    supertrend.iloc[i] = curr_final_lower
                else:
                    supertrend.iloc[i] = curr_final_upper
                
                last_final_upper = curr_final_upper
                last_final_lower = curr_final_lower
                last_close = curr_close

            # Combine into a DataFrame
            result = pd.DataFrame({
                'Open': df['Open'],
                'Close': close_prices,
                'SMA200': sma200,
                'WVF': wvf,
                'UpperBB': upper_band,
                'AvgDollarVol': avg_dollar_vol,
                'Supertrend': supertrend,
                'SupertrendTrend': trend
            })
            
            return result
            
        except Exception as e:
            # print(f"Error calculating indicators: {e}")
            return None

    def run_scan(self, scan_date=None, local_only=True):
        if self.data is None or len(self.data) == 0:
            self.log(f"No data in memory. Attempting load for {self.current_universe}...")
            self.fetch_data(universe=self.current_universe, local_only=local_only)

        if self.data is None or self.data.empty:
             self.log("[ERROR] Cannot run scan: No data available. Please update database.")
             return pd.DataFrame()

        self.log(f"[INFO] Processing {len(self.tickers)} tickers...")
        if scan_date:
            self.log(f"[INFO] Time Machine Mode: Scanning as of {scan_date}")
            # Ensure scan_date is datetime or timestamp compatible
            scan_date = pd.to_datetime(scan_date)
        else:
            scan_date = pd.Timestamp.now()
        
        candidates = []
        
        # We need to get the latest available date's data for all valid tickers
        valid_tickers_data = {}
        results = []
        
        for ticker in self.tickers:
            try:
                if ticker not in self.data.columns.levels[0]:
                    continue
                    
                df_ticker = self.data[ticker].dropna()
                if df_ticker.empty:
                    continue
                
                indicators = self.calculate_indicators(df_ticker)
                if indicators is None or indicators.empty:
                    continue
                
                # Handling Time Machine Date logic with 1-Day Lag
                # T = scan_date (Action Date / Entry Date)
                # T-1 = Signal Date
                
                # Filter data up to scan_date to simulate "what we knew" (but we need T+5 for validation later)
                # Actually, for signal detection, we only need up to scan_date.
                
                # Get index location of scan_date
                # We need to find the specific row for scan_date. if scan_date is a weekend, we might need the last trading day.
                # simpler: use searchsorted or similar, or just boolean indexing.
                
                past_data = indicators[indicators.index <= scan_date]
                if len(past_data) < 2:
                    continue
                
                # Row T (Today/Action Day)
                # If scan_date is strictly today/now, the last row might be incomplete or just closed.
                # Ideally T is the last closed bar if we run this after market.
                # If we assume "Time Machine" picks a date, that date is T.
                
                # Checking for Dual States: 
                # 1. Actionable Setup (Signal on T-1) -> Buy on Open of T.
                # 2. Developing Setup (Signal on T) -> Watchlist (Wait for Close).
                
                row_t = past_data.iloc[-1]
                date_t = past_data.index[-1]
                
                row_t_minus_1 = past_data.iloc[-2]
                date_t_minus_1 = past_data.index[-2]
                
                # Logic A: Actionable (Lagged)
                signal_t_minus_1 = (row_t_minus_1['WVF'] > row_t_minus_1['UpperBB']) and \
                                   (row_t_minus_1['Close'] > row_t_minus_1['SMA200'])
                
                # Debug
                # self.log(f"DEBUG {ticker}: Date T={date_t}, T-1={date_t_minus_1}")
                # self.log(f"  T-1 Signal: {signal_t_minus_1} (WVF={row_t_minus_1['WVF']:.2f}, BB={row_t_minus_1['UpperBB']:.2f})")

                # Logic B: Developing (Fresh)
                signal_t = (row_t['WVF'] > row_t['UpperBB']) and \
                           (row_t['Close'] > row_t['SMA200'])
                
                candidate_info = {}
                
                if signal_t_minus_1:
                    # It's an actionable buy today
                    status = "ACTIONABLE (Buy)"
                    signal_date = date_t_minus_1
                    signal_row = row_t_minus_1
                    entry_price = row_t['Open']
                    
                    # 5-Day Validation (Forward from T)
                    future_data = indicators[indicators.index > scan_date]
                    if len(future_data) >= 5:
                        exit_price = future_data.iloc[4]['Close']
                        pct_return = ((exit_price - entry_price) / entry_price) * 100
                    elif len(future_data) > 0:
                        exit_price = future_data.iloc[-1]['Close']
                        pct_return = ((exit_price - entry_price) / entry_price) * 100
                    else:
                        pct_return = None
                        
                    candidate_info = {
                        'Status': status,
                        'Signal Date': signal_date,
                        'Action Date': date_t,
                        'Entry Price': entry_price,
                        'WVF': signal_row['WVF'],
                        'UpperBB': signal_row['UpperBB'],
                        '5-Day Return %': pct_return,
                        'Volume(M)': row_t['AvgDollarVol'] / row_t['Close'] / 1e6
                    }
                    
                elif signal_t:
                    # It's a new signal forming today
                    status = "WATCH (New Signal)"
                    signal_date = date_t
                    signal_row = row_t
                    entry_price = None # Future entry
                    pct_return = None
                    
                    candidate_info = {
                        'Status': status,
                        'Signal Date': signal_date,
                        'Action Date': "Next Trading Day",
                        'Entry Price': None,
                        'WVF': signal_row['WVF'],
                        'UpperBB': signal_row['UpperBB'],
                        '5-Day Return %': None,
                        'Volume(M)': row_t['AvgDollarVol'] / row_t['Close'] / 1e6
                    }

                if candidate_info:
                    results.append({
                        'Ticker': ticker,
                        'Status': candidate_info['Status'],
                        'Signal Date': candidate_info['Signal Date'].strftime('%Y-%m-%d'),
                        'Action Date': candidate_info['Action Date'].strftime('%Y-%m-%d') if isinstance(candidate_info['Action Date'], (pd.Timestamp, datetime.date)) else candidate_info['Action Date'],
                        'Entry Price': round(candidate_info['Entry Price'], 2) if candidate_info['Entry Price'] else None,
                        'WVF': round(candidate_info['WVF'], 2),
                        'UpperBB': round(candidate_info['UpperBB'], 2),
                        '5-Day Return %': round(candidate_info['5-Day Return %'], 2) if candidate_info['5-Day Return %'] is not None else None,
                        'Volume(M)': round(candidate_info['Volume(M)'], 2)
                    })
                
            except KeyError as e:
                self.log(f"KeyError processing {ticker}: {e}")
                continue
            except Exception as e:
                self.log(f"Error processing {ticker}: {e}")
                continue

        # Sort by Status (Actionable first) then Liquidity?
        # Let's just return DF and let user sort.
        
        self.log(f"[INFO] Found {len(results)} candidates...")
        
        return pd.DataFrame(results)

if __name__ == "__main__":
    scanner = CMWilliamsVixFixScanner()
    results = scanner.run_scan()
    
    if not results.empty:
        print("\n[RESULT] Strategy Candidates for Today:")
        print(results.to_string(index=False))
        # Save to CSV
        results.to_csv("vix_fix_candidates.csv", index=False)
        print("\nSaved to 'vix_fix_candidates.csv'")
    else:
        print("\n[RESULT] No candidates found matching the criteria.")
