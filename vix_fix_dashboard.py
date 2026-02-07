import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os
import json
import google.generativeai as genai
import yfinance as yf
import importlib
import re
import requests

# Add current directory to path to import the scanner
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import cm_williams_vix_fix

# Ensure we are running from the script's directory so we can find watchlist.json
try:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
except:
    pass

# Force reload to ensure latest code changes are picked up
importlib.reload(cm_williams_vix_fix)
from cm_williams_vix_fix import CMWilliamsVixFixScanner

st.set_page_config(page_title="CM Williams Vix Fix Scanner", layout="wide")

st.title("CM Williams Vix Fix Scanner v1.4 (Offline-First) 📊")
st.markdown("""
**Strategy Logic:**
1.  **Vix Fix (WVF):** Synthetic volatility indicator based on Low vs Highest Close.
2.  **Signal:** WVF Crosses ABOVE Upper Bollinger Band (Statistical Extreme).
3.  **Filter:** Price ABOVE 200-day SMA (Bullish Trend Regime).
""")

# Watch List Persistence
WATCHLIST_FILE = "watchlist.json"

DEFAULT_WATCHLISTS = {
    "Default": ["AAPL", "NVDA", "TSLA", "MSFT"],
    "Watchlist 2": [],
    "Watchlist 3": [],
    "Watchlist 4": [],
    "Watchlist 5": []
}

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r") as f:
                data = json.load(f)
                # Migration: if legacy list, wrap in dict
                if isinstance(data, list):
                    new_data = DEFAULT_WATCHLISTS.copy()
                    new_data["Default"] = data
                    return new_data
                # Ensure all keys exist - merge with default keys if missing
                # But don't overwrite user data
                final_data = DEFAULT_WATCHLISTS.copy()
                final_data.update(data)
                return final_data
        except Exception:
            return DEFAULT_WATCHLISTS.copy()
    return DEFAULT_WATCHLISTS.copy()

def save_watchlist(tickers):
    try:
        with open(WATCHLIST_FILE, "w") as f:
            json.dump(tickers, f)
    except Exception as e:
        st.sidebar.error(f"Watchlist Error: {e}")

st.sidebar.markdown("---")
# API Key Input in Sidebar (Secrets or Manual)
# Try loading from secrets first
default_gemini = st.secrets.get("GEMINI_API_KEY", "")
default_pplx = st.secrets.get("PERPLEXITY_API_KEY", "")

api_key = st.sidebar.text_input("Gemini API Key", value=default_gemini, type="password", help="Add to .streamlit/secrets.toml for auto-load")
pplx_api_key = st.sidebar.text_input("Perplexity API Key", value=default_pplx, type="password", help="Optional fallback")

# Helper for Perplexity AI (Fallback)
def generate_perplexity_report(api_key, system_prompt):
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Perplexity 'sonar-pro' works well. We send the whole system prompt as user content
    # or split it. Given the prompt structure, sending as 'user' message is safest for standard chat.
    payload = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "user", 
                "content": system_prompt
            }
        ]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'], "Perplexity (sonar-pro)"
        else:
            return f"Perplexity Error {response.status_code}: {response.text}", "Error"
    except Exception as e:
        return f"Perplexity Request Failed: {str(e)}", "Error"

# Helper for AI Generation with Fallback
def generate_ai_report(gemini_api_key, perplexity_api_key, prompt):
    # 1. Try Gemini First
    if gemini_api_key:
        genai.configure(api_key=gemini_api_key)
        models = [
            'gemini-2.0-flash', 
            'gemini-2.0-flash-lite',
            'gemini-flash-latest',
            'gemini-1.5-flash',
            'gemini-pro'
        ]
        
        errors = []
        for model_name in models:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                if response.text:
                    return response.text, f"Gemini ({model_name})"
            except Exception as e:
                errors.append(f"{model_name}: {str(e)}")
                # If 429, we might want to break immediately to fallback? 
                # But treating all errors same for simplicity.
                continue
    else:
        errors = ["Gemini Key missing."]

    # 2. Fallback to Perplexity
    if perplexity_api_key:
        # st.toast("Gemini failed, switching to Perplexity AI...") # Can't use streamlit here easily if inside cache? 
        # Actually this function handles the call. We can return the result.
        return generate_perplexity_report(perplexity_api_key, prompt)

    # If we get here, all failed
    error_msg = "\n".join(errors)
    raise Exception(f"Gemini failed (and no Perplexity Key provided).\nDetails:\n{error_msg}")

# Initialize Session State for Logs
if 'scan_logs' not in st.session_state:
    st.session_state['scan_logs'] = []

def log_callback(msg):
    st.session_state['scan_logs'].append(msg)

# Initialize Scanner Logic
@st.cache_resource
def get_scanner_v14():
    import cm_williams_vix_fix
    importlib.reload(cm_williams_vix_fix)
    from cm_williams_vix_fix import CMWilliamsVixFixScanner
    return CMWilliamsVixFixScanner(logger_callback=log_callback)

scanner = get_scanner_v14()

# Helper for Taiwan Names
@st.cache_data
def get_taiwan_names_map():
    temp_scanner = CMWilliamsVixFixScanner()
    # Merge Top 100 and High Yield lists
    df1 = temp_scanner.get_taiwan_top100_tickers()
    d1 = dict(zip(df1['Ticker'], df1['Name']))
    
    df2 = temp_scanner.get_taiwan_high_yield_tickers()
    d2 = dict(zip(df2['Ticker'], df2['Name']))
    
    # Merge
    return {**d1, **d2}

