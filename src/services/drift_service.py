"""Evidently orchestration — decoupled from routes."""
import pandas as pd
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset, TargetDriftPreset
from src.core.config import resolve_path, settings
from src.core.logging import logger


class DriftService:

    def export_recent_to_parquet(self, txn_repo, path: str | None = None,
                                 limit=5000):
        """DB se recent transactions nikaal ke parquet banata hai drift check ke liye."""
        path = str(resolve_path(path or "artifacts/current.parquet"))
        from src.ml.features import build_features
        rows = txn_repo.list_recent(limit)
        if not rows:
            return None
        df = pd.DataFrame([{
            "timestamp": r.timestamp, "amount": r.amount,
            "merchant_category": r.merchant_category, "device_type": r.device_type,
            "country": r.country, "user_avg_amount": r.user_avg_amount,
            "txn_count_1h": r.txn_count_1h} for r in rows])
        feats = build_features(df)
        feats["target"] = [int(r.is_fraud) for r in rows]
        feats.to_parquet(path, index=False)
        return path
    def run(self, current_path: str, output_html: str | None = None) -> dict:
        output_html = str(resolve_path(output_html or "artifacts/drift_report.html"))
        reference = pd.read_parquet(settings.reference_data_path)
        current = pd.read_parquet(resolve_path(current_path))
        report = Report(metrics=[DataDriftPreset(), TargetDriftPreset()])
        report.run(reference_data=reference, current_data=current)
        report.save_html(output_html)
        res = report.as_dict()["metrics"][0]["result"]
        out = {"dataset_drift": res["dataset_drift"],
               "drifted_share": res["share_of_drifted_columns"]}
        logger.info(f"Drift: {out}")
        return out