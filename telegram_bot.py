import os
import time
import threading
import pyotp
import datetime
import pytz
import pandas as pd
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from NorenRestApiPy.NorenApi import NorenApi
from flask import Flask

# --- 1. KEEP-ALIVE WEB SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is awake, hunting for breakouts, and trailing profits! 🚀"

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# --- 2. BOT CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

MY_STOCKS = {
    "TATASTEEL": "3499",
    "ZOMATO": "76126",
    "ONGC": "2475",
    "IDFCFIRSTB": "11184"
}

api_session = None

class ShoonyaApiPy(NorenApi):
    def __init__(self):
        NorenApi.__init__(self, host='https://api.shoonya.com/NorenWClientTP/', websocket='wss://api.shoonya.com/NorenWSTP/')

def shoonya_login():
    api = ShoonyaApiPy()
    totp_val = os.getenv('SHOONYA_TOTP')
    if not totp_val:
        print("❌ Error: SHOONYA_TOTP secret is missing!")
        return None
    totp = pyotp.TOTP(totp_val).now()
    ret = api.login(
        userid=os.getenv('SHOONYA_USER'), 
        password=os.getenv('SHOONYA_PWD'), 
        twoFA=totp, 
        vendor_code=os.getenv('SHOONYA_VC'), 
        api_secret=os.getenv('SHOONYA_APIKEY'), 
        imei='cloud_bot'
    )
    if ret and ret.get('stat') == 'Ok':
        print("✅ Shoonya Login Successful!")
        return api
    return None

# --- 3. TELEGRAM HANDLERS ---

# THIS IS THE PART THAT REPLIES TO /START
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "🚀 Bot is active and monitoring the market!")

@bot.callback_query_handler(func=lambda call: True)
def handle_trade_execution(call):
    global api_session
    if call.data == "reject":
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="❌ *Trade Rejected.*", parse_mode="Markdown")
        return
    if call.data.startswith("buy_"):
        symbol = call.data.split("_")[1]
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"⏳ *Executing for {symbol}...*", parse_mode="Markdown")
        if not api_session: api_session = shoonya_login()
        if not api_session:
            bot.send_message(call.message.chat.id, "❌ Error: Could not connect to Shoonya.")
            return
        try:
            token = MY_STOCKS[symbol]
            quote = api_session.get_quotes(exchange='NSE', token=token)
            live_price = float(quote['lp'])
            stop_loss_points = round(live_price * 0.01, 1)  
            target_points = round(live_price * 0.05, 1)     
            trail_jump_points = max(round(live_price * 0.005, 1), 0.05)
            order = api_session.place_order(
                buy_or_sell='B', product_type='B', exchange='NSE',
                tradingsymbol=f"{symbol}-EQ", quantity=10, price_type='LMT', 
                price=live_price, bookloss_price=stop_loss_points, 
                bookprofit_price=target_points, trail_price=trail_jump_points, retention='DAY'
            )
            if order and order.get('stat') == 'Ok':
                bot.send_message(call.message.chat.id, f"✅ **ORDER PLACED!**\nStock: {symbol}\nEntry: ₹{live_price}", parse_mode="Markdown")
            else:
                bot.send_message(call.message.chat.id, f"⚠️ **Failed!**\nReason: {order.get('emsg', 'Unknown')}", parse_mode="Markdown")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Execution Error: {e}")

# --- 4. MARKET SCANNER ---
def send_interactive_alert(symbol, text):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Approve Buy", callback_data=f"buy_{symbol}"), InlineKeyboardButton("❌ Reject", callback_data="reject"))
    bot.send_message(TELEGRAM_CHAT_ID, text, reply_markup=markup, parse_mode="Markdown")

def check_orb_breakout(api, symbol_name, token):
    try:
        end_time = datetime.datetime.now().timestamp()
        start_time = end_time - (6 * 60 * 60)
        ret = api.get_time_price_series(exchange='NSE', token=token, starttime=start_time, endtime=end_time, interval=5)
        if not ret or not isinstance(ret, list) or len(ret) < 4: return None
        df = pd.DataFrame(ret).iloc[::-1].reset_index(drop=True) 
        df[['inth', 'intl', 'intc', 'intv']] = df[['inth', 'intl', 'intc', 'intv']].apply(pd.to_numeric)
        orb_high = df.iloc[:3]['inth'].max()
        latest_candle = df.iloc[-1]
        price = latest_candle['intc']
        avg_volume = df['intv'].tail(10).mean()
        if price > orb_high and latest_candle['intv'] > avg_volume:
            return f"🚀 *BULLISH BREAKOUT* \n**Stock:** {symbol_name}\n**Price:** ₹{price:.2f}"
        return None
    except: return None

def background_scanner():
    global api_session
    while True:
        tz = pytz.timezone('Asia/Kolkata')
        now = datetime.datetime.now(tz)
        if now.weekday() <= 4 and (8 <= now.hour <= 16):
            if not api_session: api_session = shoonya_login()
            if api_session:
                for symbol, token in MY_STOCKS.items():
                    signal = check_orb_breakout(api_session, symbol, token)
                    if signal: send_interactive_alert(symbol, signal)
        time.sleep(300)

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=background_scanner, daemon=True).start()
    print("Clearing old connections...")
    try:
        bot.remove_webhook()
        time.sleep(2)
    except: pass
    print("Bot is online!")
    bot.infinity_polling(skip_pending=True)
