import os
import time
import threading
import schedule
import pyotp
import datetime
import pytz
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from NorenRestApiPy.NorenApi import NorenApi
from flask import Flask


# ============================================================
# 1. KEEP-ALIVE WEB SERVER
# ============================================================

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is awake, hunting for breakouts, and trailing profits! 🚀"

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, use_reloader=False)


# ============================================================
# 2. BOT CONFIGURATION
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID   = os.getenv('TELEGRAM_CHAT_ID')
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

MY_STOCKS = {
    # --- Budget-Friendly Movers (Price under ₹1000) ---
    "TATASTEEL":  "3499",
    "ZOMATO":     "76126",
    "ONGC":       "2475",
    "IDFCFIRSTB": "11184",
    "ITC":        "1660",
    "HINDALCO":   "1363",
    "SBIN":       "3045",
}

# Global Shoonya session
api_session       = None
_login_fail_count = 0


# ============================================================
# 3. SHOONYA LOGIN
# ============================================================

class ShoonyaApiPy(NorenApi):
    def __init__(self):
        NorenApi.__init__(
            self,
            host='https://api.shoonya.com/NorenWClientTP/',
            websocket='wss://api.shoonya.com/NorenWSTP/'
        )


def shoonya_login():
    """Login to Shoonya and return api object, or None on failure."""
    try:
        time.sleep(2)  # Small delay to avoid rate limiting
        api = ShoonyaApiPy()
        totp_secret = os.getenv('SHOONYA_TOTP')
        if not totp_secret:
            print("❌ Error: SHOONYA_TOTP secret is missing!")
            return None

        totp = pyotp.TOTP(totp_secret).now()
        print(f"🔑 Attempting login for user: {os.getenv('SHOONYA_USER')}")

        ret = api.login(
            userid      = os.getenv('SHOONYA_USER'),
            password    = os.getenv('SHOONYA_PWD'),
            twoFA       = totp,
            vendor_code = os.getenv('SHOONYA_VC'),
            api_secret  = os.getenv('SHOONYA_APIKEY'),
            imei        = 'cloud_bot'
        )

        if ret and ret.get('stat') == 'Ok':
            print("✅ Shoonya Login Successful!")
            return api
        else:
            print(f"❌ Shoonya Login Failed: {ret}")
            return None

    except Exception as e:
        print(f"❌ Shoonya Login Exception: {e}")
        return None


def scheduled_daily_login():
    """Force a fresh login every morning before market opens."""
    global api_session, _login_fail_count
    print("🌅 Daily re-login triggered at 08:50...")
    _login_fail_count = 0
    api_session = shoonya_login()
    if api_session:
        try:
            bot.send_message(TELEGRAM_CHAT_ID, "✅ Bot re-logged into Shoonya. Ready for today's market!")
        except Exception:
            pass
    else:
        try:
            bot.send_message(TELEGRAM_CHAT_ID, "❌ Daily re-login FAILED! Please check your Shoonya credentials.")
        except Exception:
            pass


# ============================================================
# 4. TELEGRAM HANDLERS
# ============================================================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "🚀 Bot is active and monitoring the market!\n\nCommands:\n/start - Show this message\n/status - Check bot status\n/stocks - List monitored stocks")

@bot.message_handler(commands=['status'])
def send_status(message):
    tz  = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(tz)
    session_status = "✅ Connected" if api_session else "❌ Disconnected"
    market_status  = "🟢 Open" if is_market_hours() else "🔴 Closed"
    bot.reply_to(message,
        f"🤖 *Bot Status*\n"
        f"Time: {now.strftime('%d %b %Y %H:%M:%S')} IST\n"
        f"Shoonya: {session_status}\n"
        f"Market: {market_status}",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['stocks'])
def send_stocks(message):
    stocks_list = "\n".join([f"• {s}" for s in MY_STOCKS.keys()])
    bot.reply_to(message, f"📋 *Monitored Stocks:*\n{stocks_list}", parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: True)
