import os
import pyotp
import requests
import datetime
import pytz
import pandas as pd
from NorenRestApiPy.NorenApi import NorenApi

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

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
        userid=os.getenv('SHOONYA_USER'), 
        password=os.getenv('SHOONYA_PWD'), 
        twoFA=totp, 
        vendor_code=os.getenv('SHOONYA_VC'), 
        api_secret=os.getenv('SHOONYA_APIKEY'), 
        imei='gh_actions_bot'
    )
    if ret and ret.get('stat') == 'Ok':
        return api
    return None

def check_orb_breakout(api, symbol_name, token):
    try:
        end_time = datetime.datetime.now().timestamp()
        start_time = end_time - (6 * 60 * 60) # Last 6 hours
        
        ret = api.get_time_price_series(exchange='NSE', token=token, starttime=start_time, endtime=end_time, interval=5)
        
        if not ret or not isinstance(ret, list):
            return None
            
        df = pd.DataFrame(ret)
        df = df.iloc[::-1].reset_index(drop=True) 
        
        df['inth'] = pd.to_numeric(df['inth']) # High
        df['intl'] = pd.to_numeric(df['intl']) # Low
        df['intc'] = pd.to_numeric(df['intc']) # Close
        df['intv'] = pd.to_numeric(df['intv']) # Volume
        
        if len(df) < 4:
            return None

        # 15-minute Opening Range
        first_15_mins = df.iloc[:3]
        orb_high = first_15_mins['inth'].max()
        orb_low = first_15_mins['intl'].min()

        latest_candle = df.iloc[-1]
        price = latest_candle['intc']
        avg_volume = df['intv'].tail(10).mean()

        signal = None
        
        # Bullish Breakout
        if price > orb_high and latest_candle['intv'] > avg_volume:
            sl = orb_low
            risk = price - sl
            target = price + (risk * 2)
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
    
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(tz)
    
    # Run hours: 8:30 AM to 4:00 PM IST
    market_open = now.replace(hour=8, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    
    if now.weekday() > 4 or not (market_open <= now <= market_close):
        print("Market closed — bot standby mode")
        return

    api = shoonya_login()
    
    if not api:
        print("Login failed. Check GitHub Secrets.")
        return

    print("✅ Login Successful! Scanning stocks...")
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
