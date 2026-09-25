"""Deterministic feature engineering — shared by training & serving (no skew)."""
from __future__ import annotations
import pandas as pd

# Fixed vocabularies — stateless, train & serve dono me identical.
# Single source of truth: data/generate_data.py imports these too,
# so synthetic data and real features never drift apart.
CATEGORIES = {
    "merchant_category": ["grocery", "electronics", "travel", "gambling", "crypto", "food"],
    "device_type": ["ios", "android", "web"],
    "country": ["IN", "US", "GB", "NG", "RU"],
}
CATEGORICAL = list(CATEGORIES.keys())
NUMERIC = ["amount", "hour", "day_of_week", "amount_to_avg_ratio", "txn_velocity_1h"]
FEATURE_COLUMNS = NUMERIC + [f"cat_{c}" for c in CATEGORICAL]


def _label_encode(series: pd.Series, vocab: list[str]) -> pd.Series:
    """Fixed-vocab label encoding — unknown value → -1. Stateless, no skew."""
    mapping = {v: i for i, v in enumerate(vocab)}
    return series.astype(str).map(mapping).fillna(-1).astype(float)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    ts = pd.to_datetime(df["timestamp"])
    df["hour"] = ts.dt.hour
    df["day_of_week"] = ts.dt.dayofweek
    df["amount_to_avg_ratio"] = df["amount"] / df.get("user_avg_amount", 1).replace(0, 1)
    df["txn_velocity_1h"] = df.get("txn_count_1h", 0).fillna(0)

    for c, vocab in CATEGORIES.items():
        df[f"cat_{c}"] = _label_encode(df[c], vocab)

    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0
    return df[FEATURE_COLUMNS].fillna(0.0)