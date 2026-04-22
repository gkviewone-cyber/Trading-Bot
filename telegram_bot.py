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
    return "Bot is awake, hunting for breakouts! 🚀"

@app.route('/test-shoonya')
def test_shoonya():
    """Debug route — visit this to check if Shoonya is reachable from Render."""
    import requests
    try:
        r = requests.get('https://api.shoonya.com/NorenWClientTP/', timeout=10)
        return f"✅ Shoonya reachable | Status: {r.status_code} | Body: {r.text[:200]}"
    except Exception as e:
        return f"❌ Shoonya unreachable: {e}"

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
    "TATASTEEL":  "3499",
    "ZOMATO":     "76126",
    "ONGC":       "2475",
    "IDFCFIRSTB": "11184",
    "ITC":        "1660",
    "HINDALCO":   "1363",
    "SBIN":       "3045",
}

# Global state
api_session       = None
_login_lock       = threading.Lock()
_login_fail_count = 0
_last_login_time  = 0   # Timestamp of last login attempt


# ============================================================
# 3. SHOONYA LOGIN  (with rate-limit backoff)
# ============================================================

class ShoonyaApiPy(NorenApi):
    def __init__(self):
        NorenApi.__init__(
            self,
            host='https://api.shoonya.com/NorenWClientTP/',
            websocket='wss://api.shoonya.com/NorenWSTP/'
        )


def shoonya_login():
    """
    Login to Shoonya with threading lock (prevents double-login)
    and rate-limit backoff (min 60s between attempts).
    """
    global api_session, _last_login_time

    with _login_lock:
        # Reuse existing session if already logged in
        if api_session:
            return api_session

        # Rate limit: never attempt login more than once per 60 seconds
        elapsed = time.time() - _last_login_time
        if elapsed < 60:
            wait = int(60 - elapsed)
            print(f"⏳ Rate limit: waiting {wait}s before next login attempt...")
            time.sleep(wait)

        try:
            _last_login_time = time.time()
            time.sleep(2)

            api = ShoonyaApiPy()

            totp_secret = os.getenv('SHOONYA_TOTP')
            if not totp_secret:
                print("❌ SHOONYA_TOTP env variable is missing!")
                return None

            totp = pyotp.TOTP(totp_secret).now()
            user = os.getenv('SHOONYA_USER')
            print(f"🔑 Logging in as: {user}")

            ret = api.login(
                userid      = user,
                password    = os.getenv('SHOONYA_PWD'),
                twoFA       = totp,
                vendor_code = os.getenv('SHOONYA_VC'),
                api_secret  = os.getenv('SHOONYA_APIKEY'),
                imei        = 'cloud_bot'
            )

            if ret and ret.get('stat') == 'Ok':
                print("✅ Shoonya Login Successful!")
                api_session = api
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
    print("🌅 Daily re-login at 08:50 IST...")
    api_session       = None
    _login_fail_count = 0
    result = shoonya_login()
    try:
        if result:
            bot.send_message(TELEGRAM_CHAT_ID, "✅ Bot re-logged into Shoonya. Ready for today's market!")
        else:
            bot.send_message(TELEGRAM_CHAT_ID, "❌ Daily re-login FAILED! Check Render environment variables.")
    except Exception:
        pass


# ============================================================
# 4. TELEGRAM HANDLERS
# ============================================================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message,
        "🚀 *Trading Bot Active!*\n\n"
        "Commands:\n"
        "/status — Bot & market status\n"
        "/stocks — Monitored stocks\n"
        "/login  — Force re-login to Shoonya",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['status'])
def send_status(message):
    tz  = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(tz)
    bot.reply_to(message,
        f"🤖 *Bot Status*\n"
        f"Time: `{now.strftime('%d %b %Y %H:%M:%S')} IST`\n"
        f"Shoonya: {'✅ Connected' if api_session else '❌ Disconnected'}\n"
        f"Market: {'🟢 Open' if is_market_hours() else '🔴 Closed'}",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['stocks'])
