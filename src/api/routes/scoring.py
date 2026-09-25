from fastapi import APIRouter, Depends
from prometheus_client import Counter, Histogram
from src.api.schemas.scoring import TransactionIn, ScoreResponse
from src.api.dependencies import get_scoring_service
from src.services.scoring_service import ScoringService

router = APIRouter(prefix="/score", tags=["scoring"])
PRED_COUNT = Counter("fraud_predictions_total", "Predictions", ["outcome"])
LATENCY = Histogram("scoring_latency_seconds", "Scoring latency")


@router.post("", response_model=ScoreResponse)
@LATENCY.time()
def score(txn: TransactionIn, svc: ScoringService = Depends(get_scoring_service)):
    result = svc.score_and_persist(txn.model_dump())
    PRED_COUNT.labels(outcome="fraud" if result["is_fraud"] else "legit").inc()
    return result