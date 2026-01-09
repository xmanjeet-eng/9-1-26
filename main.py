import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
from flask import Flask, render_template
from datetime import datetime
import pytz
import os

app = Flask(__name__)

def get_ist_time():
    return datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')

def analyze_ticker(symbol):
    # Fetch 7 days to ensure we have enough buffer for indicators
    df = yf.download(symbol, period='7d', interval='5m', multi_level_index=False)
    
    if df.empty or len(df) < 50: 
        return None

    # --- INDICATOR CALCULATIONS ---
    df.ta.supertrend(append=True)
    df.ta.bbands(append=True)
    df.ta.rsi(append=True)
    df.ta.vwap(append=True)
    df.ta.adx(append=True)
    df.ta.atr(append=True)

    # --- DYNAMIC COLUMN FIX ---
    # This searches for columns that start with the indicator name
    try:
        bb_upper_col = [c for c in df.columns if c.startswith('BBU')][0]
        bb_lower_col = [c for c in df.columns if c.startswith('BBL')][0]
        st_col = [c for c in df.columns if c.startswith('SUPERT_') and not c.endswith('d')][0]
        rsi_col = [c for c in df.columns if c.startswith('RSI')][0]
        vwap_col = [c for c in df.columns if c.startswith('VWAP')][0]
        atr_col = [c for c in df.columns if c.startswith('ATRr')][0]
    except IndexError:
        return {"error": "Indicator calculation failed - wait for more market data"}

    last = df.iloc[-1]
    curr_price = last['Close']
    
    # Extract values safely
    vwap_val = last[vwap_col]
    rsi_val = last[rsi_col]
    bb_upper = last[bb_upper_col]
    bb_lower = last[bb_lower_col]
    super_trend = last[st_col]
    atr_val = last[atr_col]

    # --- INSTITUTIONAL SIGNAL LOGIC ---
    score = 0
    if curr_price > vwap_val: score += 1
    else: score -= 1
    
    if rsi_val > 70: score -= 1 
    elif rsi_val < 30: score += 1
    
    if curr_price > super_trend: score += 1
    else: score -= 1
    
    if curr_price > bb_upper: score += 0.5 
    elif curr_price < bb_lower: score -= 0.5

    prob_up = min(max(50 + (score * 12), 10), 90)

    return {
        "name": "NIFTY 50" if "NSEI" in symbol else "BANK NIFTY",
        "price": round(curr_price, 2),
        "target": round(curr_price + (atr_val * 1.5) if score > 0 else curr_price - (atr_val * 1.5), 2),
        "up_prob": round(prob_up, 1),
        "down_prob": round(100 - prob_up, 1),
        "signal": "STRONG BUY" if score >= 2 else "STRONG SELL" if score <= -2 else "NEUTRAL / SIDEWAYS",
        "rsi": int(rsi_val),
        "volatility": "HIGH" if (bb_upper - bb_lower) > (curr_price * 0.005) else "LOW (Squeeze)"
    }

@app.route('/')
def home():
    try:
        nifty = analyze_ticker('^NSEI')
        bank = analyze_ticker('^NSEBANK')
        
        if not nifty or not bank:
            return "Fetching Market Data... Please refresh in 1 minute."
            
        return render_template('index.html', n=nifty, b=bank, time=get_ist_time())
    except Exception as e:
        # Detailed error for debugging
        return f"Error Detail: {str(e)}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
