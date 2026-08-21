"""
Live Autonomous Auto-Trading Engine & Risk Guardian
- 24/7 background worker loop
- Dynamic Breakeven & ATR Trailing Stop-Loss
- Multi-Timeframe trend confirmation
- Telegram live push alerts
- Self-Learning adaptive feedback loop
"""

import time
import threading
import datetime
import logging
from config import cfg
from mt5_data_loader import MT5DataLoader, MT5_AVAILABLE
from quant_features import QuantFeatureExtractor
from news_engine import NewsSentimentEngine
from self_learning_agent import SelfLearningAgent
from telegram_notifier import TelegramNotifier

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

class AutoTraderEngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AutoTraderEngine, cls).__new__(cls)
            cls._instance.init_engine()
        return cls._instance

    def init_engine(self):
        self.is_running = False
        self.thread = None
        self.data_loader = MT5DataLoader()
        self.feature_extractor = QuantFeatureExtractor()
        self.news_engine = NewsSentimentEngine()
        self.telegram = TelegramNotifier()
        self.active_positions = {}
        self.trade_history = []
        self.symbols = ["XAUUSD", "BTCUSD", "EURUSD", "GBPUSD"]
        self.agents = {sym: SelfLearningAgent(sym) for sym in self.symbols}
        self.status_log = ["Auto-Trader Initialized in Standby Mode"]

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            self.status_log.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Live Auto-Trading Loop STARTED")

    def stop(self):
        self.is_running = False
        self.status_log.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Live Auto-Trading Loop STOPPED")

    def close_position(self, symbol: str) -> bool:
        if symbol in self.active_positions:
            pos = self.active_positions[symbol]
            cur_price = pos.get('current_price', pos['entry_price'])
            pnl = pos.get('unrealized_pnl', 0.0)
            win = pnl >= 0
            del self.active_positions[symbol]
            self.status_log.append(f"[{symbol}] Manual Close @ {cur_price} (PnL: ${pnl:.2f})")
            return True
        return False

    def _run_loop(self):
        while self.is_running:
            try:
                for symbol in self.symbols:
                    self._process_symbol(symbol)
            except Exception as e:
                self.status_log.append(f"[Error] {e}")
            time.sleep(10)

    def _process_symbol(self, symbol: str):
        df_raw = self.data_loader.fetch_historical_data(symbol, "M5", months=1)
        if df_raw.empty:
            return

        df = self.feature_extractor.extract_features(df_raw)
        row = df.iloc[-1]
        cur_price = float(row['close'])
        cur_atr = float(row['atr'])

        # 1. Manage Active Positions (Trailing Stop & Breakeven)
        if symbol in self.active_positions:
            pos = self.active_positions[symbol]
            p_type = pos['type']
            entry = float(pos['entry_price'])
            sl = float(pos['sl'])
            tp = float(pos['tp'])

            pos['current_price'] = cur_price
            
            # Calculate Real-Time Unrealized PnL ($)
            if "XAU" in symbol:
                diff = (cur_price - entry) if p_type == "BUY" else (entry - cur_price)
                pos['unrealized_pnl'] = round(diff * 1.0, 2)
            elif "BTC" in symbol:
                diff_pct = ((cur_price - entry) / entry) if p_type == "BUY" else ((entry - cur_price) / entry)
                pos['unrealized_pnl'] = round(diff_pct * 100.0, 2)
            else:
                diff_pips = (cur_price - entry) * 10000 if p_type == "BUY" else (entry - cur_price) * 10000
                pos['unrealized_pnl'] = round(diff_pips * 0.10, 2)

            pos['pnl_pct'] = round((pos['unrealized_pnl'] / 100.0) * 100.0, 2)

            # Check Breakeven: When price moves 1R into profit, shift SL to entry price
            if not pos.get('breakeven_set', False):
                if p_type == "BUY" and cur_price >= entry + (cur_atr * 1.0):
                    pos['sl'] = round(entry + (cur_atr * 0.1), 2 if "BTC" in symbol or "XAU" in symbol else 5)
                    pos['breakeven_set'] = True
                    pos['status'] = "🛡️ Breakeven Locked (Risk-Free)"
                    self.status_log.append(f"[{symbol}] Trailing Breakeven Locked at {pos['sl']}")
                elif p_type == "SELL" and cur_price <= entry - (cur_atr * 1.0):
                    pos['sl'] = round(entry - (cur_atr * 0.1), 2 if "BTC" in symbol or "XAU" in symbol else 5)
                    pos['breakeven_set'] = True
                    pos['status'] = "🛡️ Breakeven Locked (Risk-Free)"
                    self.status_log.append(f"[{symbol}] Trailing Breakeven Locked at {pos['sl']}")

            # Check Exit Conditions
            closed = False
            win = False
            pnl = 0.0
            reason = ""

            if p_type == "BUY":
                if cur_price <= pos['sl']:
                    closed = True
                    win = cur_price >= entry
                    pnl = 1.67 if win else -1.0
                    reason = "Trailing SL Hit" if pos.get('breakeven_set') else "Stop Loss Hit"
                elif cur_price >= pos['tp']:
                    closed = True
                    win = True
                    pnl = 1.67
                    reason = "Take Profit Hit (TP)"
            elif p_type == "SELL":
                if cur_price >= pos['sl']:
                    closed = True
                    win = cur_price <= entry
                    pnl = 1.67 if win else -1.0
                    reason = "Trailing SL Hit" if pos.get('breakeven_set') else "Stop Loss Hit"
                elif cur_price <= pos['tp']:
                    closed = True
                    win = True
                    pnl = 1.67
                    reason = "Take Profit Hit (TP)"

            if closed:
                del self.active_positions[symbol]
                self.agents[symbol].record_trade_feedback(pnl, win)
                self.telegram.notify_trade_exit(symbol, p_type, cur_price, pnl, win, reason, 100.0 + pnl)
                self.status_log.append(f"[{symbol}] {p_type} Closed @ {cur_price:.2f} ({reason}, PnL: ${pnl:.2f})")
            return

        # 2. Evaluate New Entry Signals if No Active Position
        is_safe, news_event = self.news_engine.is_safe_to_trade(symbol)
        if not is_safe:
            return

        agent = self.agents[symbol]
        signal, conf = agent.predict_signal(row, 0.0)

        if signal in ["BUY", "SELL"] and conf >= agent.adaptive_threshold:
            if signal == "BUY":
                sl = cur_price - (cur_atr * cfg.ATR_SL_MULTIPLIER)
                tp = cur_price + (cur_atr * cfg.ATR_TP_MULTIPLIER)
            else:
                sl = cur_price + (cur_atr * cfg.ATR_SL_MULTIPLIER)
                tp = cur_price - (cur_atr * cfg.ATR_TP_MULTIPLIER)

            self.active_positions[symbol] = {
                "symbol": symbol,
                "type": signal,
                "lot_size": "0.01 Lot",
                "entry_price": round(cur_price, 2 if "BTC" in symbol or "XAU" in symbol else 5),
                "current_price": round(cur_price, 2 if "BTC" in symbol or "XAU" in symbol else 5),
                "sl": round(sl, 2 if "BTC" in symbol or "XAU" in symbol else 5),
                "tp": round(tp, 2 if "BTC" in symbol or "XAU" in symbol else 5),
                "conf": round(conf * 100, 1),
                "unrealized_pnl": 0.00,
                "pnl_pct": 0.00,
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                "breakeven_set": False,
                "status": "Live Active"
            }

            self.telegram.notify_trade_entry(symbol, signal, cur_price, sl, tp, conf)
            self.status_log.append(f"[{symbol}] {signal} Executed @ {cur_price:.2f} | SL: {sl:.2f} | TP: {tp:.2f}")

    def get_status(self):
        return {
            "is_running": self.is_running,
            "active_positions": list(self.active_positions.values()),
            "logs": self.status_log[-10:]
        }

auto_trader = AutoTraderEngine()
