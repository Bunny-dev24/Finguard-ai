"""On-demand drift check — call this manually or from a cron job."""
from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_drift_service, get_txn_repo
from src.repositories.transaction_repository import TransactionRepository
from src.services.drift_service import DriftService

router = APIRouter(prefix="/drift", tags=["drift"])


@router.post("/check")
def check_drift(limit: int = 5000,
                txn_repo: TransactionRepository = Depends(get_txn_repo),
                drift_service: DriftService = Depends(get_drift_service)):
    current_path = drift_service.export_recent_to_parquet(txn_repo, limit=limit)
    if current_path is None:
        raise HTTPException(404, "No transactions yet — score some first, "
                                  "then run drift check.")
    try:
        return drift_service.run(current_path)
    except FileNotFoundError:
        raise HTTPException(400, "No reference dataset found — train a "
                                  "model first (src/ml/train.py).")
