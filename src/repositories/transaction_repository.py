from datetime import datetime, timedelta
from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from src.models.transaction import TransactionORM

HISTORY_LIMIT = 200


class TransactionRepository:
    """Encapsulates all DB access for transactions — no business logic here."""

    def __init__(self, db: Session):
        self.db = db

    def get_velocity_features(self, user_id: str, before: datetime,
                              window_hours: float = 1.0) -> tuple[float, int]:
        """Average spend and recent transaction count for a user,
        computed from their own history strictly before `before`.

        Pulls the last HISTORY_LIMIT rows and aggregates in Python
        rather than pushing the time filter into SQL — good enough at
        this scale. Worth revisiting with a proper feature store if
        write volume gets large.
        """
        stmt = (
            select(TransactionORM)
            .where(TransactionORM.user_id == user_id)
            .order_by(TransactionORM.id.desc())
            .limit(HISTORY_LIMIT)
        )
        rows = [r for r in self.db.scalars(stmt).all()
                if datetime.fromisoformat(r.timestamp) < before]
        if not rows:
            return 0.0, 0

        avg_amount = sum(r.amount for r in rows) / len(rows)
        window_start = before - timedelta(hours=window_hours)
        txn_count = sum(1 for r in rows if datetime.fromisoformat(r.timestamp) >= window_start)
        return float(avg_amount), int(txn_count)

    def save(self, data: dict, prob: float, is_fraud: bool, model_name: str
             ) -> tuple[TransactionORM, bool]:
        """Inserts a scored transaction. Returns (row, created) —
        created=False means transaction_id already existed (a retry or
        redelivered Kafka message raced us to the insert); we return
        the existing row instead of erroring out."""
        row = TransactionORM(**data, fraud_prob=prob, is_fraud=is_fraud, model_name=model_name)
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self.get_by_txn_id(data["transaction_id"])
            if existing is not None:
                return existing, False
            raise
        self.db.refresh(row)
        return row, True

    def get_by_txn_id(self, transaction_id: str) -> Optional[TransactionORM]:
        stmt = select(TransactionORM).where(TransactionORM.transaction_id == transaction_id)
        return self.db.scalar(stmt)

    def list_recent(self, limit: int = 50, fraud_only: bool = False) -> Sequence[TransactionORM]:
        stmt = select(TransactionORM).order_by(TransactionORM.created_at.desc())
        if fraud_only:
            stmt = stmt.where(TransactionORM.is_fraud.is_(True))
        return self.db.scalars(stmt.limit(limit)).all()