def send_stocks(message):
    stocks_list = "\n".join([f"• {s}" for s in MY_STOCKS.keys()])
    bot.reply_to(message, f"📋 *Monitored Stocks:*\n{stocks_list}", parse_mode="Markdown")

@bot.message_handler(commands=['login'])
def force_login(message):
    global api_session
    bot.reply_to(message, "🔄 Forcing Shoonya re-login...")
    api_session = None
    result = shoonya_login()
    bot.reply_to(message, "✅ Re-login successful!" if result else "❌ Re-login failed. Check env vars.")


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
            bot.send_message(call.message.chat.id, "❌ Cannot connect to Shoonya. Try /login")
            return

        try:
            token      = MY_STOCKS[symbol]
            quote      = api_session.get_quotes(exchange='NSE', token=token)

            if not quote or isinstance(quote, str) or quote.get('stat') != 'Ok':
                bot.send_message(call.message.chat.id, f"❌ Could not fetch live price for {symbol}.")
                return

            live_price = float(quote['lp'])
            if live_price <= 0:
                bot.send_message(call.message.chat.id, f"❌ Invalid price ₹{live_price} for {symbol}")
                return

            stop_loss_points  = round(live_price * 0.01,  1)
            target_points     = round(live_price * 0.05,  1)
            trail_jump_points = max(round(live_price * 0.005, 1), 0.05)

            order = api_session.place_order(
                buy_or_sell      = 'B',
                product_type     = 'B',
                exchange         = 'NSE',
                tradingsymbol    = f"{symbol}-EQ",
                quantity         = 10,
                price_type       = 'LMT',
                price            = live_price,
                bookloss_price   = stop_loss_points,
                bookprofit_price = target_points,
                trail_price      = trail_jump_points,
                retention        = 'DAY'
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
                reason = order.get('emsg', 'Unknown') if order else 'No response'
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
    if now.weekday() > 4:
        return False
    market_open  = now.replace(hour=9,  minute=20, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=25, second=0, microsecond=0)
    return market_open <= now <= market_close


def safe_get_quotes(api, symbol_name, token):
    """Safely fetch live quotes. Returns dict or None on any failure."""
    try:
        quote = api.get_quotes(exchange='NSE', token=token)

        if not quote:
            print(f"⚠️ [{symbol_name}] Empty response")
            return None
        if isinstance(quote, str):
            print(f"⚠️ [{symbol_name}] String response: '{quote[:60]}'")
            return None
        if quote.get('stat') != 'Ok':
            print(f"⚠️ [{symbol_name}] stat={quote.get('stat')} | {quote.get('emsg','')}")
            return None

        lp = quote.get('lp', '0')
        h  = quote.get('h',  '0')

        if not lp or lp in ('0', '', None):
            print(f"⚠️ [{symbol_name}] Price not ready (lp={lp})")
            return None

        return {
            'price':    float(lp),
            'day_high': float(h) if h else 0.0,
            'day_low':  float(quote.get('l', 0) or 0),
            'volume':   float(quote.get('v', 0) or 0),
        }

    except Exception as e:
        print(f"⚠️ [{symbol_name}] Quote error: {e}")
        return None


def check_orb_breakout(api, symbol_name, token):
    """Returns alert string if breakout detected, else None."""
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
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Approve Buy", callback_data=f"buy_{symbol}"),
        InlineKeyboardButton("❌ Reject",      callback_data="reject")
    )
    bot.send_message(TELEGRAM_CHAT_ID, text, reply_markup=markup, parse_mode="Markdown")


