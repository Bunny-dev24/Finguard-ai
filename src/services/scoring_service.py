"""Core business logic: feature build → predict → persist → raise alert."""
from datetime import datetime

import pandas as pd
from src.ml.features import build_features
from src.repositories.transaction_repository import TransactionRepository
from src.services.alert_service import AlertService
from src.core.config import settings
from src.core.exceptions import ModelNotLoadedError


class ScoringService:
    def __init__(self, bundle: dict, txn_repo: TransactionRepository,
                 alert_service: AlertService):
        if not bundle:
            raise ModelNotLoadedError("No model bundle provided")
        self.model = bundle["model"]
        self.model_name = bundle["name"]
        self.txn_repo = txn_repo
        self.alert_service = alert_service

    def _predict(self, payload: dict) -> float:
        X = build_features(pd.DataFrame([payload]))
        return float(self.model.predict_proba(X)[:, 1][0])

    def _with_server_side_velocity(self, payload: dict) -> dict:
        """user_avg_amount / txn_count_1h are never taken from the
        client — they're computed here from the user's real history so
        they can't be spoofed to lower a risk score."""
        anchor = datetime.fromisoformat(payload["timestamp"])
        avg_amount, txn_count = self.txn_repo.get_velocity_features(payload["user_id"], anchor)
        return {**payload, "user_avg_amount": avg_amount, "txn_count_1h": txn_count}

    def score_and_persist(self, payload: dict) -> dict:
        # Same transaction_id can arrive twice (Kafka redelivery, a
        # client retry) — treat that as idempotent, not a rescore.
        existing = self.txn_repo.get_by_txn_id(payload["transaction_id"])
        if existing is not None:
            return self._to_response(existing)

        enriched = self._with_server_side_velocity(payload)
        prob = self._predict(enriched)
        is_fraud = prob >= settings.fraud_threshold
        row, created = self.txn_repo.save(enriched, prob, is_fraud, self.model_name)
        if is_fraud and created:
            self.alert_service.raise_alert(row.id, row.transaction_id, prob)
        return self._to_response(row)

    @staticmethod
    def _to_response(row) -> dict:
        return {"transaction_id": row.transaction_id,
                "fraud_probability": round(row.fraud_prob, 4),
                "is_fraud": row.is_fraud, "model": row.model_name}
