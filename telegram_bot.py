import yfinance as yf
import ta
import time
import requests

BOT_TOKEN = "8677504246:AAFq6kPDoX410tz3kodv5ZQaqviiZ5JEfBc"
CHAT_ID = "8791344518"

stocks = {
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS"
}

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": message})


def get_signal(symbol):

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

    if last_rsi < 30 and last_ema9 > last_ema21:
        return "✅ BUY"
    elif last_rsi > 70 and last_ema9 < last_ema21:
        return "❌ SELL"
    else:
        return "⏳ WAIT"


def scan_market():

    message = "📊 INTRADAY SIGNAL SCANNER\n\n"

    for name, symbol in stocks.items():
        signal = get_signal(symbol)
        message += f"{name} → {signal}\n"

    print(message)
    send_telegram(message)


while True:
    scan_market()
    time.sleep(300)
