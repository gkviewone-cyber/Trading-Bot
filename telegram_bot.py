import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is online! Waiting for button clicks..."

@app.route('/buy/<symbol>')
def buy_stock(symbol):
    # This is where we will write the Shoonya "Place Order" code later!
    return f"<h1>✅ BUY ORDER APPROVED FOR {symbol}</h1><p>Order logic coming soon!</p>"

@app.route('/reject/<symbol>')
def reject_stock(symbol):
    return f"<h1>❌ Trade rejected for {symbol}</h1><p>Staying out of this one.</p>"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