# Scanner Settings
st.sidebar.header("Scanner Settings")

# Universe Selection
universe = st.sidebar.selectbox("Universe", ["Choose Universe...", "S&P 500", "Nasdaq 100", "Top ETFs", "Taiwan Top 100", "TW Dividend >5%"], index=0)

# Reactive Universe Loading
if universe != "Choose Universe..." and ('loaded_universe' not in st.session_state or st.session_state['loaded_universe'] != universe):
    with st.spinner(f"Loading {universe} constituents..."):
        if universe == "S&P 500":
            scanner.get_sp500_tickers()
        elif universe == "Nasdaq 100":
            scanner.get_nasdaq100_tickers()
        elif universe == "Top ETFs":
            scanner.get_top_etf_tickers()
        elif universe == "Taiwan Top 100":
            scanner.get_taiwan_top100_tickers()
        elif universe == "TW Dividend >5%":
            scanner.get_taiwan_high_yield_tickers()
        st.session_state['loaded_universe'] = universe

top_n = st.sidebar.number_input("Scan Top N Liquid", min_value=10, max_value=500, value=100, step=10)

scan_date = st.sidebar.date_input("Time Machine Date", value=pd.Timestamp.now().date())

# --- ACTION BUTTONS ---
st.sidebar.markdown("---")
# Data Management UI
st.sidebar.subheader("💾 Data Management")

universe_map = {
    "S&P 500": "sp500", 
    "Nasdaq 100": "nasdaq100",
    "Top ETFs": "etf_top",
    "Taiwan Top 100": "taiwan100",
    "TW Dividend >5%": "tw_high_yield"
}
current_univ_key = universe_map.get(universe, "sp500")

# Show Status
try:
    status = scanner.get_data_status(current_univ_key)
    if status.get("exists"):
        st.sidebar.success(f"Data Found ({status.get('size_mb')}MB)")
        st.sidebar.caption(f"Last Mod: {status.get('last_modified')}")
    else:
        st.sidebar.warning("No Local Data Found")
except:
    pass

update_btn = st.sidebar.button("🔄 Update Database", help="Downloads fresh data from Yahoo Finance. This may take a minute.")

st.sidebar.markdown("---")
st.sidebar.subheader("🚀 Scanner")
col_btn1, col_btn2 = st.sidebar.columns(2)
run_btn = col_btn1.button("Run Scan", type="primary", help="Instantly scans local data.")
watch_scan_btn = col_btn2.button("Scan Watchlist")
st.sidebar.markdown("---")

# Specific Ticker Input
ticker_input = st.sidebar.text_input("Specific Ticker (Optional)", help="Leave empty to scan Universe")

# Watchlist Logic
st.sidebar.markdown("---")
st.sidebar.subheader("👀 Watchlists")

# Load Watchlists
watchlists = load_watchlist()
wl_names = list(watchlists.keys())

# Watchlist Selector
selected_wl_name = st.sidebar.selectbox("Select Watchlist", wl_names, index=0)
active_watchlist_tickers = watchlists.get(selected_wl_name, [])

# Watchlist Editor
wl_text = st.sidebar.text_area("Edit Tickers (Comma/Newline)", value=",".join(active_watchlist_tickers), height=100)
    
# Save Button
if st.sidebar.button("💾 Save Watchlist"):
    # Parse input
    new_tickers = [t.strip().upper() for t in wl_text.replace('\n', ',').split(',') if t.strip()]
    watchlists[selected_wl_name] = new_tickers
    save_watchlist(watchlists)
    st.sidebar.success(f"Saved {selected_wl_name} ({len(new_tickers)} tickers)!")
    # Update active list immediately for this run
    active_watchlist_tickers = new_tickers
else:
    # Update active list from text area purely for temporary usage if user didn't save?
    # Better to stick to saved state or parse text area if we want live edit without save.
    # For simplicity, let's use the text area content as the source of truth if 'Run Scan' is clicked?
    # Actually, let's keep it simple: Use saved state.
    pass

target_tickers = []
target_tickers_msg = ""
should_run = False
target_univ = "sp500" # Default

# ACTION LOGIC

# 1. Update Database Action
if update_btn:
    st.session_state['scan_logs'] = []
    if universe == "Choose Universe...":
         st.error("Please choose a Universe to update.")
    else:
         with st.spinner(f"Updating database for {universe} (Chunks of 10)..."):
             scanner.fetch_data(universe=current_univ_key, local_only=False)
             st.success(f"Update Complete for {universe}!")

# 2. Run Scan Action
if run_btn:
    st.session_state['scan_logs'] = [] # Clear logs on run
    
    if universe == "Choose Universe...":
        st.error("⚠️ Please select a valid Universe (e.g., S&P 500, Taiwan Top 100) or use a Watchlist.")
    else:
        should_run = True
        target_univ = current_univ_key
    
    scanner.top_n_volume = top_n
    
    if ticker_input:
        target_tickers = [t.strip().upper() for t in ticker_input.split(',')]
        scanner.tickers = target_tickers
        target_tickers_msg = f"{', '.join(target_tickers)}"
        target_univ = "watchlist" # Custom
    else:
        # Tickers are already loaded by reactive logic above
        target_tickers_msg = f"{universe} (Top {top_n})"

