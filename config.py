"""
Quantitative & Real-Time News Self-Learning Trading Bot - Config
Optimized for:
- $100 Initial Balance (Micro-lot sizing, strict risk management)
- Multi-Asset: BTCUSD, XAUUSD (Gold), EURUSD, GBPUSD, USDJPY, AUDUSD
- M1 to M5 Scalping / Intraday Execution
- Safe Mode High-Impact News Filter
- 6-Month Walk-Forward Self-Learning Engine
"""

import os
from dataclasses import dataclass, field
from typing import List

@dataclass
class BotConfig:
    # 1. Supported Assets (BTC + Gold + Forex)
    SYMBOLS: List[str] = field(default_factory=lambda: ["XAUUSD", "BTCUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD"])
    
    # 2. Timeframes
    PRIMARY_TIMEFRAME: str = "M5"      # Main decision timeframe
    SECONDARY_TIMEFRAME: str = "M1"    # Micro-structure / entry refinement
    
    # 3. Capital & Risk Controls ($100 Balance Protection)
    INITIAL_BALANCE: float = 100.0
    RISK_PER_TRADE_PCT: float = 1.0     # 1% risk per trade = $1 max risk on $100
    MAX_DAILY_DRAWDOWN_PCT: float = 3.0 # Circuit breaker stops bot if daily loss > 3%
    MAX_TOTAL_DRAWDOWN_PCT: float = 8.0 # Hard stop for capital protection
    MAX_CONCURRENT_TRADES: int = 2      # Max open trades at any time
    MIN_LOT: float = 0.01               # 0.01 micro lot
    MAX_LOT: float = 0.05               # Max lot safeguard for $100 balance
    
    # 4. Dynamic Stops & Take Profit (ATR-based)
    USE_ATR_STOPS: bool = True
    ATR_PERIOD: int = 14
    ATR_SL_MULTIPLIER: float = 1.5      # Stop loss at 1.5x ATR
    ATR_TP_MULTIPLIER: float = 2.5      # Take profit at 2.5x ATR (1:1.67 Risk-to-Reward)
    TRAILING_STOP_ATR: float = 1.0      # Trailing stop activation
    
    # 5. Safe News Filter
    SAFE_NEWS_MODE: bool = True
    NEWS_HALT_MINUTES_BEFORE: int = 25  # Halt new entries 25 mins before high-impact news
    NEWS_RESUME_MINUTES_AFTER: int = 20 # Resume entries 20 mins after event
    HIGH_IMPACT_KEYWORDS: List[str] = field(default_factory=lambda: [
        "CPI", "NFP", "Non-Farm", "FOMC", "Federal Funds Rate", "Interest Rate",
        "ECB Press Conference", "BOE Rate", "Inflation Rate", "GDP", "Unemployment",
        "Bitcoin ETF", "Crypto Regulation", "SEC", "Halving"
    ])
    
    # 6. Self-Learning & Machine Learning Parameters
    TRAINING_MONTHS: int = 6            # 6 months of historical data
    WALK_FORWARD_DAYS: int = 14         # Self-learning adaptive update cycle (14 days)
    CONFIDENCE_THRESHOLD: float = 0.60  # Minimum model probability to trigger trade
    N_ESTIMATORS: int = 150
    LEARNING_RATE: float = 0.03
    MAX_DEPTH: int = 5
    
    # 7. Environment Paths
    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    MODELS_DIR: str = os.path.join(BASE_DIR, "models")
    LOGS_DIR: str = os.path.join(BASE_DIR, "logs")

cfg = BotConfig()