def background_scanner():
    """
    Scanner loop. Waits 15s on startup so __main__ login finishes first.
    Uses exponential backoff on login failures to avoid rate limiting.
    """
    global api_session, _login_fail_count

    # Wait for __main__ to finish its login attempt first
    time.sleep(15)

    while True:
        try:
            schedule.run_pending()

            if not is_market_hours():
                tz  = pytz.timezone('Asia/Kolkata')
                now = datetime.datetime.now(tz)
                print(f"⏰ Market closed ({now.strftime('%H:%M')} IST). Sleeping 60s...")
                time.sleep(60)
                continue

            # Session missing during market hours — try login with backoff
            if not api_session:
                if _login_fail_count >= 3:
                    # Exponential backoff: 5 min, 10 min, 15 min...
                    wait_min = min(5 * _login_fail_count, 30)
                    print(f"❌ {_login_fail_count} failures. Cooling down {wait_min} min...")
                    time.sleep(wait_min * 60)
                    _login_fail_count = 0
                    continue

                print(f"🔄 No session — login attempt {_login_fail_count + 1}...")
                result = shoonya_login()
                if not result:
                    _login_fail_count += 1
                    backoff = 60 * (2 ** _login_fail_count)  # 120s, 240s, 480s
                    print(f"⏳ Backing off {backoff}s before next attempt...")
                    time.sleep(backoff)
                    continue
                else:
                    _login_fail_count = 0

            # Scan all stocks
            print(f"\n🔍 Scanning {len(MY_STOCKS)} stocks...")
            for symbol, token in MY_STOCKS.items():
                signal = check_orb_breakout(api_session, symbol, token)
                if signal:
                    send_interactive_alert(symbol, signal)
                time.sleep(0.5)

        except Exception as e:
            err = str(e).lower()
            print(f"⚠️ Scanner error: {e}")
            if any(w in err for w in ['session', 'login', 'token', 'unauthorized', 'expired']):
                print("🔄 Auth error — will re-login next cycle")
                api_session = None

        time.sleep(300)


# ============================================================
# 6. MAIN — startup sequence
# ============================================================

if __name__ == "__main__":

    # STEP 1: Kill ghost Telegram sessions from previous crashed instances
    # Retry up to 5 times with increasing delay until Telegram releases the old session
    print("🧹 Clearing old Telegram sessions...")
    for attempt in range(5):
        try:
            bot.delete_webhook(drop_pending_updates=True)
            print(f"✅ Webhook cleared (attempt {attempt + 1})")
            time.sleep(8)  # Give Telegram time to release old long-poll connection
            break
        except Exception as e:
            print(f"⚠️ Webhook clear attempt {attempt + 1} failed: {e}")
            time.sleep(5)

    # STEP 2: Schedule daily re-login at 8:50 AM IST
    schedule.every().day.at("08:50").do(scheduled_daily_login)

    # STEP 3: Start Flask keep-alive server
    threading.Thread(target=run_server, daemon=True).start()
    print("✅ Web server started.")

    # STEP 4: Login to Shoonya ONCE — scanner thread will reuse this session
    print("🔄 Initial Shoonya login...")
    result = shoonya_login()
    if result:
        print("✅ Initial login successful.")
        try:
            bot.send_message(
                TELEGRAM_CHAT_ID,
                "🤖 *Trading Bot Started!*\n"
                "Scanning stocks 9:20 AM – 3:25 PM IST.\n"
                "Type /status to check connection.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    else:
        print("⚠️ Initial login failed. Will retry during market hours.")

    # STEP 5: Start scanner thread AFTER login attempt
    threading.Thread(target=background_scanner, daemon=True).start()
    print("✅ Background scanner started.")

    # STEP 6: Start Telegram polling with 409 auto-recovery loop
    # This is blocking — must be last
    print("✅ Bot polling started!")
    while True:
        try:
            bot.infinity_polling(
                skip_pending=True,
                timeout=60,
                long_polling_timeout=60,
                interval=1
            )
        except telebot.apihelper.ApiTelegramException as e:
            if '409' in str(e):
                # Another instance still running — wait for it to die
                print("⚠️ 409 Conflict — old instance still alive. Waiting 30s...")
                time.sleep(30)
                print("🔄 Retrying polling...")
            else:
                print(f"⚠️ Telegram API error: {e}")
                time.sleep(10)
        except Exception as e:
            print(f"⚠️ Polling crashed: {e}")
            time.sleep(10)
