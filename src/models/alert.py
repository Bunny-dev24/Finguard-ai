from datetime import datetime
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base


class AlertORM(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_pk: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True)
    transaction_id: Mapped[str] = mapped_column(String, index=True)
    severity: Mapped[str] = mapped_column(String, index=True)   # HIGH / MEDIUM
    fraud_prob: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="OPEN") # OPEN/REVIEWED
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    transaction = relationship("TransactionORM", back_populates="alerts")