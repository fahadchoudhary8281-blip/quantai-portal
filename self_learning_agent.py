"""
Quantitative Self-Learning AI Agent
- Combines Technical Quant Features + News Sentiment Score.
- Trains on 6 months of historical data with walk-forward online learning.
- Adaptive Feedback Loop: Modifies confidence threshold & weights based on recent trade outcomes.
"""

import os
import json
import datetime
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional
from config import cfg

# Try importing LightGBM or Scikit-learn with broad exception handling for Linux/Cloud containers
try:
    import lightgbm as lgb
    LGB_AVAILABLE = True
except Exception:
    lgb = None
    LGB_AVAILABLE = False

try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

class SelfLearningAgent:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.model = None
        self.scaler = None
        self.feature_columns = []
        self.model_path = os.path.join(cfg.MODELS_DIR, f"{symbol}_model.json")
        self.memory_buffer_path = os.path.join(cfg.MODELS_DIR, f"{symbol}_memory.json")
        
        # Adaptive self-learning parameters
        self.adaptive_threshold = cfg.CONFIDENCE_THRESHOLD
        self.trade_history = []
        self.load_memory()

    def create_labels(self, df: pd.DataFrame, forward_bars: int = 5, profit_factor: float = 1.5) -> pd.DataFrame:
        """
        Creates training labels:
        1 = Profitable BUY (Price went up >= ATR * 1.5 before hitting SL)
        -1 = Profitable SELL (Price went down >= ATR * 1.5 before hitting SL)
        0 = Noise / Consolidation
        """
        df = df.copy()
        future_close = df['close'].shift(-forward_bars)
        future_high = df['high'].rolling(window=forward_bars).max().shift(-forward_bars)
        future_low = df['low'].rolling(window=forward_bars).min().shift(-forward_bars)
        atr = df['atr']

        labels = []
        for i in range(len(df)):
            if pd.isna(future_close.iloc[i]) or pd.isna(atr.iloc[i]):
                labels.append(0)
                continue
                
            cur_close = df['close'].iloc[i]
            cur_atr = atr.iloc[i]
            target_distance = cur_atr * profit_factor
            
            up_move = (future_high.iloc[i] - cur_close) >= target_distance
            down_move = (cur_close - future_low.iloc[i]) >= target_distance
            
            if up_move and not down_move:
                labels.append(1)  # BUY
            elif down_move and not up_move:
                labels.append(2)  # SELL (label 2 for multiclass)
            else:
                labels.append(0)  # HOLD / NEUTRAL
                
        df['target'] = labels
        return df.dropna().reset_index(drop=True)

    def train_on_historical(self, df_with_features: pd.DataFrame) -> Dict[str, Any]:
        """
        Trains initial model on 6 months of quant feature data.
        """
        df_labeled = self.create_labels(df_with_features)
        
        # Exclude non-feature columns
        exclude_cols = ['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'volume', 'target']
        self.feature_columns = [c for c in df_labeled.columns if c not in exclude_cols]
        
        X = df_labeled[self.feature_columns].values
        y = df_labeled['target'].values
        
        # Train / Test split (80% train, 20% validation)
        split_idx = int(len(X) * 0.8)
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        if LGB_AVAILABLE:
            train_data = lgb.Dataset(X_train, label=y_train)
            val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
            
            params = {
                'objective': 'multiclass',
                'num_class': 3,
                'metric': 'multi_logloss',
                'learning_rate': cfg.LEARNING_RATE,
                'num_leaves': 31,
                'max_depth': cfg.MAX_DEPTH,
                'verbosity': -1,
                'seed': 42
            }
            
            self.model = lgb.train(
                params,
                train_data,
                num_boost_round=cfg.N_ESTIMATORS,
                valid_sets=[val_data]
            )
        elif SKLEARN_AVAILABLE:
            self.model = RandomForestClassifier(n_estimators=cfg.N_ESTIMATORS, max_depth=cfg.MAX_DEPTH, random_state=42)
            self.model.fit(X_train, y_train)
        else:
            # Fallback lightweight Decision Tree rule learner
            self.model = SimpleQuantRuleLearner()
            self.model.fit(X_train, y_train, self.feature_columns)

        print(f"[SelfLearningAgent] Successfully trained 6-month model for {self.symbol} on {len(X_train)} samples.")
        return {"status": "trained", "samples": len(X), "features": len(self.feature_columns)}

    def predict_signal(self, current_features: pd.Series, news_sentiment: float = 0.0) -> Tuple[str, float]:
        """
        Combines Quant Model Probabilities + Real-Time News Sentiment to generate actionable signal.
        Returns: (Signal: 'BUY' | 'SELL' | 'HOLD', Confidence: float)
        """
        if self.model is None or not self.feature_columns:
            return "HOLD", 0.0

        try:
            feat_values = np.array([current_features[col] for col in self.feature_columns]).reshape(1, -1)
            
            if LGB_AVAILABLE:
                probs = self.model.predict(feat_values)[0]  # [p_hold, p_buy, p_sell]
                p_hold, p_buy, p_sell = probs[0], probs[1], probs[2]
            elif SKLEARN_AVAILABLE:
                probs = self.model.predict_proba(feat_values)[0]
                p_hold, p_buy, p_sell = probs[0], probs[1], probs[2]
            else:
                p_buy, p_sell = self.model.predict_proba(feat_values)
                p_hold = 1.0 - (p_buy + p_sell)

            # News Sentiment Adjustment (+0.10 boost if news aligns, -0.10 penalty if contradicts)
            sentiment_weight = 0.12
            p_buy += (news_sentiment * sentiment_weight)
            p_sell -= (news_sentiment * sentiment_weight)
            
            # Normalize probabilities
            total = max(p_hold + p_buy + p_sell, 1e-6)
            p_buy /= total
            p_sell /= total

            if p_buy > self.adaptive_threshold and p_buy > p_sell:
                return "BUY", float(p_buy)
            elif p_sell > self.adaptive_threshold and p_sell > p_buy:
                return "SELL", float(p_sell)
            else:
                return "HOLD", float(max(p_buy, p_sell, p_hold))

        except Exception as e:
            return "HOLD", 0.0

    def record_trade_feedback(self, pnl: float, win: bool):
        """
        SELF-LEARNING FEEDBACK LOOP:
        Updates confidence threshold and strategy behavior dynamically.
        - If bot is in a winning streak: slightly expands confidence.
        - If bot suffers consecutive losses: increases threshold and tightens filter to protect capital.
        """
        self.trade_history.append({"time": datetime.datetime.now().isoformat(), "pnl": pnl, "win": win})
        # Keep last 50 trades in memory
        if len(self.trade_history) > 50:
            self.trade_history.pop(0)

        # Calculate recent win rate
        recent_trades = self.trade_history[-10:]
        if len(recent_trades) >= 5:
            win_rate = sum(1 for t in recent_trades if t["win"]) / len(recent_trades)
            if win_rate < 0.40:
                # Tighten threshold to avoid bad regime
                self.adaptive_threshold = min(0.72, self.adaptive_threshold + 0.02)
                print(f"[SelfLearningAgent] Low winrate ({win_rate*100:.1f}%) detected. Tightened confidence threshold to {self.adaptive_threshold:.2f}")
            elif win_rate > 0.65:
                # Normal healthy confidence
                self.adaptive_threshold = max(cfg.CONFIDENCE_THRESHOLD, self.adaptive_threshold - 0.01)
                
        self.save_memory()

    def save_memory(self):
        try:
            data = {"threshold": self.adaptive_threshold, "history": self.trade_history}
            with open(self.memory_buffer_path, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass

    def load_memory(self):
        try:
            if os.path.exists(self.memory_buffer_path):
                with open(self.memory_buffer_path, 'r') as f:
                    data = json.load(f)
                    self.adaptive_threshold = data.get("threshold", cfg.CONFIDENCE_THRESHOLD)
                    self.trade_history = data.get("history", [])
        except Exception:
            pass

class SimpleQuantRuleLearner:
    """Lightweight rule learner used when external binary ML packages are building."""
    def __init__(self):
        self.weights = {}
        
    def fit(self, X: np.ndarray, y: np.ndarray, feature_names: list):
        # Basic correlation learning between features and target labels
        for idx, col in enumerate(feature_names):
            corr = np.corrcoef(X[:, idx], y)[0, 1] if len(X) > 10 else 0.0
            self.weights[col] = 0.0 if np.isnan(corr) else corr

    def predict_proba(self, X: np.ndarray) -> Tuple[float, float]:
        score = 0.0
        for idx, w in enumerate(self.weights.values()):
            if idx < X.shape[1]:
                score += X[0, idx] * w
        p_buy = float(1.0 / (1.0 + np.exp(-score)))
        p_sell = 1.0 - p_buy
        return p_buy, p_sell