def handle_trade_execution(call):
    global api_session

    if call.data == "reject":
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="❌ *Trade Rejected.*",
            parse_mode="Markdown"
        )
        return

    if call.data.startswith("buy_"):
        symbol = call.data.split("_")[1]
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"⏳ *Executing order for {symbol}...*",
            parse_mode="Markdown"
        )

        if not api_session:
            api_session = shoonya_login()
        if not api_session:
            bot.send_message(call.message.chat.id, "❌ Error: Could not connect to Shoonya.")
            return

        try:
            token = MY_STOCKS[symbol]
            quote = api_session.get_quotes(exchange='NSE', token=token)

            if not quote or quote.get('stat') != 'Ok':
                bot.send_message(call.message.chat.id, f"❌ Could not fetch live price for {symbol}.")
                return

            live_price = float(quote['lp'])
            if live_price <= 0:
                bot.send_message(call.message.chat.id, f"❌ Invalid price for {symbol}: ₹{live_price}")
                return

            stop_loss_points  = round(live_price * 0.01,  1)
            target_points     = round(live_price * 0.05,  1)
            trail_jump_points = max(round(live_price * 0.005, 1), 0.05)

            order = api_session.place_order(
                buy_or_sell    = 'B',
                product_type   = 'B',
                exchange       = 'NSE',
                tradingsymbol  = f"{symbol}-EQ",
                quantity       = 10,
                price_type     = 'LMT',
                price          = live_price,
                bookloss_price = stop_loss_points,
                bookprofit_price = target_points,
                trail_price    = trail_jump_points,
                retention      = 'DAY'
            )

            if order and order.get('stat') == 'Ok':
                bot.send_message(
                    call.message.chat.id,
                    f"✅ *ORDER PLACED!*\n"
                    f"Stock: `{symbol}`\n"
                    f"Entry: ₹{live_price}\n"
                    f"Stop Loss: ₹{live_price - stop_loss_points:.2f}\n"
                    f"Target: ₹{live_price + target_points:.2f}",
                    parse_mode="Markdown"
                )
            else:
                reason = order.get('emsg', 'Unknown error') if order else 'No response'
                bot.send_message(
                    call.message.chat.id,
                    f"⚠️ *Order Failed!*\nReason: {reason}",
                    parse_mode="Markdown"
                )

        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Execution Error: {e}")


# ============================================================
# 5. MARKET SCANNER
# ============================================================

def is_market_hours():
    """Return True only between 9:20 AM and 3:25 PM IST, Mon-Fri."""
    tz  = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(tz)
    if now.weekday() > 4:  # 5=Sat, 6=Sun
        return False
    market_open  = now.replace(hour=9,  minute=20, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=25, second=0, microsecond=0)
    return market_open <= now <= market_close


def safe_get_quotes(api, symbol_name, token):
    """
    Safely fetch live quotes from Shoonya.
    Returns a dict with price/day_high/day_low/volume, or None on any failure.
    """
    try:
        quote = api.get_quotes(exchange='NSE', token=token)

        # Guard: None or empty
        if not quote:
            print(f"⚠️ [{symbol_name}] Empty response from Shoonya")
            return None

        # Guard: raw string instead of dict (the main bug!)
        if isinstance(quote, str):
            print(f"⚠️ [{symbol_name}] Unexpected string response: '{quote[:80]}'")
            return None

        # Guard: bad status
        if quote.get('stat') != 'Ok':
            print(f"⚠️ [{symbol_name}] stat={quote.get('stat')} | {quote.get('emsg', '')}")
            return None

        # Guard: missing or zero price fields (pre-market / holiday)
        lp = quote.get('lp', '0')
        h  = quote.get('h',  '0')
        l  = quote.get('l',  '0')
        v  = quote.get('v',  '0')

        if not lp or lp in ('0', '', None):
            print(f"⚠️ [{symbol_name}] Price not ready yet (lp={lp})")
            return None

        return {
            'price':    float(lp),
            'day_high': float(h) if h else 0.0,
            'day_low':  float(l) if l else 0.0,
            'volume':   float(v) if v else 0.0,
        }

    except (KeyError, ValueError, TypeError) as e:
        print(f"⚠️ [{symbol_name}] Parse error: {e}")
        return None
    except Exception as e:
        print(f"⚠️ [{symbol_name}] Unexpected error: {e}")
        return None


