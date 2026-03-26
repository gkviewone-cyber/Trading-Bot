import yfinance as yf
import requests
from datetime import datetime
import pytz

BOT_TOKEN = "8677504246:AAFq6kPDoX410tz3kodv5ZQaqviiZ5JEfBc"
CHAT_ID = "8791344518"

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

    try:

        url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

        requests.post(url,data={"chat_id":CHAT_ID,"text":message})

    except Exception as e:

        print("Telegram error:",e)


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


def stock_signal(symbol,name):

    try:

        df=yf.download(symbol,period="1d",interval="5m",progress=False)

        if df.empty:
            return None

        close=df["Close"]

        ema9=close.ewm(span=9).mean()

        ema21=close.ewm(span=21).mean()

        price=close.iloc[-1]

        if price>1000:
            return None

        if ema9.iloc[-1]>ema21.iloc[-1]:

            return f"📈 BUY {name} @ ₹{round(price,2)}"

        if ema9.iloc[-1]<ema21.iloc[-1]:

            return f"📉 SELL {name} @ ₹{round(price,2)}"

        return None

    except:

        return None


def index_signal(symbol,name):

    try:

        df=yf.download(symbol,period="1d",interval="5m",progress=False)

        if df.empty:
            return None

        close=df["Close"]

        ema9=close.ewm(span=9).mean()

        ema21=close.ewm(span=21).mean()

        if ema9.iloc[-1]>ema21.iloc[-1]:

            return f"🔥 BUY {name} CE (Trend Up)"

        if ema9.iloc[-1]<ema21.iloc[-1]:

            return f"🔻 BUY {name} PE (Trend Down)"

        return None

    except:

        return None


def run():

    if not market_open():

        return

    signals_sent=0


    for name,symbol in stocks.items():

        signal=stock_signal(symbol,name)

        if signal:

            send_telegram(signal)

            signals_sent+=1


    for name,symbol in indices.items():

        signal=index_signal(symbol,name)

        if signal:

            send_telegram(signal)

            signals_sent+=1


    if signals_sent==0:

        send_telegram("📊 Scanner active — waiting breakout setup")


run()
