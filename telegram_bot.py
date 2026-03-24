import yfinance as yf
import ta
import requests
import time

# 🔐 Replace with your Telegram bot token
BOT_TOKEN = "8677504246:AAFq6kPDoX410tz3kodv5ZQaqviiZ5JEfBc"

# 🔐 Replace with your chat ID
CHAT_ID = "8791344518"


# 📊 Stock list
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


# 📩 Telegram send function
def send_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message
        }
    )


# 📈 Signal generator function
def generate_signal(stock_name, ticker):

    try:
        data = yf.download(
            ticker,
            period="1d",
            interval="5m"
        )

        if data.empty:
            return f"{stock_name}: Data not available"

        close = data["Close"]

        # EMA indicators
        ema_9 = ta.trend.ema_indicator(close, window=9)
        ema_21 = ta.trend.ema_indicator(close, window=21)

        # RSI indicator
        rsi = ta.momentum.RSIIndicator(close).rsi()

        latest_price = close.iloc[-1]
        latest_ema9 = ema_9.iloc[-1]
        latest_ema21 = ema_21.iloc[-1]
        latest_rsi = rsi.iloc[-1]

        # 📊 Trading logic
        if latest_ema9 > latest_ema21 and latest_rsi < 70:
            signal = "BUY 📈"

        elif latest_ema9 < latest_ema21 and latest_rsi > 30:
            signal = "SELL 📉"

        else:
            signal = "HOLD ⏸️"

        return (
            f"{stock_name}\n"
            f"Price: {round(latest_price,2)}\n"
            f"RSI: {round(latest_rsi,2)}\n"
            f"Signal: {signal}"
        )

    except Exception as e:
        return f"{stock_name}: Error generating signal"


# 🚀 Main execution
def main():

    send_message("📊 Trading Signals Update")

    for stock_name, ticker in stocks.items():

        signal_message = generate_signal(stock_name, ticker)

        send_message(signal_message)

        # Prevent Telegram rate limit block
        time.sleep(1)


# ▶ Run bot
if __name__ == "__main__":
    main()
