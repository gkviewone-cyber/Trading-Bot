import yfinance as yf
import pandas as pd
import ta
import requests
from datetime import datetime
import pytz

BOT_TOKEN = "8677504246:AAFq6kPDoX410tz3kodv5ZQaqviiZ5JEfBc"
CHAT_ID = "8791344518"

CAPITAL = 600
LEVERAGE = 10   # intraday leverage estimate

stocks = {
    "SBIN": "SBIN.NS",
    "AXISBANK": "AXISBANK.NS",
    "ITC": "ITC.NS",
    "WIPRO": "WIPRO.NS",
    "POWERGRID": "POWERGRID.NS",
    "NTPC": "NTPC.NS",
    "TATAMOTORS": "TATAMOTORS.NS"
}

indices = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "SENSEX": "^BSESN"
}


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": message})


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

    vol = df["Volume"]
    price = (df["High"] + df["Low"] + df["Close"]) / 3

    return (price * vol).cumsum() / vol.cumsum()


def calculate_quantity(price):

    buying_power = CAPITAL * LEVERAGE

    qty = int(buying_power / price)

    if qty < 1:
        qty = 1

    return qty


def check_stock_signal(name, symbol):

    df = yf.download(symbol, period="1d", interval="5m")

    if df.empty:
        return None

    price = df["Close"].iloc[-1]

    if price > 1000:
        return None

    df["VWAP"] = vwap(df)

    rsi = ta.momentum.RSIIndicator(df["Close"]).rsi()

    last_rsi = rsi.iloc[-1]

    last_price = df["Close"].iloc[-1]

    last_vwap = df["VWAP"].iloc[-1]

    qty = calculate_quantity(last_price)

    if last_price > last_vwap and last_rsi < 40:

        target = round(last_price * 1.01, 2)
        sl = round(last_price * 0.995, 2)

        return f"""📈 BUY {name}
Entry: ₹{last_price}
Target: ₹{target}
SL: ₹{sl}
Qty: {qty} shares"""


    if last_price < last_vwap and last_rsi > 60:

        target = round(last_price * 0.99, 2)
        sl = round(last_price * 1.005, 2)

        return f"""📉 SELL {name}
Entry: ₹{last_price}
Target: ₹{target}
SL: ₹{sl}
Qty: {qty} shares"""

    return None


def check_index_signal(name, symbol):

    df = yf.download(symbol, period="1d", interval="5m")

    if df.empty:
        return None

    close = df["Close"]

    ema9 = close.ewm(span=9).mean()
    ema21 = close.ewm(span=21).mean()

    if ema9.iloc[-1] > ema21.iloc[-1]:

        return f"🔥 BUY {name} TREND UP"

    if ema9.iloc[-1] < ema21.iloc[-1]:

        return f"🔻 SELL {name} TREND DOWN"

    return None


def run_bot():

    if not market_open():
        return

    for name, symbol in stocks.items():

        signal = check_stock_signal(name, symbol)

        if signal:
            send_telegram(signal)

    for name, symbol in indices.items():

        signal = check_index_signal(name, symbol)

        if signal:
            send_telegram(signal)


run_bot()
