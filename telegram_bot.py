import yfinance as yf
import requests
import time

BOT_TOKEN = "8677504246:AAFq6kPDoX410tz3kodv5ZQaqviiZ5JEfBc"
CHAT_ID = "8791344518"

stocks = {
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS",
    "ITC": "ITC.NS",
    "LT": "LT.NS",
    "AXISBANK": "AXISBANK.NS",
    "KOTAKBANK": "KOTAKBANK.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "HCLTECH": "HCLTECH.NS",
    "WIPRO": "WIPRO.NS",
    "MARUTI": "MARUTI.NS",
    "TITAN": "TITAN.NS"
}

for name, ticker in stocks.items():
    try:
        data = yf.Ticker(ticker).history(period="1d", interval="1m")
        last_price = data['Close'][-1]
        message = f"{name}: {last_price}"
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={message}"
        requests.get(url)
        time.sleep(1)  # pause 1 second to avoid Telegram rate limit
    except Exception as e:
        print(f"Error for {name}: {e}")
