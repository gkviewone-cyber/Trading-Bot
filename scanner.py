"""
scanner.py  —  One-shot market scanner for GitHub Actions
---------------------------------------------------------------
Runs every 5 minutes via GitHub Actions cron.
Login → Scan all stocks → Send Telegram alerts → Exit.
No Flask. No polling. No long-running process.
"""

import os
import sys
import time
import pyotp
import datetime
import pytz
import requests
from NorenRestApiPy.NorenApi import NorenApi


# ============================================================
# CONFIGURATION
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID   = os.getenv('TELEGRAM_CHAT_ID')

# Your Render button-handler URL
RENDER_URL = os.getenv('RENDER_URL', 'https://trading-bot-qsjg.onrender.com')

MY_STOCKS = {
    "TATASTEEL":  "3499",
    "ZOMATO":     "76126",
    "ONGC":       "2475",
    "IDFCFIRSTB": "11184",
    "ITC":        "1660",
    "HINDALCO":   "1363",
    "SBIN":       "3045",
}


# ============================================================
# HELPERS
# ============================================================

class ShoonyaApiPy(NorenApi):
    def __init__(self):
        NorenApi.__init__(
            self,
            host='https://api.shoonya.com/NorenWClientTP/',
            websocket='wss://api.shoonya.com/NorenWSTP/'
        )


def is_market_hours():
    tz  = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(tz)
    if now.weekday() > 4:
        return False
    market_open  = now.replace(hour=9,  minute=20, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=25, second=0, microsecond=0)
    return market_open <= now <= market_close


def send_telegram(text, reply_markup=None):
    """Send a Telegram message, optionally with inline buttons."""
    url  = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        import json
        data["reply_markup"] = json.dumps(reply_markup)
    try:
        r = requests.post(url, data=data, timeout=10)
        return r.json()
    except Exception as e:
        print(f"⚠️ Telegram send error: {e}")
        return None


def send_breakout_alert(symbol, price, day_high):
    """Send alert with Approve Buy / Reject inline buttons."""
    text = (
        f"🚀 *BULLISH BREAKOUT*\n"
        f"*Stock:* `{symbol}`\n"
        f"*Live Price:* ₹{price:.2f}\n"
        f"*Day High:* ₹{day_high:.2f}"
    )
    # Buttons point to your Render webhook handler
    reply_markup = {
        "inline_keyboard": [[
            {"text": "✅ Approve Buy", "url": f"{RENDER_URL}/buy/{symbol}"},
            {"text": "❌ Reject",      "url": f"{RENDER_URL}/reject/{symbol}"}
        ]]
    }
    send_telegram(text, reply_markup)
    print(f"📨 Alert sent for {symbol}")


def shoonya_login():
    try:
        api = ShoonyaApiPy()
        totp_secret = os.getenv('SHOONYA_TOTP')
        if not totp_secret:
            print("❌ SHOONYA_TOTP missing!")
            return None

        totp = pyotp.TOTP(totp_secret).now()
        ret  = api.login(
            userid      = os.getenv('SHOONYA_USER'),
            password    = os.getenv('SHOONYA_PWD'),
            twoFA       = totp,
            vendor_code = os.getenv('SHOONYA_VC'),
            api_secret  = os.getenv('SHOONYA_APIKEY'),
            imei        = 'cloud_bot'
        )
        if ret and ret.get('stat') == 'Ok':
            print("✅ Shoonya Login OK")
            return api
        else:
            print(f"❌ Login failed: {ret}")
            return None
    except Exception as e:
        print(f"❌ Login exception: {e}")
        return None


def safe_get_quotes(api, symbol, token):
    try:
        quote = api.get_quotes(exchange='NSE', token=token)
        if not quote or isinstance(quote, str):
            return None
        if quote.get('stat') != 'Ok':
            return None
        lp = quote.get('lp', '0')
        h  = quote.get('h',  '0')
        if not lp or lp in ('0', '', None):
            return None
        return {
            'price':    float(lp),
            'day_high': float(h) if h else 0.0,
        }
    except Exception as e:
        print(f"⚠️ [{symbol}] Quote error: {e}")
        return None


# ============================================================
# MAIN — one-shot scan
# ============================================================

def main():
    tz  = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(tz)
    print(f"🕐 Scanner triggered at {now.strftime('%d %b %Y %H:%M:%S')} IST")

    if not is_market_hours():
        print("⏰ Outside market hours. Exiting.")
        sys.exit(0)

    # Login
    api = shoonya_login()
    if not api:
        print("❌ Login failed. Exiting.")
        send_telegram("⚠️ *Scanner Error:* Shoonya login failed. Check credentials.")
        sys.exit(1)

    # Scan
    print(f"🔍 Scanning {len(MY_STOCKS)} stocks...")
    alerts_sent = 0

    for symbol, token in MY_STOCKS.items():
        data = safe_get_quotes(api, symbol, token)
        if not data:
            print(f"⚠️ [{symbol}] Skipped — no data")
            continue

        price    = data['price']
        day_high = data['day_high']
        print(f"👀 [{symbol}] LTP: ₹{price:.2f} | Day High: ₹{day_high:.2f}")

        if day_high > 0 and price >= day_high:
            send_breakout_alert(symbol, price, day_high)
            alerts_sent += 1

        time.sleep(0.5)  # Small delay between stocks

    print(f"✅ Scan complete. {alerts_sent} alert(s) sent.")
    sys.exit(0)


if __name__ == "__main__":
    main()
