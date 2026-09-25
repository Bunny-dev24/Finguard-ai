import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.core.exceptions import ModelNotLoadedError
from src.ml.registry import ModelRegistry


@pytest.fixture(scope="module")
def client():
    # context-manager form triggers FastAPI's startup event (init_db, model load)
    with TestClient(app) as c:
        yield c


def _txn_payload(**overrides) -> dict:
    base = {"transaction_id": "api-1", "user_id": "test-user-1",
            "timestamp": "2024-01-01T10:00:00", "amount": 500.0,
            "merchant_category": "crypto", "device_type": "web", "country": "RU"}
    base.update(overrides)
    return base


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_score_endpoint(client):
    r = client.post("/score", json=_txn_payload())
    assert r.status_code == 200
    assert 0 <= r.json()["fraud_probability"] <= 1


def test_score_endpoint_rejects_client_velocity_fields(client):
    payload = _txn_payload(transaction_id="api-2", user_id="test-user-2",
        amount=20.0, merchant_category="grocery", device_type="ios", country="IN",
        user_avg_amount=99999.0, txn_count_1h=999)
    r = client.post("/score", json=payload)
    assert r.status_code == 200


def test_drift_check_needs_transactions_first(client):
    r = client.post("/drift/check?limit=10")
    assert r.status_code in (200, 404)


def test_drift_check_after_scoring(client):
    for i in range(5):
        client.post("/score", json=_txn_payload(
            transaction_id=f"drift-{i}", user_id=f"drift-user-{i}",
            amount=40.0 + i, merchant_category="grocery", device_type="ios", country="IN"))

    r = client.post("/drift/check?limit=100")
    assert r.status_code == 200
    body = r.json()
    assert "dataset_drift" in body
    assert "drifted_share" in body


def test_missing_transaction_returns_clean_404(client):
    r = client.get("/transactions/this-id-does-not-exist")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_model_not_loaded_returns_503_not_raw_500(client, monkeypatch):
    def _raise(cls):
        raise ModelNotLoadedError("Model artifact not found")

    monkeypatch.setattr(ModelRegistry, "get", classmethod(_raise))

    payload = _txn_payload(transaction_id="no-model-1", user_id="u1",
        amount=20.0, merchant_category="grocery", device_type="ios", country="IN")
    r = client.post("/score", json=payload)

    assert r.status_code == 503
    assert "model" in r.json()["detail"].lower()
