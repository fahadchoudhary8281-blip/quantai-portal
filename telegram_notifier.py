"""
Telegram Instant Alert Notifier for Quant AI Bot
Sends real-time trade entries, exits, and news guard alerts directly to user phone.
"""

import urllib.request
import urllib.parse
import json
import logging
from config import cfg

class TelegramNotifier:
    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self.bot_token = bot_token or getattr(cfg, 'TELEGRAM_BOT_TOKEN', '')
        self.chat_id = chat_id or getattr(cfg, 'TELEGRAM_CHAT_ID', '')
        self.enabled = bool(self.bot_token and self.chat_id)

    def send_message(self, text: str) -> bool:
        if not self.enabled:
            return False
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }
            data = urllib.parse.urlencode(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=8) as response:
                return response.status == 200
        except Exception as e:
            logging.error(f"[TelegramNotifier] Error sending message: {e}")
            return False

    def notify_trade_entry(self, symbol: str, trade_type: str, price: float, sl: float, tp: float, conf: float):
        emoji = "🟢" if trade_type.upper() == "BUY" else "🔴"
        msg = (
            f"{emoji} *QUANTAI NEW TRADE OPENED*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Asset:* `{symbol}`\n"
            f"🎯 *Type:* `{trade_type.upper()}`\n"
            f"💵 *Entry Price:* `{price:.2f}`\n"
            f"🛑 *Stop Loss:* `{sl:.2f}`\n"
            f"🎯 *Take Profit:* `{tp:.2f}`\n"
            f"🧠 *AI Confidence:* `{conf*100:.1f}%`\n"
            f"🛡️ *Risk Sizing:* `1.0% ($1.00)`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 _Autonomous Quant AI Shield Active_"
        )
        return self.send_message(msg)

    def notify_trade_exit(self, symbol: str, trade_type: str, exit_price: float, pnl: float, win: bool, reason: str, balance: float):
        emoji = "🎉 ✅" if win else "⚠️ 🛑"
        pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        msg = (
            f"{emoji} *QUANTAI TRADE CLOSED*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Asset:* `{symbol}` ({trade_type.upper()})\n"
            f"🚪 *Exit Price:* `{exit_price:.2f}`\n"
            f"💰 *Net PnL:* `{pnl_str}`\n"
            f"📝 *Reason:* `{reason}`\n"
            f"💼 *Account Balance:* `${balance:.2f}`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📊 _Self-Learning Feedback Updated_"
        )
        return self.send_message(msg)

    def notify_news_guard(self, headline: str, impact: str = "HIGH"):
        msg = (
            f"⚠️ *NEWS GUARD SHIELD ACTIVATED*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📰 *Event:* `{headline}`\n"
            f"🚨 *Impact:* `{impact}`\n"
            f"⏸️ *Action:* Trading paused for 25 mins (Safe Mode)\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        return self.send_message(msg)
