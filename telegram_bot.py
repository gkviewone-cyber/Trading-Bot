import yfinance as yf
import pandas as pd
import ta
import requests
from datetime import datetime
import pytz

BOT_TOKEN = "8677504246:AAFq6kPDoX410tz3kodv5ZQaqviiZ5JEfBc"
CHAT_ID = "8791344518"

CAPITAL = 1400
LEVERAGE = 10

stocks = {
    "SBIN": "SBIN.NS",
    "AXISBANK": "AXISBANK.NS",
    "ITC": "ITC.NS",
    "WIPRO": "WIPRO.NS",
    "POWERGRID": "POWERGRID.NS",
    "NTPC": "NTPC.NS",
    "TATAMOTORS": "TATAMOTORS.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "IOC": "IOC.NS",
    "IRFC": "IRFC.NS",
    "YESBANK": "YESBANK.NS"
}


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})


def market_open():

    india = pytz.timezone("Asia/Kolkata")
    now = datetime.now(india)

    if now.weekday() >= 5:
        return False

    if now.hour < 9:
        return False

    if now.hour == 9 and now.minute < 15:
        return False

    if now.hour > 15:
        return False

    if now.hour == 15 and now.minute > 30:
        return False

    return True


def vwap(df):

    price = (df["High"] + df["Low"] + df["Close"]) / 3
    vol = df["Volume"]

    return (price * vol).cumsum() / vol.cumsum()


def quantity(price):

    buying_power = CAPITAL * LEVERAGE
    qty = int(buying_power / price)

    if qty < 1:
        qty = 1

    return qty


def check_signal(name, symbol):

    df = yf.download(symbol, period="1d", interval="5m")

    if df.empty:
        return None

    df["VWAP"] = vwap(df)

    df["EMA9"] = df["Close"].ewm(span=9).mean()
    df["EMA21"] = df["Close"].ewm(span=21).mean()

    rsi = ta.momentum.RSIIndicator(df["Close"]).rsi()

    last_price = df["Close"].iloc[-1]
    last_vwap = df["VWAP"].iloc[-1]
    last_ema9 = df["EMA9"].iloc[-1]
    last_ema21 = df["EMA21"].iloc[-1]
    last_rsi = rsi.iloc[-1]

    qty = quantity(last_price)

    if last_price > last_vwap and last_ema9 > last_ema21 and last_rsi > 50:

        target = round(last_price * 1.01, 2)
        sl = round(last_price * 0.995, 2)

        return f"""🚀 BUY {name}
Entry ₹{last_price}
Target ₹{target}
SL ₹{sl}
Qty {qty}"""

    if last_price < last_vwap and last_ema9 < last_ema21 and last_rsi < 50:

        target = round(last_price * 0.99, 2)
        sl = round(last_price * 1.005, 2)

        return f"""📉 SELL {name}
Entry ₹{last_price}
Target ₹{target}
SL ₹{sl}
Qty {qty}"""

    return None


def run_bot():

    if not market_open():
        return

    signals = []

    for name, symbol in stocks.items():

        signal = check_signal(name, symbol)

        if signal:
            signals.append(signal)

    if signals:

        for s in signals:
            send_telegram(s)

    else:

        send_telegram("📊 Scanner active — waiting breakout setup")


run_bot()