if watch_scan_btn:
    should_run = True # As above

    st.session_state['scan_logs'] = []
    
    if selected_wl_name == "Default":
        # Hybrid Mode: Fallback to selected Universe
        universe_map = {
            "S&P 500": "sp500", 
            "Nasdaq 100": "nasdaq100",
            "Top ETFs": "etf_top",
            "Taiwan Top 100": "taiwan100"
        }
        target_univ = universe_map.get(universe, "sp500")
        scanner.top_n_volume = top_n
        target_tickers_msg = f"{universe} (Scan)"
    else:
        # Standard Watchlist Scan
        target_tickers = active_watchlist_tickers
        
        if not target_tickers:
            st.error(f"{selected_wl_name} is empty!")
            should_run = False
        else:
            scanner.tickers = target_tickers
            target_tickers_msg = f"{selected_wl_name}"
            scanner.top_n_volume = len(target_tickers) + 10
            target_univ = "watchlist"

if should_run:
    with st.spinner(f"Scanning {target_tickers_msg} (Local Data) as of {scan_date}..."):
        # Explicitly fetch variables if needed, OR trust scanner.tickers is set.
        # If target_univ is NOT watchlist, we should ensure fetch logic runs for correct universe
        if target_univ != "watchlist":
             # LOCAL ONLY FETCH (For big universes like SP500, we don't auto-download on every scan)
             scanner.fetch_data(universe=target_univ, local_only=True)
        else:
             # WATCHLIST: Always allow download because it's usually small and dynamic
             scanner.fetch_data(universe="watchlist", local_only=False)
             
        # scanner.data = None # No longer needed if we called fetch_data above? 
        # Actually fetch_data populates self.data.
        
        results = scanner.run_scan(scan_date=pd.to_datetime(scan_date), local_only=True)
        st.session_state['scan_results'] = results
        st.session_state['scan_complete'] = True
        st.session_state['scan_date'] = scan_date
        st.session_state['universe_name'] = target_tickers_msg

# Layout
tab_results, tab_universe, tab_ai_details, tab_logs = st.tabs(["📊 Results", "🌍 Universe", "🧠 AI Analysis", "📝 Scan Logs"])

with tab_logs:
    st.subheader("Process Logs")
    if st.session_state['scan_logs']:
        log_text = "\n".join(st.session_state['scan_logs'])
        st.text_area("Log Output", value=log_text, height=300)
    else:
        st.info("No logs generated yet.")

with tab_universe:
    st.subheader("Universe Composition")
    if scanner.universe_df is not None and not scanner.universe_df.empty:
        univ_df = scanner.universe_df
        
        col_u1, col_u2 = st.columns([1, 1])
        
        with col_u1:
            st.markdown("### Sector Distribution")
            if 'Sector' in univ_df.columns:
                sector_counts = univ_df['Sector'].value_counts()
                fig_pie = go.Figure(data=[go.Pie(labels=sector_counts.index, values=sector_counts.values, hole=.3)])
                fig_pie.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=350)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.warning("No sector data available.")
                
        with col_u2:
            st.markdown("### Universe Constituents")
            st.dataframe(univ_df, height=350, use_container_width=True)
            
        st.markdown(f"**Total Securities:** {len(univ_df)}")
        
    else:
        st.info("No universe data loaded. Click 'Run Live Scan' to load a universe.")

with tab_ai_details:
    st.subheader("Full AI Valuation Report")
    sel_ticker = st.session_state.get('selected_ticker')
    if sel_ticker and 'ai_cache' in st.session_state and sel_ticker in st.session_state['ai_cache']:
        cache_item = st.session_state['ai_cache'][sel_ticker]
        if isinstance(cache_item, dict):
            st.markdown(cache_item['content'])
            st.caption(f"Generated by: {cache_item.get('source', 'Unknown')}")
        else:
            st.markdown(cache_item)
    elif sel_ticker:
        st.info(f"Analysis for {sel_ticker} pending... Check Results tab to generate.")
    else:
        st.info("Select a ticker in the 'Results' tab to view detailed analysis.")

