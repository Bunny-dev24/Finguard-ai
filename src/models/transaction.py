from datetime import datetime
from sqlalchemy import String, Float, Boolean, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base


class TransactionORM(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    timestamp: Mapped[str] = mapped_column(String)
    amount: Mapped[float] = mapped_column(Float)
    merchant_category: Mapped[str] = mapped_column(String, index=True)
    device_type: Mapped[str] = mapped_column(String)
    country: Mapped[str] = mapped_column(String, index=True)
    user_avg_amount: Mapped[float] = mapped_column(Float, default=0.0)
    txn_count_1h: Mapped[int] = mapped_column(Integer, default=0)

    fraud_prob: Mapped[float] = mapped_column(Float, index=True)
    is_fraud: Mapped[bool] = mapped_column(Boolean, index=True)
    model_name: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    alerts = relationship("AlertORM", back_populates="transaction",
                          cascade="all, delete-orphan")