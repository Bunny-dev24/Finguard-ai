"""Dependency injection wiring — the glue between layers."""
from fastapi import Depends
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.ml.registry import ModelRegistry
from src.repositories.transaction_repository import TransactionRepository
from src.repositories.alert_repo import AlertRepository
from src.services.alert_service import AlertService
from src.services.scoring_service import ScoringService
from src.services.drift_service import DriftService


def get_txn_repo(db: Session = Depends(get_db)) -> TransactionRepository:
    return TransactionRepository(db)


def get_alert_repo(db: Session = Depends(get_db)) -> AlertRepository:
    return AlertRepository(db)


def get_alert_service(repo: AlertRepository = Depends(get_alert_repo)) -> AlertService:
    return AlertService(repo)


def get_scoring_service(
    txn_repo: TransactionRepository = Depends(get_txn_repo),
    alert_service: AlertService = Depends(get_alert_service),
) -> ScoringService:
    return ScoringService(ModelRegistry.get(), txn_repo, alert_service)


def get_drift_service() -> DriftService:
    return DriftService()