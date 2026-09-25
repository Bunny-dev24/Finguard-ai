from typing import Sequence
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.models.alert import AlertORM


class AlertRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, transaction_pk: int, transaction_id: str,
               severity: str, prob: float) -> AlertORM:
        alert = AlertORM(transaction_pk=transaction_pk, transaction_id=transaction_id,
                         severity=severity, fraud_prob=prob)
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def list_open(self, limit: int = 50) -> Sequence[AlertORM]:
        stmt = (select(AlertORM).where(AlertORM.status == "OPEN")
                .order_by(AlertORM.created_at.desc()).limit(limit))
        return self.db.scalars(stmt).all()

    def mark_reviewed(self, alert_id: int) -> None:
        alert = self.db.get(AlertORM, alert_id)
        if alert:
            alert.status = "REVIEWED"
            self.db.commit()