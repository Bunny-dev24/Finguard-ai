"""Encapsulates alert severity rules & persistence."""
from src.repositories.alert_repo import AlertRepository
from src.core.config import settings


class AlertService:
    def __init__(self, alert_repo: AlertRepository):
        self.alert_repo = alert_repo

    def _severity(self, prob: float) -> str:
        return "HIGH" if prob >= settings.high_risk_threshold else "MEDIUM"

    def raise_alert(self, transaction_pk: int, transaction_id: str, prob: float):
        return self.alert_repo.create(transaction_pk, transaction_id,
                                      self._severity(prob), prob)

    def list_open(self, limit: int = 50):
        return self.alert_repo.list_open(limit)

    def review(self, alert_id: int):
        self.alert_repo.mark_reviewed(alert_id)