"""Pure unit tests — mock repos, no DB/HTTP. Shows testability of layering."""
from datetime import datetime
from unittest.mock import MagicMock
import numpy as np
from src.services.scoring_service import ScoringService
from src.services.alert_service import AlertService


def _fake_bundle(prob):
    model = MagicMock()
    model.predict_proba.return_value = np.array([[1 - prob, prob]])
    return {"model": model, "name": "xgboost"}


def _fresh_repo(saved_row) -> MagicMock:
    """Repo mock for a transaction_id that doesn't exist yet."""
    repo = MagicMock()
    repo.get_by_txn_id.return_value = None
    repo.save.return_value = (saved_row, True)
    return repo


def _txn_payload(**overrides) -> dict:
    base = {"transaction_id": "t1", "user_id": "u1",
            "timestamp": "2024-01-01T10:00:00", "amount": 500,
            "merchant_category": "crypto", "device_type": "web", "country": "RU"}
    base.update(overrides)
    return base


def test_fraud_triggers_alert():
    txn_repo = _fresh_repo(MagicMock(id=1, transaction_id="t1", fraud_prob=0.95,
                                      is_fraud=True, model_name="xgboost"))
    txn_repo.get_velocity_features.return_value = (40.0, 9)
    alert_service = MagicMock(spec=AlertService)
    svc = ScoringService(_fake_bundle(0.95), txn_repo, alert_service)

    out = svc.score_and_persist(_txn_payload())

    assert out["is_fraud"] is True
    alert_service.raise_alert.assert_called_once()
    txn_repo.get_velocity_features.assert_called_once_with("u1", datetime(2024, 1, 1, 10, 0))


def test_legit_no_alert():
    txn_repo = _fresh_repo(MagicMock(id=2, transaction_id="t2", fraud_prob=0.05,
                                      is_fraud=False, model_name="xgboost"))
    txn_repo.get_velocity_features.return_value = (25.0, 1)
    alert_service = MagicMock(spec=AlertService)
    svc = ScoringService(_fake_bundle(0.05), txn_repo, alert_service)

    out = svc.score_and_persist(_txn_payload(transaction_id="t2", user_id="u2",
        amount=20, merchant_category="grocery", device_type="ios", country="IN"))

    assert out["is_fraud"] is False
    alert_service.raise_alert.assert_not_called()


def test_client_cannot_spoof_velocity():
    txn_repo = _fresh_repo(MagicMock(id=3, transaction_id="t3", fraud_prob=0.95,
                                      is_fraud=True, model_name="xgboost"))
    txn_repo.get_velocity_features.return_value = (500.0, 12)
    alert_service = MagicMock(spec=AlertService)
    svc = ScoringService(_fake_bundle(0.95), txn_repo, alert_service)

    svc.score_and_persist(_txn_payload(transaction_id="t3", user_id="u3",
        amount=20, merchant_category="grocery", device_type="ios", country="IN",
        user_avg_amount=0.0, txn_count_1h=0))

    saved_payload = txn_repo.save.call_args[0][0]
    assert saved_payload["user_avg_amount"] == 500.0
    assert saved_payload["txn_count_1h"] == 12


def test_duplicate_transaction_is_idempotent():
    existing = MagicMock(id=99, transaction_id="dupe-1", fraud_prob=0.91,
                         is_fraud=True, model_name="lightgbm")
    txn_repo = MagicMock()
    txn_repo.get_by_txn_id.return_value = existing
    alert_service = MagicMock(spec=AlertService)
    svc = ScoringService(_fake_bundle(0.5), txn_repo, alert_service)

    out = svc.score_and_persist(_txn_payload(transaction_id="dupe-1", user_id="u9", amount=999))

    assert out == {"transaction_id": "dupe-1", "fraud_probability": 0.91,
                    "is_fraud": True, "model": "lightgbm"}
    txn_repo.save.assert_not_called()
    txn_repo.get_velocity_features.assert_not_called()
    alert_service.raise_alert.assert_not_called()


def test_race_condition_insert_does_not_double_alert():
    row = MagicMock(id=5, transaction_id="race-1", fraud_prob=0.9,
                    is_fraud=True, model_name="xgboost")
    txn_repo = MagicMock()
    txn_repo.get_by_txn_id.return_value = None
    txn_repo.get_velocity_features.return_value = (0.0, 0)
    txn_repo.save.return_value = (row, False)
    alert_service = MagicMock(spec=AlertService)
    svc = ScoringService(_fake_bundle(0.9), txn_repo, alert_service)

    svc.score_and_persist(_txn_payload(transaction_id="race-1", user_id="u5", amount=500))

    alert_service.raise_alert.assert_not_called()
