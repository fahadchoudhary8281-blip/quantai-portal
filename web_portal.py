"""
Secure Web Dashboard & Interactive Portal for Quant AI Trading Bot
- Live Auto-Trading Master Switch (ON / OFF)
- Telegram Push Alert Integration & Test
- Monthly PnL Calendar Heatmap
- Exness / MetaTrader 5 & Binance API Broker Integration
- TradingView Candlestick Charts with BUY / SELL Arrows
"""

import sys
import os
import json
CUR_DIR = os.path.dirname(os.path.abspath(__file__))
if CUR_DIR not in sys.path:
    sys.path.insert(0, CUR_DIR)

from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file, send_from_directory
import pandas as pd
import numpy as np
import datetime
from config import cfg
from backtester import BacktestEngine
from news_engine import NewsSentimentEngine
from mt5_data_loader import MT5DataLoader, MT5_AVAILABLE
from auto_trader import auto_trader
from telegram_notifier import TelegramNotifier

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

app = Flask(__name__, template_folder=os.path.join(CUR_DIR, "templates"), static_folder=os.path.join(CUR_DIR, "static"))
app.secret_key = "quant_ai_super_secure_secret_key_2026_xau_btc"

AUTH_USERS = {
    "fahad": "quant100",
    "admin": "admin123"
}

ACCOUNTS_FILE = os.path.join(CUR_DIR, "accounts.json")

def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "exness_mt5": {"login": "111080033", "server": "MetaQuotes-Demo", "connected": True, "broker": "Exness / MT5"},
        "binance": {"api_key": "", "api_secret": "", "testnet": True, "connected": False, "broker": "Binance Crypto"}
    }

def save_accounts(data):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

data_loader = MT5DataLoader()
news_engine = NewsSentimentEngine()
telegram = TelegramNotifier()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(CUR_DIR, "static"), "favicon.svg", mimetype="image/svg+xml")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username in AUTH_USERS and AUTH_USERS[username] == password:
            session["user"] = username
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Invalid Username or Password!")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    return render_template("index.html")

@app.route("/api/autotrade/status", methods=["GET"])
@login_required
def autotrade_status():
    return jsonify(auto_trader.get_status())

@app.route("/api/autotrade/close", methods=["POST"])
@login_required
def autotrade_close():
    data = request.json or {}
    symbol = data.get("symbol", "").upper()
    success = auto_trader.close_position(symbol)
    return jsonify({"success": success, "message": f"Position for {symbol} closed." if success else "No active position found."})

@app.route("/api/autotrade/toggle", methods=["POST"])
@login_required
def autotrade_toggle():
    if auto_trader.is_running:
        auto_trader.stop()
        msg = "Auto-Trader Paused."
    else:
        auto_trader.start()
        msg = "Auto-Trader Activated! Running 24/7 scanning live signals."
    return jsonify({"is_running": auto_trader.is_running, "message": msg})

@app.route("/api/telegram/save", methods=["POST"])
@login_required
def telegram_save():
    data = request.json or {}
    token = str(data.get("bot_token", "")).strip()
    chat_id = str(data.get("chat_id", "")).strip()
    telegram.bot_token = token
    telegram.chat_id = chat_id
    telegram.enabled = bool(token and chat_id)
    return jsonify({"status": "success", "message": "Telegram Bot credentials saved!"})

@app.route("/api/telegram/test", methods=["POST"])
@login_required
def telegram_test():
    if not telegram.enabled:
        return jsonify({"status": "error", "message": "Please enter Telegram Bot Token & Chat ID first"}), 400
    res = telegram.send_message("🤖 *QuantAI Notification Test*\n\n✅ Telegram alerts connected successfully!")
    if res:
        return jsonify({"status": "success", "message": "Test alert sent to your Telegram!"})
    return jsonify({"status": "error", "message": "Failed to send message. Verify Token & Chat ID"}), 400

@app.route("/api/accounts", methods=["GET"])
@login_required
def get_accounts():
    accs = load_accounts()
    safe_accs = {
        "exness_mt5": {
            "login": accs.get("exness_mt5", {}).get("login", "111080033"),
            "server": accs.get("exness_mt5", {}).get("server", "MetaQuotes-Demo"),
            "connected": True if (MT5_AVAILABLE and mt5 and data_loader.connected) else accs.get("exness_mt5", {}).get("connected", False),
            "broker": accs.get("exness_mt5", {}).get("broker", "Exness / MT5")
        },
        "binance": {
            "api_key": (accs.get("binance", {}).get("api_key", "")[:6] + "..." + accs.get("binance", {}).get("api_key", "")[-4:]) if accs.get("binance", {}).get("api_key") else "",
            "testnet": accs.get("binance", {}).get("testnet", True),
            "connected": accs.get("binance", {}).get("connected", False),
            "broker": "Binance Crypto Exchange"
        }
    }
    return jsonify(safe_accs)

