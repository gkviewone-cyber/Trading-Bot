import yfinance as yf
import pandas as pd
import ta
import requests
from datetime import datetime
import pytz

BOT_TOKEN = "8677504246:AAFq6kPDoX410tz3kodv5ZQaqviiZ5JEfBc"
CHAT_ID = "8791344518"

CAPITAL = 1400   # 800 + 600 combined capital
LEVERAGE = 10

stocks = {

"SBIN":"SBIN.NS",
"AXISBANK":"AXISBANK.NS",
"ITC":"ITC.NS",
"WIPRO":"WIPRO.NS",
"POWERGRID":"POWERGRID.NS",
"NTPC":"NTPC.NS",
"TATAMOTORS":"TATAMOTORS.NS",
"RELIANCE":"RELIANCE.NS",
"HDFCBANK":"HDFCBANK.NS",
"ICICIBANK":"ICICIBANK.NS",
"INFY":"INFY.NS",
"LT":"LT.NS",
"KOTAKBANK":"KOTAKBANK.NS",
"BHARTIARTL":"BHARTIARTL.NS",
"ADANIENT":"ADANIENT.NS",
"HINDUNILVR":"HINDUNILVR.NS",
"ULTRACEMCO":"ULTRACEMCO.NS",
"BAJFINANCE":"BAJFINANCE.NS",
"MARUTI":"MARUTI.NS"
}

indices = {

"NIFTY":"^NSEI",
"BANKNIFTY":"^NSEBANK",
"SENSEX":"^BSESN"

}


def send_telegram(message):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    requests.post(url,data={"chat_id":CHAT_ID,"text":message})


def market_open():

    india=pytz.timezone("Asia/Kolkata")

    now=datetime.now(india)

    if now.weekday()>=5:

        return False

    if now.hour<9:

        return False

    if now.hour==9 and now.minute<20:

        return False

    if now.hour>15:

        return False

    if now.hour==15 and now.minute>30:

        return False

    return True


def quantity(price):

    buying_power=CAPITAL*LEVERAGE

    qty=int(buying_power/price)

    if qty<1:

        qty=1

    return qty


def vwap(df):

    vol=df["Volume"]

    price=(df["High"]+df["Low"]+df["Close"])/3

    return (price*vol).cumsum()/vol.cumsum()


def strategy(symbol,name):

    df=yf.download(symbol,period="1d",interval="5m")

    if df.empty:

        return None

    df["VWAP"]=vwap(df)

    df["EMA9"]=df["Close"].ewm(span=9).mean()

    df["EMA21"]=df["Close"].ewm(span=21).mean()

    rsi=ta.momentum.RSIIndicator(df["Close"]).rsi()

    price=df["Close"].iloc[-1]

    last_vwap=df["VWAP"].iloc[-1]

    last_ema9=df["EMA9"].iloc[-1]

    last_ema21=df["EMA21"].iloc[-1]

    last_rsi=rsi.iloc[-1]

    qty=quantity(price)

    if price>last_vwap and last_ema9>last_ema21 and last_rsi<40 and price<1000:

        target=round(price*1.01,2)

        sl=round(price*0.995,2)

        return f"""📈 BUY {name}

Entry ₹{price}

Target ₹{target}

SL ₹{sl}

Qty {qty}"""

    if price<last_vwap and last_ema9<last_ema21 and last_rsi>60 and price<1000:

        target=round(price*0.99,2)

        sl=round(price*1.005,2)

        return f"""📉 SELL {name}

Entry ₹{price}

Target ₹{target}

SL ₹{sl}

Qty {qty}"""

    return None


def index_strategy(symbol,name):

    df=yf.download(symbol,period="1d",interval="5m")

    if df.empty:

        return None

    ema9=df["Close"].ewm(span=9).mean()

    ema21=df["Close"].ewm(span=21).mean()

    if ema9.iloc[-1]>ema21.iloc[-1]:

        return f"🔥 BUY {name} OPTION TREND UP"

    if ema9.iloc[-1]<ema21.iloc[-1]:

        return f"🔻 SELL {name} OPTION TREND DOWN"

    return None


def run():

    if not market_open():

        return

    for name,symbol in stocks.items():

        signal=strategy(symbol,name)

        if signal:

            send_telegram(signal)

    for name,symbol in indices.items():

        signal=index_strategy(symbol,name)

        if signal:

            send_telegram(signal)


run()
