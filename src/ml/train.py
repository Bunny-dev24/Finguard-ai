"""Trains XGBoost + LightGBM, selects best by PR-AUC, persists artifact."""
import json
import sys
from pathlib import Path

import joblib
import lightgbm as lgb
import pandas as pd
import xgboost as xgb
from sklearn.metrics import average_precision_score, classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.config import settings
from src.core.logging import logger
from src.ml.features import build_features


def _train_one(name, model, Xtr, ytr, Xte, yte):
    model.fit(Xtr, ytr)
    p = model.predict_proba(Xte)[:, 1]
    ap, auc = average_precision_score(yte, p), roc_auc_score(yte, p)
    logger.info(f"[{name}] PR-AUC={ap:.4f} ROC-AUC={auc:.4f}")
    return model, ap


def main():
    data_path = ROOT / "data" / "transactions.parquet"
    if not data_path.exists():
        from data.generate_data import generate

        data_path.parent.mkdir(parents=True, exist_ok=True)
        generate().to_parquet(data_path, index=False)

    df = pd.read_parquet(data_path)
    y = df["is_fraud"].values
    X = build_features(df)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    scale = (ytr == 0).sum() / max((ytr == 1).sum(), 1)

    candidates = {
        "xgboost": xgb.XGBClassifier(n_estimators=400, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, scale_pos_weight=scale,
            eval_metric="aucpr", n_jobs=-1, tree_method="hist"),
        "lightgbm": lgb.LGBMClassifier(n_estimators=500, num_leaves=48, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, class_weight="balanced", n_jobs=-1),
    }

    best, best_ap, best_name = None, -1, None
    for name, m in candidates.items():
        model, ap = _train_one(name, m, Xtr, ytr, Xte, yte)
        if ap > best_ap:
            best, best_ap, best_name = model, ap, name

    preds = (best.predict_proba(Xte)[:, 1] >= settings.fraud_threshold).astype(int)
    logger.info(f"Best={best_name}\n{classification_report(yte, preds, digits=3)}")

    model_path = Path(settings.model_path)
    reference_path = Path(settings.reference_data_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": best, "name": best_name, "columns": list(X.columns)}, model_path)
    ref = X.iloc[:5000].copy(); ref["target"] = y[:5000]
    ref.to_parquet(reference_path, index=False)
    with open(model_path.parent / "metrics.json", "w") as f:
        json.dump({"pr_auc": best_ap, "model": best_name}, f, indent=2)
    logger.info(f"Artifact saved → {model_path}")


if __name__ == "__main__":
    main()