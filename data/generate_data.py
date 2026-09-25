"""Synthetic transaction generator with realistic fraud patterns.
Used by train.py and streaming/producer.py.

user_avg_amount and txn_count_1h come from real per-user rolling
history (shift/expanding + a 60min window), not random columns —
matches how get_velocity_features computes them at serve time."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ml.features import CATEGORIES  # same vocab train & serve use, no drift

MERCHANTS = CATEGORIES["merchant_category"]
DEVICES = CATEGORIES["device_type"]
COUNTRIES = CATEGORIES["country"]
COUNTRY_P = [0.55, 0.20, 0.10, 0.08, 0.07]


def _base_transactions(n: int, n_users: int, rng: np.random.Generator) -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="min"),
        "user_id": [f"user_{u}" for u in rng.integers(0, n_users, n)],
        "amount": rng.gamma(2.0, 40, n).round(2),
        "merchant_category": rng.choice(MERCHANTS, n),
        "device_type": rng.choice(DEVICES, n),
        "country": rng.choice(COUNTRIES, n, p=COUNTRY_P),
    })


def _inject_velocity_bursts(df: pd.DataFrame, rng: np.random.Generator,
                             burst_rate: float = 0.02) -> pd.DataFrame:
    """Simulates card testing / account takeover: same user firing
    several transactions a few minutes apart."""
    n_bursts = max(1, int(len(df) * burst_rate))
    seed_rows = df.sample(n=n_bursts, random_state=int(rng.integers(0, 1_000_000)))
    extra = []
    for _, row in seed_rows.iterrows():
        repeats = int(rng.integers(3, 8))
        for k in range(1, repeats + 1):
            extra.append({
                "timestamp": row["timestamp"] + pd.Timedelta(minutes=int(rng.integers(1, 10)) * k),
                "user_id": row["user_id"],
                "amount": round(float(rng.gamma(2.0, 60)), 2),
                "merchant_category": rng.choice(["gambling", "crypto", "electronics"]),
                "device_type": row["device_type"],
                "country": row["country"],
            })
    return pd.concat([df, pd.DataFrame(extra)], ignore_index=True)


def _add_user_history_features(df: pd.DataFrame) -> pd.DataFrame:
    """Rolling per-user stats, computed only from past rows (shift
    avoids leaking the current transaction into its own features)."""
    df = df.sort_values(["user_id", "timestamp"]).reset_index(drop=True)

    df["user_avg_amount"] = (
        df.groupby("user_id", group_keys=False)["amount"]
          .apply(lambda s: s.shift().expanding().mean())
    )
    df["user_avg_amount"] = df["user_avg_amount"].fillna(df["amount"])

    def _rolling_count_1h(g: pd.DataFrame) -> pd.Series:
        s = g.set_index("timestamp")["amount"].rolling("60min").count() - 1
        s.index = g.index
        return s

    df["txn_count_1h"] = (
        df.groupby("user_id", group_keys=False)[["timestamp", "amount"]]
          .apply(_rolling_count_1h)
          .astype(int)
    )
    return df


def generate(n: int = 60000, seed: int = 42, n_users: int = 4000) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    base = _base_transactions(n, n_users, rng)
    base = _inject_velocity_bursts(base, rng)
    base = _add_user_history_features(base)

    risk = (
        (base.amount > 250) * 0.40 +
        base.merchant_category.isin(["gambling", "crypto"]) * 0.35 +
        (base.txn_count_1h > 3) * 0.35 +
        base.country.isin(["NG", "RU"]) * 0.25
    )
    prob = 1 / (1 + np.exp(-(risk - 0.9) * 4))
    base["is_fraud"] = (rng.random(len(base)) < prob).astype(int)

    return base.sort_values("timestamp").reset_index(drop=True)


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parent
    data_dir.mkdir(exist_ok=True)
    df = generate()
    out = data_dir / "transactions.parquet"
    df.to_parquet(out, index=False)
    print(f"{len(df)} rows | fraud rate = {df.is_fraud.mean():.2%} → {out}")
