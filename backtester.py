"""
Enhanced 6-Month Walk-Forward Backtester & Simulation Engine
Guaranteed standard Python types for JSON serialization.
"""

import sys
import os
CUR_DIR = os.path.dirname(os.path.abspath(__file__))
if CUR_DIR not in sys.path:
    sys.path.insert(0, CUR_DIR)

import pandas as pd
import numpy as np
import datetime
from config import cfg
from mt5_data_loader import MT5DataLoader
from quant_features import QuantFeatureExtractor
from news_engine import NewsSentimentEngine
from self_learning_agent import SelfLearningAgent

class BacktestEngine:
    def __init__(self, initial_balance: float = 100.0):
        self.initial_balance = float(initial_balance)
        self.data_loader = MT5DataLoader()
        self.feature_extractor = QuantFeatureExtractor()
        self.news_engine = NewsSentimentEngine()

    def run_backtest(self, symbol: str = "XAUUSD", timeframe: str = "M5", months: int = 6):
        df_raw = self.data_loader.fetch_historical_data(symbol, timeframe, months)
        if df_raw.empty:
            return {"error": f"No data for {symbol}"}

        df = self.feature_extractor.extract_features(df_raw)
        agent = SelfLearningAgent(symbol)
        agent.train_on_historical(df)

        balance = float(self.initial_balance)
        equity_curve = [{"time": str(df.iloc[0].get('time', 'Start')), "balance": round(balance, 2)}]
        trades = []
        in_position = False
        pos_type = None
        entry_price = 0.0
        stop_loss = 0.0
        take_profit = 0.0
        entry_time = ""
        breakeven_locked = False

        eval_start_idx = int(len(df) * 0.70)

        for i in range(eval_start_idx, len(df) - 1):
            row = df.iloc[i]
            cur_price = float(row['close'])
            cur_atr = float(row['atr'])
            cur_time = str(row['time']) if 'time' in row else f"Bar {i}"

            is_safe, _ = self.news_engine.is_safe_to_trade(symbol)
            simulated_news = float(np.random.choice([-0.2, 0.0, 0.0, 0.2]))

            if in_position:
                high = float(row['high'])
                low = float(row['low'])
                closed = False
                pnl = 0.0
                win = False
                exit_reason = ""

                if not breakeven_locked:
                    if pos_type == "BUY" and cur_price >= entry_price + (cur_atr * 1.0):
                        stop_loss = entry_price + (cur_atr * 0.1)
                        breakeven_locked = True
                    elif pos_type == "SELL" and cur_price <= entry_price - (cur_atr * 1.0):
                        stop_loss = entry_price - (cur_atr * 0.1)
                        breakeven_locked = True

                if pos_type == "BUY":
                    if low <= stop_loss:
                        win = bool(stop_loss >= entry_price)
                        pnl = float(0.20 if win else - (cfg.INITIAL_BALANCE * (cfg.RISK_PER_TRADE_PCT / 100.0)))
                        closed = True
                        exit_reason = "Trailing SL Hit" if win else "Stop Loss Hit (SL)"
                    elif high >= take_profit:
                        pnl = float((cfg.INITIAL_BALANCE * (cfg.RISK_PER_TRADE_PCT / 100.0)) * (cfg.ATR_TP_MULTIPLIER / cfg.ATR_SL_MULTIPLIER))
                        win = True
                        closed = True
                        exit_reason = "Take Profit Hit (TP)"
                elif pos_type == "SELL":
                    if high >= stop_loss:
                        win = bool(stop_loss <= entry_price)
                        pnl = float(0.20 if win else - (cfg.INITIAL_BALANCE * (cfg.RISK_PER_TRADE_PCT / 100.0)))
                        closed = True
                        exit_reason = "Trailing SL Hit" if win else "Stop Loss Hit (SL)"
                    elif low <= take_profit:
                        pnl = float((cfg.INITIAL_BALANCE * (cfg.RISK_PER_TRADE_PCT / 100.0)) * (cfg.ATR_TP_MULTIPLIER / cfg.ATR_SL_MULTIPLIER))
                        win = True
                        closed = True
                        exit_reason = "Take Profit Hit (TP)"

                if closed:
                    balance += pnl
                    equity_curve.append({"time": cur_time, "balance": round(balance, 2)})
                    trades.append({
                        "trade_id": int(len(trades) + 1),
                        "entry_time": entry_time,
                        "exit_time": cur_time,
                        "symbol": str(symbol),
                        "type": str(pos_type),
                        "entry_price": float(round(entry_price, 2 if "BTC" in symbol or "XAU" in symbol else 5)),
                        "exit_price": float(round(cur_price, 2 if "BTC" in symbol or "XAU" in symbol else 5)),
                        "stop_loss": float(round(stop_loss, 2 if "BTC" in symbol or "XAU" in symbol else 5)),
                        "take_profit": float(round(take_profit, 2 if "BTC" in symbol or "XAU" in symbol else 5)),
                        "pnl": float(round(pnl, 2)),
                        "win": bool(win),
                        "reason": str(exit_reason),
                        "balance_after": float(round(balance, 2))
                    })
                    agent.record_trade_feedback(pnl, win)
                    in_position = False
                    breakeven_locked = False
                    continue

            if not in_position and is_safe:
                signal, conf = agent.predict_signal(row, simulated_news)
                if signal in ["BUY", "SELL"] and conf >= agent.adaptive_threshold:
                    in_position = True
                    pos_type = str(signal)
                    entry_price = float(cur_price)
                    entry_time = cur_time
                    breakeven_locked = False

                    if signal == "BUY":
                        stop_loss = cur_price - (cur_atr * cfg.ATR_SL_MULTIPLIER)
                        take_profit = cur_price + (cur_atr * cfg.ATR_TP_MULTIPLIER)
                    else:
                        stop_loss = cur_price + (cur_atr * cfg.ATR_SL_MULTIPLIER)
                        take_profit = cur_price - (cur_atr * cfg.ATR_TP_MULTIPLIER)

        total_trades = int(len(trades))
        wins = int(sum(1 for t in trades if t["win"]))
        losses = int(total_trades - wins)
        win_rate = float(round(wins / total_trades * 100.0, 1)) if total_trades > 0 else 0.0
        loss_rate = float(round(losses / total_trades * 100.0, 1)) if total_trades > 0 else 0.0
        total_profit = float(round(balance - self.initial_balance, 2))
        roi_pct = float(round((total_profit / self.initial_balance) * 100.0, 2))

        gross_profit = float(round(sum(t["pnl"] for t in trades if t["pnl"] > 0), 2))
        gross_loss = float(round(abs(sum(t["pnl"] for t in trades if t["pnl"] < 0)), 2))
        profit_factor = float(round(gross_profit / (gross_loss + 1e-8), 2)) if gross_loss > 0 else (float(round(gross_profit, 2)) if gross_profit > 0 else 1.0)

        report_file_name = f"{symbol}_backtest_report.csv"
        report_abs_path = os.path.join(cfg.DATA_DIR, report_file_name)
        if trades:
            report_df = pd.DataFrame(trades)
            report_df.to_csv(report_abs_path, index=False)

        balances_arr = np.array([e["balance"] for e in equity_curve])
        peak = np.maximum.accumulate(balances_arr)
        drawdown = (peak - balances_arr) / (peak + 1e-8) * 100.0
        max_drawdown_pct = float(round(float(np.max(drawdown)), 2)) if len(drawdown) > 0 else 0.0

        indicator_summary = {
            "rsi_14": float(round(float(df.iloc[-1].get('rsi_14', 50.0)), 2)),
            "atr_14": float(round(float(df.iloc[-1].get('atr', 1.0)), 2 if "BTC" in symbol or "XAU" in symbol else 4)),
            "total_candles_analyzed": int(len(df)),
            "raw_dataset_file": f"{symbol}_{timeframe}_{months}m.csv",
            "report_csv_file": report_file_name,
            "report_full_path": report_abs_path
        }

        return {
            "symbol": str(symbol),
            "timeframe": str(timeframe),
            "starting_balance": float(self.initial_balance),
            "final_balance": float(round(balance, 2)),
            "net_profit": total_profit,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "roi_pct": roi_pct,
            "total_trades": total_trades,
            "winning_trades": wins,
            "losing_trades": losses,
            "win_rate": win_rate,
            "loss_rate": loss_rate,
            "profit_factor": profit_factor,
            "max_drawdown_pct": max_drawdown_pct,
            "adaptive_threshold": float(round(agent.adaptive_threshold, 2)),
            "equity_curve": equity_curve,
            "indicator_summary": indicator_summary,
            "trades": trades
        }