def check_orb_breakout(api, symbol_name, token):
    """Check if live price is breaking the day's high. Returns signal string or None."""
    data = safe_get_quotes(api, symbol_name, token)
    if not data:
        return None

    price    = data['price']
    day_high = data['day_high']

    print(f"👀 [{symbol_name}] LTP: ₹{price:.2f} | Day High: ₹{day_high:.2f}")

    if day_high > 0 and price >= day_high:
        return (
            f"🚀 *BULLISH BREAKOUT*\n"
            f"*Stock:* `{symbol_name}`\n"
            f"*Live Price:* ₹{price:.2f}\n"
            f"*Day High:* ₹{day_high:.2f}"
        )
    return None


def send_interactive_alert(symbol, text):
    """Send Telegram alert with Approve/Reject buttons."""
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Approve Buy", callback_data=f"buy_{symbol}"),
        InlineKeyboardButton("❌ Reject",      callback_data="reject")
    )
    bot.send_message(TELEGRAM_CHAT_ID, text, reply_markup=markup, parse_mode="Markdown")


def background_scanner():
    """Main scanner loop — runs every 5 minutes during market hours."""
    global api_session, _login_fail_count

    while True:
        try:
            # Run any scheduled tasks (daily re-login etc.)
            schedule.run_pending()

            if not is_market_hours():
                tz  = pytz.timezone('Asia/Kolkata')
                now = datetime.datetime.now(tz)
                print(f"⏰ Outside market hours ({now.strftime('%H:%M')} IST). Sleeping 60s...")
                time.sleep(60)
                continue

            # --- Login if session missing ---
            if not api_session:
                if _login_fail_count >= 3:
                    print("❌ 3 consecutive login failures. Cooling down 10 minutes...")
                    time.sleep(600)
                    _login_fail_count = 0
                    continue

                print(f"🔄 No session — attempting login (attempt {_login_fail_count + 1}/3)...")
                api_session = shoonya_login()

                if not api_session:
                    _login_fail_count += 1
                    print(f"❌ Login failed. Retrying in 60s...")
                    time.sleep(60)
                    continue
                else:
                    _login_fail_count = 0
                    print("✅ Session ready. Starting scan...")

            # --- Scan all stocks ---
            print(f"\n🔍 Scanning {len(MY_STOCKS)} stocks...")
            for symbol, token in MY_STOCKS.items():
                signal = check_orb_breakout(api_session, symbol, token)
                if signal:
                    send_interactive_alert(symbol, signal)
                time.sleep(0.5)  # Small delay between each API call

        except Exception as e:
            err_str = str(e).lower()
            print(f"⚠️ Scanner loop error: {e}")

            # Only reset session for auth-related errors
            if any(word in err_str for word in ['session', 'login', 'token', 'unauthorized', 'expired']):
                print("🔄 Auth error — will re-login on next cycle")
                api_session = None
            # For all other errors, keep the session alive

        time.sleep(300)  # Scan every 5 minutes


# ============================================================
# 6. MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":

    # Schedule daily re-login at 8:50 AM IST
    schedule.every().day.at("08:50").do(scheduled_daily_login)

    # Start keep-alive web server
    threading.Thread(target=run_server, daemon=True).start()
    print("✅ Web server started.")

    # Start market scanner
    threading.Thread(target=background_scanner, daemon=True).start()
    print("✅ Background scanner started.")

    # Initial login on startup
    print("🔄 Initial Shoonya login...")
    api_session = shoonya_login()
    if api_session:
        print("✅ Initial login successful.")
        try:
            bot.send_message(TELEGRAM_CHAT_ID, "🤖 *Trading Bot Started!*\nMonitoring market during 9:20 AM – 3:25 PM IST.", parse_mode="Markdown")
        except Exception:
            pass
    else:
        print("⚠️ Initial login failed. Will retry when market opens.")

    # Start Telegram bot polling
    print("✅ Bot is online and polling Telegram!")
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception:
        pass

    bot.infinity_polling(skip_pending=True)
