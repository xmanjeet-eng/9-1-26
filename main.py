import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
from flask import Flask, render_template
from datetime import datetime
import pytz

app = Flask(__name__)

def get_ist_time():
    return datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')

def analyze_ticker(symbol):
    # Fetch 5-minute data (Standard for Indian Intraday)
    df = yf.download(symbol, period='5d', interval='5m', multi_level_index=False)
    if df.empty: return None

    # --- ADVANCED INDICATOR SUITE ---
    # 1. Trend: SuperTrend (7, 3)
    df.ta.supertrend(append=True)
    # 2. Volatility: Bollinger Bands (20, 2)
    df.ta.bbands(append=True)
    # 3. Momentum: RSI (14)
    df.ta.rsi(append=True)
    # 4. Volume: VWAP
    df.ta.vwap(append=True)
    # 5. Trend Strength: ADX (14)
    df.ta.adx(append=True)

    # Latest Values
    last = df.iloc[-1]
    curr_price = last['Close']
    vwap_val = last['VWAP_D']
    rsi_val = last['RSI_14']
    bb_upper = last['BBU_20_2.0']
    bb_lower = last['BBL_20_2.0']
    super_trend = last['SUPERT_7_3.0'] # Direction: 1 is Green, -1 is Red
    
    # --- INSTITUTIONAL SIGNAL LOGIC ---
    score = 0
    # Condition 1: Price vs VWAP (Institutional Benchmark)
    if curr_price > vwap_val: score += 1
    else: score -= 1
    
    # Condition 2: RSI Exhaustion (Mean Reversion)
    if rsi_val > 70: score -= 1 # Overbought
    elif rsi_val < 30: score += 1 # Oversold
    
    # Condition 3: SuperTrend Alignment
    if curr_price > super_trend: score += 1
    
    # Condition 4: Bollinger Squeeze/Breakout
    if curr_price > bb_upper: score += 0.5 # Breakout
    elif curr_price < bb_lower: score -= 0.5 # Breakdown

    # Final Probability Mapping
    # Convert score (-3.5 to 3.5) to %
    prob_up = min(max(50 + (score * 12), 10), 90)

    return {
        "name": "NIFTY 50" if "NSEI" in symbol else "BANK NIFTY",
        "price": round(curr_price, 2),
        "target": round(curr_price + (last['ATRr_14'] * 1.5) if score > 0 else curr_price - (last['ATRr_14'] * 1.5), 2),
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
        return render_template('index.html', n=nifty, b=bank, time=get_ist_time())
    except Exception as e:
        return f"Market Offline or Data Error: {str(e)}"

if __name__ == "__main__":
    app.run(debug=True)
