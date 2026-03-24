import yfinance as yf
import ta
import requests


# ======================
# TELEGRAM SETTINGS
# ======================

BOT_TOKEN = "8677504246:AAFq6kPDoX410tz3kodv5ZQaqviiZ5JEfBc"
CHAT_ID = "8791344518"


# ======================
# STOCK LIST
# ======================

stocks = {
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS"
}


# ======================
# TELEGRAM FUNCTION
# ======================

def send_telegram(message):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": message
        })
    except:
        print("Telegram send failed")


# ======================
# SIGNAL FUNCTION
# ======================

def get_signal(symbol):

    try:

        data = yf.download(symbol, period="5d", interval="5m")

        if data.empty:
            return "No data"

        close = data["Close"].squeeze()

        rsi = ta.momentum.RSIIndicator(close).rsi()

        ema9 = ta.trend.EMAIndicator(close, window=9).ema_indicator()
        ema21 = ta.trend.EMAIndicator(close, window=21).ema_indicator()

        last_rsi = rsi.dropna().iloc[-1]
        last_ema9 = ema9.dropna().iloc[-1]
        last_ema21 = ema21.dropna().iloc[-1]


        # SIGNAL CONDITIONS

        if last_rsi < 35 and last_ema9 > last_ema21:
            return "✅ BUY"

        elif last_rsi > 65 and last_ema9 < last_ema21:
            return "❌ SELL"

        else:
            return "⏳ WAIT"

    except:
        return "Error"


# ======================
# MAIN SCANNER FUNCTION
# ======================

def scan_market():

    message = "📊 INTRADAY SIGNAL SCANNER\n\n"

    signal_found = False

    for name, symbol in stocks.items():

        signal = get_signal(symbol)

        if signal in ["✅ BUY", "❌ SELL"]:
            signal_found = True

        message += f"{name} → {signal}\n"


    if not signal_found:

        message += "\n✅ Bot running normally"
        message += "\nNo strong signals now"


    print(message)

    send_telegram(message)


# ======================
# RUN BOT
# ======================

scan_market()
