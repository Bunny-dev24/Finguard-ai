from pydantic import BaseModel, Field


class TransactionIn(BaseModel):
    # No user_avg_amount / txn_count_1h here — those are computed
    # server-side from history, see ScoringService.
    transaction_id: str
    user_id: str
    timestamp: str
    amount: float = Field(gt=0)
    merchant_category: str
    device_type: str
    country: str


class ScoreResponse(BaseModel):
    transaction_id: str
    fraud_probability: float
    is_fraud: bool
    model: str


class TransactionOut(ScoreResponse):
    user_id: str
    amount: float
    merchant_category: str
    country: str


class AlertOut(BaseModel):
    id: int
    transaction_id: str
    severity: str
    fraud_prob: float
    status: str