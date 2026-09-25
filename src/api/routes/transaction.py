from fastapi import APIRouter, Depends
from src.api.dependencies import get_txn_repo
from src.core.exceptions import TransactionNotFoundError
from src.repositories.transaction_repository import TransactionRepository

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("")
def list_transactions(limit: int = 50, fraud_only: bool = False,
                      repo: TransactionRepository = Depends(get_txn_repo)):
    return repo.list_recent(limit, fraud_only)


@router.get("/{transaction_id}")
def get_transaction(transaction_id: str,
                    repo: TransactionRepository = Depends(get_txn_repo)):
    row = repo.get_by_txn_id(transaction_id)
    if not row:
        raise TransactionNotFoundError(f"Transaction '{transaction_id}' not found")
    return row