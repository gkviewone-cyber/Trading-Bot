import yfinance as yf
import requests
from datetime import datetime
import pytz
import time


BOT_TOKEN = "8677504246:AAFq6kPDoX410tz3kodv5ZQaqviiZ5JEfBc"
CHAT_ID = "8791344518"


MAX_PRICE = 500


# STOCKS UNDER ₹500

stocks = {

"SBIN":"SBIN.NS",
"ITC":"ITC.NS",
"WIPRO":"WIPRO.NS",
"NTPC":"NTPC.NS",
"POWERGRID":"POWERGRID.NS",
"TATAMOTORS":"TATAMOTORS.NS",
"COALINDIA":"COALINDIA.NS",
"IOC":"IOC.NS",
"ONGC":"ONGC.NS",
"PNB":"PNB.NS",
"CANBK":"CANBK.NS",
"IDFCFIRSTB":"IDFCFIRSTB.NS",
"BHEL":"BHEL.NS",
"SAIL":"SAIL.NS",
"IRFC":"IRFC.NS",
"NBCC":"NBCC.NS"

}


# INDEX SYMBOLS

indices = {

"NIFTY":"^NSEI",
"BANKNIFTY":"^NSEBANK",
"SENSEX":"^BSESN"

}


sent_today = set()


def send_telegram(message):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": message
    })


def market_open():

    india = pytz.timezone("Asia/Kolkata")

    now = datetime.now(india)

    if now.weekday() >= 5:
        return False

    start = now.replace(hour=9, minute=20, second=0)
    end = now.replace(hour=15, minute=30, second=0)

    return start <= now <= end


def breakout_logic(symbol, name, is_index=False):

    try:

        if name in sent_today:
            return


        data = yf.download(symbol, period="1d", interval="5m")

        if data.empty:
            return


        first_20 = data.between_time("09:15","09:20")

        if first_20.empty:
            return


        range_high = first_20["High"].max()
        range_low = first_20["Low"].min()

        last_price = data["Close"].iloc[-1]


        if not is_index:
            if last_price > MAX_PRICE:
                return


        avg_volume = data["Volume"].mean()
        last_volume = data["Volume"].iloc[-1]


        # BUY BREAKOUT

        if last_price > range_high and last_volume > avg_volume:

            entry = round(last_price,2)
            sl = round(range_low,2)
            target = round(entry * 1.02,2)


            message = f"""
🚨 9:20 BREAKOUT BUY

{name}

Entry: {entry}
SL: {sl}
Target: {target}
"""

            send_telegram(message)
            print(message)

            sent_today.add(name)


        # SELL BREAKDOWN

        elif last_price < range_low and last_volume > avg_volume:

            entry = round(last_price,2)
            sl = round(range_high,2)
            target = round(entry * 0.98,2)


            message = f"""
🚨 9:20 BREAKOUT SELL

{name}

Entry: {entry}
SL: {sl}
Target: {target}
"""

            send_telegram(message)
            print(message)

            sent_today.add(name)


    except:

        pass


def scan_market():

    if not market_open():
        return


    for name, symbol in indices.items():

        breakout_logic(symbol, name, True)


    for name, symbol in stocks.items():

        breakout_logic(symbol, name)


while True:

    scan_market()

    time.sleep(300)
