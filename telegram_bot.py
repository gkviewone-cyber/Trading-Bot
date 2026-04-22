import os
from flask import Flask

# Initialize the Flask web server
app = Flask(__name__)

# 1. The Health Check (Keeps Render happy)
@app.route('/')
def home():
    return "🟢 Bot is online! The button receiver is listening..."

# 2. The Buy Button Route
@app.route('/buy/<symbol>')
def buy_stock(symbol):
    # (We will add the Shoonya order execution code here later)
    print(f"💰 BUY button clicked for {symbol}!")
    
    return f"""
    <html>
        <head><title>Order Approved</title></head>
        <body style="background-color: #121212; color: #00FF00; font-family: Arial; text-align: center; padding-top: 50px;">
            <h1>✅ BUY ORDER APPROVED</h1>
            <h2>Stock: {symbol}</h2>
            <p>Order logic is ready to be connected.</p>
        </body>
    </html>
    """

# 3. The Reject Button Route
@app.route('/reject/<symbol>')
def reject_stock(symbol):
    print(f"❌ Trade rejected for {symbol}.")
    
    return f"""
    <html>
        <head><title>Order Rejected</title></head>
        <body style="background-color: #121212; color: #FF4444; font-family: Arial; text-align: center; padding-top: 50px;">
            <h1>❌ TRADE REJECTED</h1>
            <h2>Stock: {symbol}</h2>
            <p>Staying out of this one.</p>
        </body>
    </html>
    """

if __name__ == "__main__":
    # Render assigns a dynamic port. This catches it.
    port = int(os.environ.get('PORT', 10000))
    # Run the server on all IP addresses (0.0.0.0) so the internet can reach it
    app.run(host='0.0.0.0', port=port)