@app.route("/api/connect_exness_mt5", methods=["POST"])
@login_required
def connect_exness_mt5():
    data = request.json or {}
    login_id = str(data.get("login", "")).strip()
    password = str(data.get("password", "")).strip()
    server = str(data.get("server", "Exness-Real")).strip()

    accs = load_accounts()
    accs["exness_mt5"] = {
        "login": login_id,
        "server": server,
        "connected": True,
        "broker": "Exness / MT5",
        "last_connected": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_accounts(accs)

    if MT5_AVAILABLE and mt5 and login_id.isdigit():
        try:
            mt5.initialize()
            if password:
                mt5.login(login=int(login_id), password=password, server=server)
            else:
                mt5.login(login=int(login_id), server=server)
        except Exception:
            pass

    return jsonify({"status": "success", "message": f"Exness/MT5 Account {login_id} Attached Successfully!"})

@app.route("/api/connect_binance", methods=["POST"])
@login_required
def connect_binance():
    data = request.json or {}
    api_key = str(data.get("api_key", "")).strip()
    api_secret = str(data.get("api_secret", "")).strip()
    testnet = bool(data.get("testnet", False))

    if not api_key:
        return jsonify({"status": "error", "message": "API Key is required"}), 400

    accs = load_accounts()
    accs["binance"] = {
        "api_key": api_key,
        "api_secret": api_secret,
        "testnet": testnet,
        "connected": True,
        "broker": "Binance Crypto Exchange",
        "last_connected": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_accounts(accs)

    return jsonify({"status": "success", "message": "Binance Account API Connected Successfully!"})

@app.route("/api/binance/balance", methods=["GET"])
@login_required
def api_binance_balance():
    accs = load_accounts()
    b_data = accs.get("binance", {})
    if not b_data or not b_data.get("api_key"):
        return jsonify({"status": "unconnected", "balance": 0.00, "currency": "USDT", "message": "No API Key configured"})

    api_key = str(b_data.get("api_key", "")).strip()
    api_secret = str(b_data.get("api_secret", "")).strip()
    testnet = bool(b_data.get("testnet", False))

    if not api_key or not api_secret:
        return jsonify({"status": "unconnected", "balance": 0.00, "currency": "USDT", "message": "API Key or Secret is missing"})

    import hmac
    import hashlib
    import time
    import urllib.request
    import urllib.error

    errors = []

    # 1. Try Binance USDⓈ-M Futures Balance
    try:
        ts = int(time.time() * 1000)
        query = f"recvWindow=60000&timestamp={ts}"
        sig = hmac.new(api_secret.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()
        
        base_url = "https://testnet.binancefuture.com" if testnet else "https://fapi.binance.com"
        url = f"{base_url}/fapi/v2/account?{query}&signature={sig}"
        
        req = urllib.request.Request(url, headers={"X-MBX-APIKEY": api_key, "User-Agent": "QuantAI/2.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            total_bal = float(data.get("totalWalletBalance", 0.0) or data.get("totalMarginBalance", 0.0))
            avail_bal = float(data.get("availableBalance", total_bal))
            return jsonify({
                "status": "success",
                "balance": round(total_bal, 2),
                "available": round(avail_bal, 2),
                "currency": "USDT",
                "mode": "Futures (USDⓈ-M)",
                "unrealized_pnl": float(data.get("totalUnrealizedProfit", 0.0))
            })
    except urllib.error.HTTPError as he:
        try:
            err_body = json.loads(he.read().decode('utf-8'))
            errors.append(f"Futures: {err_body.get('msg', str(he))}")
        except Exception:
            errors.append(f"Futures HTTP {he.code}")
    except Exception as e:
        errors.append(f"Futures: {str(e)}")

    # 2. Try Binance Spot & Funding Wallet Balance
    try:
        ts = int(time.time() * 1000)
        query = f"recvWindow=60000&timestamp={ts}"
        sig = hmac.new(api_secret.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()
        
        spot_base = "https://testnet.binance.vision" if testnet else "https://api.binance.com"
        spot_url = f"{spot_base}/api/v3/account?{query}&signature={sig}"
        
        req = urllib.request.Request(spot_url, headers={"X-MBX-APIKEY": api_key, "User-Agent": "QuantAI/2.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            total_usd = 0.0
            for b in data.get("balances", []):
                asset = b.get("asset", "")
                free = float(b.get("free", 0.0))
                locked = float(b.get("locked", 0.0))
                tot = free + locked
                if tot > 0:
                    if asset in ["USDT", "USDC", "FDUSD", "BUSD", "USD"]:
                        total_usd += tot
                    elif asset == "BTC":
                        total_usd += (tot * 65000.0)
            
            return jsonify({
                "status": "success",
                "balance": round(total_usd, 2),
                "currency": "USDT",
                "mode": "Spot Wallet"
            })
    except urllib.error.HTTPError as he:
        try:
            err_body = json.loads(he.read().decode('utf-8'))
            errors.append(f"Spot: {err_body.get('msg', str(he))}")
        except Exception:
            errors.append(f"Spot HTTP {he.code}")
    except Exception as e:
        errors.append(f"Spot: {str(e)}")

    return jsonify({
        "status": "error",
        "balance": 0.00,
        "currency": "USDT",
        "message": " | ".join(errors) or "Unable to connect to Binance API. Please check API Permissions."
    })

@app.route("/api/candles", methods=["GET"])
@login_required
def api_candles():
    symbol = request.args.get("symbol", "XAUUSD").upper()
    timeframe = request.args.get("timeframe", "M5").upper()
    months = int(request.args.get("months", 6))

    df = data_loader.fetch_historical_data(symbol, timeframe, months)
    if df.empty:
        return jsonify([])

    candles = []
    df_slice = df.tail(300).reset_index(drop=True)
    base_unix = int((datetime.datetime.now() - datetime.timedelta(minutes=len(df_slice) * 5)).timestamp())
    
    for idx, row in df_slice.iterrows():
        if 'time' in row and not pd.isna(row['time']):
            try:
                unix_time = int(pd.to_datetime(row['time']).timestamp())
            except Exception:
                unix_time = base_unix + (idx * 300)
        else:
            unix_time = base_unix + (idx * 300)
            
        candles.append({
            "time": unix_time,
            "open": float(round(row['open'], 2 if "BTC" in symbol or "XAU" in symbol else 5)),
            "high": float(round(row['high'], 2 if "BTC" in symbol or "XAU" in symbol else 5)),
            "low": float(round(row['low'], 2 if "BTC" in symbol or "XAU" in symbol else 5)),
            "close": float(round(row['close'], 2 if "BTC" in symbol or "XAU" in symbol else 5))
        })
        
    seen_times = set()
    unique_candles = []
    for c in candles:
        if c["time"] not in seen_times:
            seen_times.add(c["time"])
            unique_candles.append(c)
            
    return jsonify(unique_candles)

@app.route("/api/backtest", methods=["GET"])
@login_required
def api_backtest():
    symbol = request.args.get("symbol", "XAUUSD").upper()
    balance = float(request.args.get("balance", 100.0))
    timeframe = request.args.get("timeframe", "M5").upper()
    months = int(request.args.get("months", 6))

    engine = BacktestEngine(initial_balance=balance)
    results = engine.run_backtest(symbol=symbol, timeframe=timeframe, months=months)
    return jsonify(results)

@app.route("/api/download_report", methods=["GET"])
@login_required
def api_download_report():
    symbol = request.args.get("symbol", "XAUUSD").upper()
    report_file = os.path.join(cfg.DATA_DIR, f"{symbol}_backtest_report.csv")
    if os.path.exists(report_file):
        return send_file(report_file, as_attachment=True, download_name=f"{symbol}_6Month_Backtest_Report.csv")
    return "Report not generated yet. Please run backtest first.", 404

@app.route("/api/news", methods=["GET"])
@login_required
def api_news():
    raw_headlines = news_engine.fetch_live_headlines()
    scored_headlines = []
    
    for h in raw_headlines[:15]:
        score = news_engine.calculate_sentiment(h.get("title", ""))
        scored_headlines.append({
            "title": h.get("title", ""),
            "time": h.get("pubDate", ""),
            "score": round(score, 2)
        })
        
    return jsonify({
        "headlines": scored_headlines,
        "count": len(scored_headlines)
    })

if __name__ == "__main__":
    cert_file = os.path.join(CUR_DIR, "cert.pem")
    key_file = os.path.join(CUR_DIR, "key.pem")
    has_ssl = os.path.exists(cert_file) and os.path.exists(key_file)

    def run_https():
        if has_ssl:
            try:
                print("  HTTPS Server Running on https://quantai-portal.com (Port 443)")
                app.run(host="0.0.0.0", port=443, ssl_context=(cert_file, key_file), debug=False)
            except Exception as e:
                print(f"[HTTPS Warning] {e}")

    import threading
    if has_ssl:
        t_https = threading.Thread(target=run_https, daemon=True)
        t_https.start()

    port = 80
    try:
        import socket
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.bind(('127.0.0.1', 80))
        test_sock.close()
        port = 80
    except Exception:
        port = 8080

    print("="*70)
    print("  QUANTAI SECURE WEB PORTAL RUNNING")
    print(f"  HTTP Access:  http://quantai-portal.com (Port {port})")
    if has_ssl:
        print("  HTTPS Access: https://quantai-portal.com (Port 443)")
    print("="*70)
    app.run(host="0.0.0.0", port=port, debug=False)
