import os
import pyotp
import requests
import datetime
import pandas as pd
from NorenRestApiPy.NorenApi import NorenApi

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.getenv('8677504246:AAFq6kPDoX410tz3kodv5ZQaqviiZ5JEfBc') # Add this to GitHub Secrets!
TELEGRAM_CHAT_ID = os.getenv('8791344518')     # Add this to GitHub Secrets!

# Stocks under ₹250 for ₹1000 Budget (Format: "Symbol": "Token")
MY_STOCKS = {
    "TATASTEEL": "3499",
    "ZOMATO": "76126",
    "ONGC": "2475",
    "IDFCFIRSTB": "11184"
}

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram Error: {e}")

class ShoonyaApiPy(NorenApi):
    def __init__(self):
        NorenApi.__init__(self, host='https://api.shoonya.com/NorenWClientTP/', websocket='wss://api.shoonya.com/NorenWSTP/')

def shoonya_login():
    api = ShoonyaApiPy()
    totp = pyotp.TOTP(os.getenv('SHOONYA_TOTP')).now()
    ret = api.login(
        userid=os.getenv('FN201252'), 
        password=os.getenv('Nikitha@143'), 
        twoFA=totp, 
        vendor_code=os.getenv('FN201252_U'), 
        api_secret=os.getenv('f35144bf80dc93c952e3ee6d6e1fcce2'), 
        imei='gh_actions_bot'
    )
    if ret and ret.get('stat') == 'Ok':
        return api
    return None

def check_orb_breakout(api, symbol_name, token):
    try:
        # Fetch data for today
        end_time = datetime.datetime.now().timestamp()
        start_time = end_time - (6 * 60 * 60) # Last 6 hours
        
        ret = api.get_time_price_series(exchange='NSE', token=token, starttime=start_time, endtime=end_time, interval=5)
        
        if not ret or not isinstance(ret, list):
            return None
            
        df = pd.DataFrame(ret)
        df = df.iloc[::-1].reset_index(drop=True) # Reverse to chronological
        
        df['inth'] = pd.to_numeric(df['inth']) # High
        df['intl'] = pd.to_numeric(df['intl']) # Low
        df['intc'] = pd.to_numeric(df['intc']) # Close
        df['intv'] = pd.to_numeric(df['intv']) # Volume
        
        if len(df) < 4: # Need at least first 15 mins (3 candles) + 1 new candle to break out
            return None

        # Calculate 15-minute Opening Range (first 3 candles of the day)
        first_15_mins = df.iloc[:3]
        orb_high = first_15_mins['inth'].max()
        orb_low = first_15_mins['intl'].min()

        latest_candle = df.iloc[-1]
        price = latest_candle['intc']
        avg_volume = df['intv'].tail(10).mean() # Simple volume average

        signal = None
        
        # Bullish Breakout
        if price > orb_high and latest_candle['intv'] > avg_volume:
            sl = orb_low
            risk = price - sl
            target = price + (risk * 2) # 1:2 Risk/Reward
            signal = f"🚀 *BULLISH BREAKOUT* \n**Stock:** {symbol_name}\n**Entry:** ₹{price:.2f}\n**Stop Loss:** ₹{sl:.2f}\n**Target:** ₹{target:.2f}"
            
        # Bearish Breakout
        elif price < orb_low and latest_candle['intv'] > avg_volume:
            sl = orb_high
            risk = sl - price
            target = price - (risk * 2)
            signal = f"🩸 *BEARISH BREAKOUT* \n**Stock:** {symbol_name}\n**Entry:** ₹{price:.2f}\n**Stop Loss:** ₹{sl:.2f}\n**Target:** ₹{target:.2f}"

        return signal

    except Exception as e:
        print(f"Error checking {symbol_name}: {e}")
        return None

def main():
    print("Initiating Market Scanner...")
    api = shoonya_login()
    
    if not api:
        print("Login failed. Exiting.")
        return

    signals_found = 0
    for symbol, token in MY_STOCKS.items():
        signal = check_orb_breakout(api, symbol, token)
        if signal:
            send_telegram_message(signal)
            signals_found += 1
            print(f"Alert sent for {symbol}")
            
    if signals_found == 0:
        print("No breakouts detected in this cycle.")

    api.logout()

if __name__ == "__main__":
    main()
