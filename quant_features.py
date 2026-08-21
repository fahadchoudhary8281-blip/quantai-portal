"""
Optimized Quantitative Analysis & Feature Engineering Module
Vectorized calculations for instant processing of 6 months (36,000+ candles) in <1 second.
"""

import sys
import os
CUR_DIR = os.path.dirname(os.path.abspath(__file__))
if CUR_DIR not in sys.path:
    sys.path.insert(0, CUR_DIR)

import numpy as np
import pandas as pd
from typing import Dict, Any

class QuantFeatureExtractor:
    def __init__(self, atr_period: int = 14):
        self.atr_period = atr_period

    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Computes high-speed vectorized quantitative features on OHLCV data.
        """
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]

        close = df['close']
        high = df['high']
        low = df['low']
        volume = df.get('tick_volume', df.get('volume', pd.Series(1, index=df.index)))

        # 1. EMAs & Trend Multipliers
        df['ema_9'] = close.ewm(span=9, adjust=False).mean()
        df['ema_21'] = close.ewm(span=21, adjust=False).mean()
        df['ema_50'] = close.ewm(span=50, adjust=False).mean()
        df['ema_200'] = close.ewm(span=200, adjust=False).mean()

        df['trend_ema_ratio'] = (df['ema_9'] - df['ema_21']) / (df['ema_21'] + 1e-8)
        df['macro_trend_ratio'] = (df['ema_50'] - df['ema_200']) / (df['ema_200'] + 1e-8)

        # 2. RSI (14) Vectorized
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-8)
        df['rsi_14'] = 100 - (100 / (1 + rs))

        # 3. ATR & Normalized ATR
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=self.atr_period).mean()
        df['natr'] = (df['atr'] / (close + 1e-8)) * 100

        # 4. Bollinger Bands (20, 2)
        bb_mean = close.rolling(window=20).mean()
        bb_std = close.rolling(window=20).std()
        df['bb_upper'] = bb_mean + (bb_std * 2)
        df['bb_lower'] = bb_mean - (bb_std * 2)
        df['bb_pct_b'] = (close - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-8)
        df['bb_bandwidth'] = (df['bb_upper'] - df['bb_lower']) / (bb_mean + 1e-8)

        # 5. MACD (12, 26, 9)
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        df['macd'] = ema_12 - ema_26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']

        # 6. Returns & Volatility
        df['log_ret_1'] = np.log(close / close.shift(1))
        df['log_ret_5'] = np.log(close / close.shift(5))
        df['rolling_vol_20'] = df['log_ret_1'].rolling(window=20).std()

        # 7. Candlestick Features
        candle_range = (high - low) + 1e-8
        df['body_pct'] = (close - df['open']).abs() / candle_range
        df['upper_wick_pct'] = (high - df[['open', 'close']].max(axis=1)) / candle_range
        df['lower_wick_pct'] = (df[['open', 'close']].min(axis=1) - low) / candle_range

        # 8. VWAP Proxy
        cum_vol = volume.cumsum()
        cum_vp = (close * volume).cumsum()
        df['vwap'] = cum_vp / (cum_vol + 1e-8)
        df['vwap_dist'] = (close - df['vwap']) / (df['vwap'] + 1e-8)

        # 9. Fast Hurst / Regime Proxy (Variance Ratio test proxy)
        var_1 = df['log_ret_1'].rolling(window=30).var()
        var_5 = (df['log_ret_5'] / np.sqrt(5)).rolling(window=30).var()
        df['regime_ratio'] = var_5 / (var_1 + 1e-8)

        return df.dropna().reset_index(drop=True)