with tab_results:
    if st.session_state.get('scan_complete', False):
        results = st.session_state['scan_results']
        scan_date_display = st.session_state.get('scan_date', pd.Timestamp.now().date())
        universe_name = st.session_state.get('universe_name', 'Custom List')
        
        col1, col2 = st.columns([1, 2])
        
        selected_ticker = None
        
        with col1:
            st.subheader(f"Candidates: {scan_date_display}")
            st.caption(f"Universe: {universe_name}")
            
            if not results.empty:
                def color_cells(val):
                    if val == "ACTIONABLE (Buy)":
                        return 'color: green; font-weight: bold'
                    elif val == "WATCH (New Signal)":
                        return 'color: orange; font-weight: bold'
                    return ''
                
                def color_return(val):
                    if val is None:
                        return 'color: gray'
                    elif val > 0:
                        return 'color: green'
                    elif val < 0:
                        return 'color: red'
                    return ''

                cols = ['Ticker', 'Status', 'Signal Date', 'Action Date', 'Entry Price', '5-Day Return %', 'WVF', 'UpperBB']
                cols = [c for c in cols if c in results.columns]
                df_display = results[cols]
                
                # Interactive Dataframe with Selection
                event = st.dataframe(
                    df_display.style.applymap(color_return, subset=['5-Day Return %'] if '5-Day Return %' in df_display.columns else None)
                                   .applymap(color_cells, subset=['Status']),
                    hide_index=True, 
                    use_container_width=True,
                    on_select="rerun", # New selection API
                    selection_mode="single-row"
                )
                
                if len(event.selection.rows) > 0:
                    selected_row_idx = event.selection.rows[0]
                    selected_ticker = df_display.iloc[selected_row_idx]['Ticker']
                else:
                    selected_ticker = st.selectbox("Or Select Ticker:", results['Ticker'].tolist())
                
                # Store selection for other tabs
                st.session_state['selected_ticker'] = selected_ticker

            else:
                st.info("No stocks matched the criteria.")

        with col2:
            if selected_ticker and scanner.data is not None:
                # Fetch Full Name
                col_results = st.container()
                with col_results:
                    long_name = selected_ticker
                    info = {}
                    
                    # 1. Try Taiwan Map First (Fast & Accurate for TW)
                    tw_map = get_taiwan_names_map()
                    if selected_ticker in tw_map:
                        long_name = tw_map[selected_ticker]
                    else:
                        # 2. Fallback to YFinance
                        try:
                            t_info = yf.Ticker(selected_ticker)
                            info = t_info.info
                            long_name = info.get('longName', selected_ticker)
                        except:
                            pass
                    
                    # 3. Double check current scanner universe (Dynamic overrides)
                    if hasattr(scanner, 'universe_df') and scanner.universe_df is not None:
                         match = scanner.universe_df[scanner.universe_df['Ticker'] == selected_ticker]
                         if not match.empty:
                             long_name = match.iloc[0]['Name']
                             if 'Sector' in match.columns:
                                 info['sector'] = match.iloc[0]['Sector']

                    st.subheader(f"Analysis: {selected_ticker} - {long_name}")
                    
                    # Re-calculate indicators
                    try:
                        if isinstance(scanner.data.columns, pd.MultiIndex):
                            df_ticker = scanner.data[selected_ticker].dropna()
                        else:
                            df_ticker = scanner.data
                    
                        indicators = scanner.calculate_indicators(df_ticker)
                        target_date = pd.to_datetime(scan_date_display)
                        history_slice = indicators[indicators.index <= target_date]
                        
                        if not history_slice.empty:
                            plot_data = history_slice.tail(200)
                            
                            # Initialize Parsed Data to None
                            ai_parsed_data = None
                            
                            # Check Cache FIRST to see if we have lines to draw
                            if 'ai_cache' not in st.session_state:
                                st.session_state['ai_cache'] = {}
                            
                            report_content = ""
                            source_model = ""
                            cache_data = st.session_state['ai_cache'].get(selected_ticker)
                            
                            if isinstance(cache_data, dict):
                                report_content = cache_data.get('content', "")
                                source_model = cache_data.get('source', "Unknown")
                            elif isinstance(cache_data, str):
                                report_content = cache_data
                            
                            if report_content:
                                 try:
                                    json_match = re.search(r'```json\n(.*?)\n```', report_content, re.DOTALL)
                                    if json_match:
                                        ai_parsed_data = json.loads(json_match.group(1))
                                 except:
                                     pass
    
                            # Plot Construction
                            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.6, 0.4], specs=[[{"secondary_y": False}], [{"secondary_y": False}]])
                            fig.add_trace(go.Candlestick(x=plot_data.index, open=df_ticker.loc[plot_data.index]['Open'], high=df_ticker.loc[plot_data.index]['High'], low=df_ticker.loc[plot_data.index]['Low'], close=plot_data['Close'], name="Price"), row=1, col=1)
                            
                            # Get Last Price (Price at Date)
                            last_price = plot_data.iloc[-1]['Close']
                            last_date_str = plot_data.index[-1].strftime('%Y-%m-%d')
                            
                            # Add Annotations List
                            annotations = []
                            
                            # 1. Price at Date Annotation
                            annotations.append(dict(
                                x=1, xref="paper", y=last_price, yref="y",
                                text=f"Price ({last_date_str}): {last_price:.2f}",
                                showarrow=False, xanchor="left", align="left",
                                font=dict(color="white", size=10),
                                bgcolor="black", bordercolor="gray"
                            ))
    
                            # Add AI Lines and Annotations if data exists
                            if ai_parsed_data:
                                if 'buy_below' in ai_parsed_data and ai_parsed_data['buy_below'] is not None and ai_parsed_data['buy_below'] > 0:
                                    val = ai_parsed_data['buy_below']
                                    fig.add_hline(y=val, line_dash="dash", line_color="green", row=1, col=1)
                                    annotations.append(dict(
                                        x=1, xref="paper", y=val, yref="y",
                                        text=f"AI Buy: {val:.2f}",
                                        showarrow=False, xanchor="left", align="left",
                                        font=dict(color="green", size=10),
                                        bgcolor="rgba(0,0,0,0.5)"
                                    ))
                                    
                                if 'fair_value' in ai_parsed_data and ai_parsed_data['fair_value'] is not None and ai_parsed_data['fair_value'] > 0:
                                    val = ai_parsed_data['fair_value']
                                    fig.add_hline(y=val, line_dash="dot", line_color="blue", row=1, col=1)
                                    annotations.append(dict(
                                        x=1, xref="paper", y=val, yref="y",
                                        text=f"Fair Value: {val:.2f}",
                                        showarrow=False, xanchor="left", align="left",
                                        font=dict(color="cyan", size=10),
                                        bgcolor="rgba(0,0,0,0.5)"
                                    ))
                            
                            st_up = plot_data.apply(lambda x: x['Supertrend'] if x['SupertrendTrend'] == 1 else None, axis=1)
                            st_down = plot_data.apply(lambda x: x['Supertrend'] if x['SupertrendTrend'] == -1 else None, axis=1)
                            fig.add_trace(go.Scatter(x=plot_data.index, y=st_up, mode='lines', line=dict(color='green', width=2), name='Supertrend (Up)'), row=1, col=1)
                            fig.add_trace(go.Scatter(x=plot_data.index, y=st_down, mode='lines', line=dict(color='red', width=2), name='Supertrend (Down)'), row=1, col=1)
                            fig.add_trace(go.Scatter(x=plot_data.index, y=plot_data['SMA200'], mode='lines', line=dict(color='orange', width=2), name='SMA 200'), row=1, col=1)
                            fig.add_trace(go.Scatter(x=plot_data.index, y=plot_data['WVF'], fill='tozeroy', line=dict(color='cyan', width=1), name="WVF"), row=2, col=1)
                            fig.add_trace(go.Scatter(x=plot_data.index, y=plot_data['UpperBB'], line=dict(color='gray', dash='dash'), name="Upper BB"), row=2, col=1)
                            
                            signals = plot_data[(plot_data['WVF'] > plot_data['UpperBB']) & (plot_data['Close'] > plot_data['SMA200'])]
                            if not signals.empty:
                                fig.add_trace(go.Scatter(x=signals.index, y=signals['WVF'], mode='markers', marker=dict(color='red', size=8, symbol='x'), name='Signal'), row=2, col=1)
                            
                            # Update layout with margins and annotations
                            # Move labels to Title to avoid overlap
                            title_text = f"{selected_ticker} - {scan_date_display} | P: {last_price:.2f}"
                            
                            # Localization for Labels
                            label_fair = "Fair"
                            label_buy = "Buy"
                            
                            if ai_parsed_data:
                                # Update Title with Chinese Name if available
                                if 'company_name_zh' in ai_parsed_data:
                                    title_text = f"{selected_ticker} {ai_parsed_data['company_name_zh']} - {scan_date_display} | P: {last_price:.2f}"
                                
                                # Localization check
                                if selected_ticker.endswith(".TW"):
                                    label_fair = "股價合理區"
                                    label_buy = "AI 買入價"
                                
                                if 'fair_value' in ai_parsed_data and ai_parsed_data['fair_value'] is not None and ai_parsed_data['fair_value'] > 0:
                                    title_text += f" | {label_fair}: {ai_parsed_data['fair_value']:.2f}"
                                if 'buy_below' in ai_parsed_data and ai_parsed_data['buy_below'] is not None and ai_parsed_data['buy_below'] > 0:
                                    title_text += f" | {label_buy}: {ai_parsed_data['buy_below']:.2f}"
                            
                            fig.update_layout(
                                title=dict(text=f"<b>{title_text}</b>", font=dict(size=24)),
                                xaxis_rangeslider_visible=False, 
                                height=500, 
                                template="plotly_dark", 
                                margin=dict(l=10, r=10, t=50, b=10) # Reset right margin
                            )
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # --- AI Analysis Section within Column 2 ---
                            st.markdown("---")
                            st.subheader("🤖 AI Analyst Verdict")
                            
                            # Helper for safe formatting
                            def safe_val(val):
                                try:
                                    if val is None: return 0.0
                                    return float(val)
                                except:
                                    return 0.0

                            if report_content:
                                # Display Source if available
                                if source_model:
                                    st.caption(f"Source: {source_model}")
                                
                                # 2. Display Structured Summary
                                if ai_parsed_data:
                                    ac1, ac2, ac3 = st.columns(3)
                                    action = ai_parsed_data.get("action", "N/A").upper()
                                    color = "red"
                                    if "BUY" in action: color = "green"
                                    elif "HOLD" in action: color = "orange"
                                    
                                    # Standardized Metric Display
                                    ac1.metric("Action", action)
                                    
                                    val_fair = safe_val(ai_parsed_data.get('fair_value'))
                                    val_buy = safe_val(ai_parsed_data.get('buy_below'))
                                    
                                    ac2.metric(label_fair, f"${val_fair:.2f}")
                                    ac3.metric(label_buy, f"${val_buy:.2f}")
                                    
                                    st.info(f"**Rationale:** {ai_parsed_data.get('rationale', 'See full report.')}")
                                else:
                                    st.warning("Summary data parsing failed. Generating report might fix this.")
                                
                                # Extract Conclusion for text fallback (Supports US & TW formats)
                                try:
                                    full_text_to_show = ""
                                    
                                    # Check for Taiwan Headers first
                                    # Check for Taiwan Headers first
                                    if "## 最終綜合判斷" in report_content or "## 結論與總結" in report_content:
                                        # Determine the split key
                                        split_key = "## 最終綜合判斷" if "## 最終綜合判斷" in report_content else "## 結論與總結"
                                        
                                        # Extract Conclusion
                                        conclusion_part = report_content.split(split_key)[1]
                                        
                                        # Extract Rating if exists (legacy check)
                                        rating_part = ""
                                        if "## 財務分析師評級摘要" in report_content:
                                             rating_part = report_content.split("## 財務分析師評級摘要")[1].split(split_key)[0]
                                             full_text_to_show += f"#### 📊 財務分析師評級摘要\n{rating_part}\n"
                                        
                                        full_text_to_show += f"#### 📋 最終綜合判斷 (Final Synthesis)\n{conclusion_part}"
                                        st.markdown(f"#### 🇹🇼 台灣市場分析報告\n")
    
                                    # Fallback to US Part K or Final Proposal
                                    elif "3. Final Proposal & Execution" in report_content:
                                        full_text_to_show = report_content.split("3. Final Proposal & Execution")[1]
                                        st.markdown(f"### 📋 Final Proposal & Execution\n")
                                    elif "PART K: FINAL INVESTMENT CONCLUSION" in report_content:
                                        full_text_to_show = report_content.split("PART K: FINAL INVESTMENT CONCLUSION")[1]
                                        st.markdown(f"### 📋 Final Investment Conclusion (Trade Card)\n")
                                    elif "PART K:" in report_content:
                                        full_text_to_show = report_content.split("PART K:")[1]
                                    elif "## PART K" in report_content:
                                        full_text_to_show = report_content.split("## PART K")[1]
                                    
                                    if full_text_to_show:
                                        # Clean up JSON if present to keep it professional
                                        full_text_to_show = re.sub(r'```json.*?```', '', full_text_to_show, flags=re.DOTALL)
                                        st.markdown(full_text_to_show)
                                        
                                except Exception as e:
                                    st.error(f"Error parsing Conclusion: {e}")
                                    
                                st.caption("👉 Go to **'AI Analysis'** tab above for the Full Report (Parts A-J).")
                                
                                if st.button("Regenerate Report"):
                                    del st.session_state['ai_cache'][selected_ticker]
                                    st.rerun()
                            else:
                                # Automatic Generation
                                if api_key:
                                    try:
                                        with st.spinner(f"🔍 AI Analyst is researching {selected_ticker} ({long_name}) as of {scan_date_display}..."):
                                            # Use HISTORICAL Price Context
                                            # Ensure we use the price from the scan date, not today
                                            hist_price = last_price # Calculated above from plot_data tail
                                            
                                            # Safe Year Extraction
                                            scan_year = str(scan_date_display).split('-')[0]

                                            # Construct Context
                                            market_context = f"""
                                            **HISTORICAL ANALYST TASK**:
                                            Target: {selected_ticker} ({long_name})
                                            As-At Date: {scan_date_display}
                                            Closing Price: ${hist_price:.2f}
                                            
                                            **OBJECTIVE**:
                                            You are an Intelligence Officer retrieving filed reports from the archives.
                                            You must find the *latest* data that was available to the public *before* {scan_date_display}.
                                            
                                            **REQUIRED SEARCH OPERATIONS**:
                                            1. Search: "{long_name} {selected_ticker} investor relations financial reports"
                                            2. Search: "{long_name} {selected_ticker} quarterly earnings {scan_year}"
                                            3. Search: "{long_name} {selected_ticker} analyst ratings history {scan_year}"
                                            4. Search: "Taiwan Manufacturing PMI {scan_year} historical data"
                                            
                                            **DATA HANDLING RULES**:
                                            - **BEST AVAILABLE DATA**: If {scan_date_display} is in Q1, look for Q4 of previous year. If in Q4, look for Q3.
                                            - **EXAMPLE**: If today is Feb 2026 and Q4 2025 report is not out, YOU MUST USE THE Q3 2025 REPORT found on the investor relations page.
                                            - **NO FUTURE KNOWLEDGE**: Do not use data released *after* {scan_date_display}.
                                            - **ESTIMATION**: If a specific number is not found from the exact quarter, estimate it based on the TTM (Trailing Twelve Months) trend.
                                            - **CITATION**: Clearly state the source date (e.g., "Using Q3 2025 data as Q4 was not yet released...").
                                            """
                                            
                                            # --- CONDITIONAL VALUATION FRAMEWORK PROMPT ---
                                            if selected_ticker.endswith(".TW") or selected_ticker.endswith(".TWO"):
                                                # --- TAIWAN MARKET PROMPT ---
                                                system_prompt = f"""
# 📌 Institutional Multi-Factor Stock Valuation Framework  
## Part 1 (Reality-Based) + Part 2 (Expectation-Based)

---

## ROLE

You are an **Institutional Quantitative Strategist**.
Your goal is to provide a valuation report.

**Override**: If exact financial data is missing, use TTM (Trailing Twelve Months) data found via search.


Your task is to perform a **two-part equity valuation** of a specified US-listed stock using **only information that was publicly available _as at a specified date_**.

You must behave as if you are operating **on that date**, with **no knowledge of future events**.

---

## GLOBAL CONSTRAINTS (MANDATORY)

1. **No Guessing / No Estimation**
   - Do NOT estimate missing data.
   - If data is unavailable as at the date, explicitly state:  
     > “Data not available as at this date.”

2. **No Future Knowledge**
   - Do NOT reference:
     - Earnings released after the as-at date
     - Price movements after the as-at date
     - Macro data revisions after the as-at date
     - Any hindsight-based outcomes

3. **Source Discipline**
   Allowed sources (as at date only):
   - Published quarterly / annual financial reports
   - Official company guidance and press releases
   - Analyst consensus forecasts published by that date
   - Macro data released by that date

4. **Strict Separation**
   - **Part 1** → backward-looking, factual, no forecasts  
   - **Part 2** → forward-looking, but only expectations visible at the date

5. **Default As-At Date**
   - Today, unless explicitly specified by the user

---

## INPUTS

- **Target Stock Ticker**
- **As-At Date**
- **Latest Financial Statements Available as at the Date**
- **Latest Macro Data Available as at the Date**

---

# =========================
# PART 1 — REALITY-BASED VALUATION (NO FORECAST)
# =========================

## OBJECTIVE

Determine whether the stock was **Overvalued, Fairly Valued, or Undervalued** using **only historical and trailing data available as at the date**.

---

## PHASE 1: MACRO REGIME IDENTIFICATION (INVESTMENT CLOCK)

Using macro data available as at the date (PMI, inflation, growth, policy stance), classify the regime:

### 1. Recovery
- PMI < 50 but rising
- Inflation falling  
**Factor Bias:** Value / Size

### 2. Expansion
- PMI > 50
- Growth accelerating  
**Factor Bias:** Growth / Momentum

### 3. Slowdown / Stagflation
- PMI falling
- Inflation high or rising  
**Factor Bias:** Quality / Low Vol  
**Adjustment:** Apply valuation multiple compression

### 4. Contraction
- PMI < 50 and falling
- Growth negative  
**Factor Bias:** Balance Sheet / Yield

### Discount Rate Adjustment
If:
- Inflation > 3%, OR
- Rate volatility is high  

→ Increase Cost of Equity (COE) by **+150 bps**  
→ Penalize long-duration cash flows

---

## PHASE 2: STOCK CLASSIFICATION & VALUATION METHOD

Classify the stock using **reported data only**.

---

### A. HIGH GROWTH / SAAS

**Criteria**
- Revenue Growth > 15%
- Operating or FCF Margin < 10%

**Valuation Method**
- EV / Sales (P/E NOT allowed)
- Rule of 40 = Revenue Growth + FCF Margin

**Adjustments**
- Rule of 40 > 40 → Premium valuation (1.2x)
- Rule of 40 < 40 → Discount valuation (0.8x)
- Rule of 40 < 20 → “Broken Growth” classification

**Risk Check**
- LTM Cash Burn > Cash Balance → Flag as High Risk

---

### B. CYCLICAL

**Criteria**
- Sector: Energy, Materials, Industrials  
OR
- Earnings volatility > market

**Valuation Method**
- Normalized P/E (7–10 year average earnings, if available)
- Price-to-Tangible Book (P/TBV)

**Trap Detection**
- Low current P/E + record-high margins → Flag as **Peak Cycle / Value Trap**

---

### C. VALUE / MATURE

**Criteria**
- Profitable
- Revenue Growth < 10%

**Valuation Method**
- ROE vs P/TBV regression  
  Target P/B = (ROE − g) / (COE − g)
- Dividend Discount Model (if dividends exist)

**Quality Overlay**
- Piotroski F-Score
- F-Score < 4 → Apply 20% discount to fair value

---

## PHASE 3: RISK & VETO CHECKS

1. **Altman Z-Score**
   - Z < 1.81 → **DISTRESS WARNING**
   - Recommendation: **AVOID regardless of valuation**

2. **Beneish M-Score**
   - M > −1.78 → Flag potential earnings manipulation

3. **Momentum Sanity Check**
   - 6-month relative strength vs SPY
   - Negative momentum + value signal → “Falling Knife” risk

---

## PART 1 OUTPUT

- Historical Fair Value Range
- Valuation Status:
  - Overvalued / Fairly Valued / Undervalued
- Explicit justification referencing:
  - Macro regime
  - Financial strength
  - Earnings quality
  - Appropriate valuation multiples

---

# =========================
# PART 2 — EXPECTATION-BASED VALUATION (AS-AT-DATE ONLY)
# =========================

## OBJECTIVE

Evaluate whether the stock price was **under- or over-valued relative to expectations that were visible at the as-at date**, without using any future information.

---

## ALLOWED FORWARD-LOOKING DATA

(Only if available as at the date)

- Management guidance
- Analyst consensus forecasts
- Announced capex plans
- Publicly announced products, contracts, or pipelines

---

## FORWARD VALUATION LOGIC

1. **Forecast Profitability Path**
   - Revenue growth expectations
   - Margin expansion expectations

2. **Forward Valuation Multiples**
   - Forward P/E, EV/Sales, PEG  
   (Only if forecast data existed as at the date)

3. **Market-Implied Expectations**
   - What growth and margins the market price assumes **as at that date**

---

## PART 2 OUTPUT

- Expected Fair Value Range based on contemporaneous expectations
- Comparison of market price vs expected fundamentals
- Expectation assessment:
  - Overly optimistic
  - Conservative discount
  - Fairly priced

---

# =========================
# 最終綜合判斷 (FINAL SYNTHESIS)
# =========================

You MUST start this section with the exact markdown header:
**## 最終綜合判斷 (FINAL SYNTHESIS)**

Provide **FINAL SUMMARY ONLY**, including:

1. **Part 1 Conclusion**
   - Historical, no-forecast valuation verdict

2. **Part 2 Conclusion**
   - Expectation-based valuation verdict

3. **Integrated Judgment**
   - Cheap but risky
   - Fair but high quality
   - Expensive but expectation-justified

4. **Composite Valuation Score (0–100)**
   - 0–20: Significantly Overvalued
   - 21–40: Overvalued
   - 41–60: Fairly Valued
   - 61–80: Undervalued
   - 81–100: Deep Value / Strong Conviction

5. **Required Margin of Safety**
   - Stable compounder: ~20%
   - Growth / Cyclical: 40%+
   - Distressed: Avoid

---

## OUTPUT STYLE REQUIREMENTS

- **LANGUAGE: STRICTLY TRADITIONAL CHINESE (繁體中文) FOR THE ENTIRE REPORT.**
- Institutional
- Evidence-based
- Concise but rigorous
- Explicitly state: **“As at [DATE]”**
- No speculation
- No hindsight

---

**END OF FRAMEWORK**

Context:
{market_context}

CRITICAL INSTRUCTION:
At the very end of your response, AFTER the sections, you MUST provide a JSON block summary in this EXACT format for software parsing:
```json
{{
    "action": "BUY" or "HOLD" or "SELL",
    "company_name_zh": "Traditional Chinese Name of Stock (if applicable)",
    "fair_value": 150.25, 
    "buy_below": 140.00,
    "risk_level": "Medium",
    "rationale": "One sentence summary (in target language)."
}}
```
"""
                                            else:
                                                # --- GLOBAL / US MARKET PROMPT ---
                                                system_prompt = f"""
# 📌 Institutional Multi-Factor Stock Valuation Framework

## ROLE & GOVERNANCE
You are an **Institutional Quantitative Strategist and Equity Valuation Expert**. Your mission is to provide world-class, rigorous equity analysis using a dual-layered methodology (Historical Reality vs. Forward Expectations). 

### 🛑 MANDATORY PROTOCOLS
1. **Zero-Hindsight Constraint**: You must strictly operate as if the current date is the user-specified **As-At Date**. Referencing any event (earnings, macro shifts, or price action) that occurred after that date is a total breach of institutional protocol.
2. **Data Integrity**: Do not estimate missing data. If data was unavailable as of the date, explicitly state: "Data not available as at this date."
3. **Language Protocol**: 
   - **US Stocks**: Respond in English.
   - **Taiwan (TW) or Hong Kong (HK) Stocks**: Respond in Traditional Chinese (繁體中文).

---

## PART 1: REALITY-BASED VALUATION (THE ANCHOR)
*Objective: Determine intrinsic value using only hard, historical data available on the date.*

### 1. Macro Regime Identification
Identify the Investment Clock phase (Recovery, Expansion, Slowdown, or Contraction) using PMI and CPI data. 
- **Adjustment**: Increase Cost of Equity (COE) by **+150 bps** if Inflation > 3% or Rate Volatility is high to penalize long-duration cash flows.

### 2. Deep-Dive Classification
- **High Growth/SaaS**: Evaluate via EV/Sales. Calculate **Rule of 40** (Revenue Growth + FCF Margin).
- **Cyclical**: Use Normalized P/E (7-10 yr average) and Price-to-Tangible Book (P/TBV).
- **Value/Mature**: Execute ROE vs. P/TBV Regression: $$Target P/B = \\frac{{ROE - g}}{{COE - g}}$$

### 3. Institutional Quality Vetoes
- **Altman Z-Score**: If Z < 1.81, issue a mandatory **DISTRESS WARNING**.
- **Beneish M-Score**: If M > −1.78, flag potential earnings manipulation.
- **Piotroski F-Score**: If Score < 4, apply a 20% haircut to fair value.

---

## PART 2: EXPECTATION-BASED VALUATION (THE ALPHA)
*Objective: Evaluate market-implied sentiment and forward-looking visibility.*

1. **Consensus Dissection**: Analyze analyst EPS/Revenue forecasts and management guidance active **as of the date**.
2. **Reverse DCF Analysis**: Determine what implied growth rate and margins the market price assumes at that specific moment.
3. **Forward Multiples**: Calculate Forward P/E, PEG, and EV/EBITDA based on contemporaneous forecasts.

---

## FINAL OUTPUT: THE INSTITUTIONAL DIRECTIVE
Generate the final report using this structure:

### 1. Institutional Research Summary
| Pillar | Metric / Status | Quantitative Commentary |
| :--- | :--- | :--- |
| **Macro Regime** | [Regime Name] | Impact on sector valuation and discount rates. |
| **Reality (Part 1)** | [Key Trailing Ratios] | Verdict on historical valuation (Over/Under/Fair). |
| **Expectations (Part 2)** | [Forward Ratios/Guidance] | Assessment of market sentiment and growth visibility. |
| **Quality/Risk** | [Z/F/M-Scores] | Comprehensive balance sheet and earnings quality review. |

### 2. Scenario Valuation Matrix (12-Month Outlook)
| Scenario | Target Price | Probability | Critical Trigger |
| :--- | :--- | :--- | :--- |
| **Bull Case** | [Price] | [%] | [Specific Catalyst] |
| **Base Case** | [Price] | [%] | [Expected Outcome] |
| **Bear Case** | [Price] | [%] | [Specific Risk Event] |

### 3. Final Proposal & Execution
- **Action**: (Strong Buy / Buy / Hold / Sell / Avoid)
- **Composite Valuation Score**: 0–100 (81-100: Deep Value; 0-20: Significantly Overvalued)
- **Execution Zone**: Optimal Buy/Entry Price Range.
- **Stop-Loss**: Hard exit price for risk management.
- **Strategic Rationale**: Concise 3-point thesis justifying the verdict.

Context:
{market_context}

CRITICAL INSTRUCTION:
At the very end of your response, AFTER the sections, you MUST provide a JSON block summary in this EXACT format for software parsing:
```json
{{
    "action": "BUY" or "HOLD" or "SELL",
    "company_name_zh": "Traditional Chinese Name of Stock (if applicable)",
    "fair_value": 150.25, 
    "buy_below": 140.00,
    "risk_level": "Medium",
    "rationale": "One sentence summary (in target language)."
}}
```
"""
                                            
                                            # Use Helper with Retry Logic and Perplexity Fallback
                                            report_content, source_model = generate_ai_report(api_key, pplx_api_key, system_prompt)
                                            
                                            # Cache results
                                            st.session_state['ai_cache'][selected_ticker] = {
                                                'content': report_content,
                                                'source': source_model
                                            }
                                            st.rerun() # Rerun to show the split view appropriately
                                            
                                    except Exception as e:
                                        st.error(f"AI Analysis Failed: {e}")
                                        st.caption("All models failed. Check API Key or Region availability.")
                                else:
                                    st.info("Enter Gemini API Key in Sidebar to enable Auto-Analysis.")

                        else:
                            st.warning("No historical data to plot.")

                    except Exception as e:
                        st.error(f"Plot Error: {e}")
    else:
        st.info("Run a scan to see results.")
