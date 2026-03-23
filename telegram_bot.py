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

    data = yf.download(symbol, period="1d", interval="5m")

    if data.empty:
        return None

    close = data["Close"].squeeze()
    volume = data["Volume"].squeeze()

    rsi = ta.momentum.RSIIndicator(close).rsi()
    ema9 = ta.trend.EMAIndicator(close, window=9).ema_indicator()
    ema21 = ta.trend.EMAIndicator(close, window=21).ema_indicator()

    last_price = close.iloc[-1]
    last_rsi = rsi.dropna().iloc[-1]
    last_ema9 = ema9.dropna().iloc[-1]
    last_ema21 = ema21.dropna().iloc[-1]

    avg_volume = volume.mean()
    last_volume = volume.iloc[-1]

    if last_rsi < 35 and last_ema9 > last_ema21 and last_volume > avg_volume:

        entry = round(last_price, 2)
        sl = round(entry * 0.99, 2)
        target = round(entry * 1.02, 2)

        return f"✅ BUY\nEntry: {entry}\nSL: {sl}\nTarget: {target}"

    elif last_rsi > 65 and last_ema9 < last_ema21 and last_volume > avg_volume:

        entry = round(last_price, 2)
        sl = round(entry * 1.01, 2)
        target = round(entry * 0.98, 2)

        return f"❌ SELL\nEntry: {entry}\nSL: {sl}\nTarget: {target}"

    return None


def scan_market():

    message = "📊 INTRADAY TRADE SIGNALS\n\n"

    signal_found = False

    for name, symbol in stocks.items():

        signal = get_signal(symbol)

        if signal:
            signal_found = True
            message += f"{name}\n{signal}\n\n"

    if signal_found:
        send_telegram(message)
        print(message)
    else:
        print("No strong signals now")


scan_market()
