<div align="center">

# 🛡️ FinGuard AI

**Real-time transaction fraud detection — built like production, not a notebook.**

FastAPI · XGBoost / LightGBM · Kafka · SQLAlchemy · Evidently · Streamlit

[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/tests-14%20passing-brightgreen.svg)](#testing)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

</div>

---

## What this actually is

A fraud-scoring service that takes a transaction, computes real per-user
behavioral features **on the server** (not from client input), runs it
through a trained XGBoost/LightGBM model, persists the result, and raises
an alert if the risk is high enough. It can be driven synchronously over
HTTP or asynchronously off a Kafka topic — same scoring logic either way.

It's a personal project built to actually think through the problems a
fraud system runs into in practice, not just fit a model on a Kaggle CSV.

## Why it's not "just another fraud CSV notebook"

A lot of fraud-detection portfolio projects stop at `model.fit()`. The
interesting part of fraud detection is everything around the model:

- **Clients can't spoof their own risk score.** Early version of this
  took `user_avg_amount` / `txn_count_1h` straight from the request body —
  which means a fraudster could just claim a spotless history. Fixed by
  computing both server-side from the user's actual transaction history
  at scoring time (`get_velocity_features` in the repository layer).
- **Duplicate transactions don't crash anything.** Kafka delivers
  at-least-once, and clients retry. A repeated `transaction_id` is treated
  as idempotent — same response returned, no duplicate row, no double
  alert — instead of an uncaught `IntegrityError`.
- **A bad Kafka message doesn't take down the consumer.** Each record
  gets its own DB session and try/except; failures get routed to a DLQ
  topic (`fraud-detection-dlq`) instead of killing the whole loop.
- **Train/serve skew is structurally prevented.** `build_features()` is
  the single function both `train.py` and the live scoring path call —
  and the categorical vocabulary (`merchant_category`, `device_type`,
  `country`) lives in one place (`src/ml/features.py`) so synthetic data
  generation and serving can never drift apart.
- **Drift doesn't go unnoticed.** An Evidently-based drift check compares
  recent live traffic against the training reference set on demand
  (`POST /drift/check`), with a report visualized right in the dashboard.
- **Errors map to real HTTP semantics.** Model not loaded → `503`,
  unknown transaction → `404`, bad domain state → `400` — not a wall of
  raw `500`s.

## What it deliberately does *not* do

- **No auth on the API.** This is a demo/portfolio service meant to be
  scored against and inspected end-to-end — not a hardened public
  endpoint. Wiring in API keys/OAuth is a config change away, not a
  redesign.
- **No feature store.** Velocity features are computed from the last
  200 rows per user, aggregated in Python. Fine at this scale; a real
  feature store (Feast, Tecton) would be the next step if write volume
  got large.
- **Synthetic data.** Transactions are generated with realistic-ish
  burst/velocity fraud patterns (`data/generate_data.py`), not real
  financial data — this is a systems/engineering project, not a Kaggle
  leaderboard entry.

---

## Architecture

```
 ┌────────────┐  HTTP   ┌───────────────────────────────┐   ┌──────────┐
 │ Streamlit  │────────▶│           FastAPI API           │◀──│  curl /  │
 │ Dashboard  │         │  routes → services → repos      │   │  client  │
 └────────────┘         └───────────────┬─────────────────┘   └──────────┘
                                         │
                              ┌──────────┴──────────┐
                              ▼                     ▼
                       ┌─────────────┐       ┌─────────────┐
                       │ SQLite /    │       │ model.joblib│
                       │ Postgres    │       │ (XGB/LGBM)  │
                       └─────────────┘       └─────────────┘

 ┌────────────┐  topic:transactions   ┌───────────────┐  topic:fraud-alerts
 │   Kafka    │───────────────────────▶│ Kafka Consumer │─────────────▶ (alerts topic)
 │  Producer  │                        │ (same Scoring  │
 │ (synthetic)│                        │  Service the   │  bad message ──▶ DLQ topic
 └────────────┘                        │  API uses)     │
                                        └───────┬────────┘
                                                 ▼
                                          same DB as the API

 Model artifact (XGBoost/LightGBM) + drift reference set live in artifacts/,
 trained offline by src/ml/train.py.
```

**Layering inside the API:** `routes/` (HTTP only) → `services/` (business
rules: scoring, alerting, drift) → `repositories/` (all DB access) →
`models/` (SQLAlchemy ORM). Nothing above the repository layer touches SQL
directly.

## Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI + Pydantic v2 |
| ML | XGBoost & LightGBM (best-of-two picked by PR-AUC) |
| Streaming | Kafka (`kafka-python`), consumer + producer |
| Storage | SQLAlchemy 2.0 — SQLite for local dev, Postgres in Docker |
| Drift monitoring | Evidently (`DataDriftPreset`, `TargetDriftPreset`) |
| Dashboard | Streamlit + Plotly |
| Metrics | Prometheus client, mounted at `/metrics` |
| Migrations | Alembic |
| Tests | Pytest (unit + integration, 14 tests) |

## Project structure

```
Finguard_AI/
├── src/
│   ├── api/              # FastAPI app, routes, request/response schemas
│   ├── services/         # scoring, alerting, drift — business logic
│   ├── repositories/     # all DB access, no logic
│   ├── models/           # SQLAlchemy ORM
│   ├── ml/               # feature engineering + model registry
│   ├── streaming/        # Kafka producer & consumer
│   ├── core/             # settings, logging, domain exceptions
│   └── db/               # session + Alembic migrations
├── data/generate_data.py # synthetic transaction generator
├── frontend/app.py       # Streamlit dashboard
├── tests/                # pytest suite
├── artifacts/            # trained model, reference set, metrics
└── Docker-compose.yml    # api + consumer + kafka + postgres
```

---

## Getting started

### Option A — Docker Compose (full stack: Kafka + Postgres)

```bash
cp .env.example .env
docker compose -f Docker-compose.yml up --build
```

This brings up Postgres, Zookeeper, Kafka, the API, and the Kafka
consumer. API comes up on `http://localhost:8000`.

### Option B — Local dev (SQLite, no Kafka needed for the API)

```bash
conda create -n finguard python=3.11 pip -y
conda activate finguard
pip install -r requirements.txt

# train a model (generates synthetic data if none exists)
python src/ml/train.py

# run the API
python -m src.api.main
# → http://localhost:8000/health

# run the dashboard (separate terminal)
streamlit run frontend/app.py
```

To exercise the Kafka path locally you still need a running broker —
point `KAFKA_BOOTSTRAP_SERVERS` at it and run:

```bash
python -m src.streaming.producer   # feeds synthetic traffic
python -m src.streaming.consumer   # scores it, same service layer as the API
```

---

## API reference

| Method | Path | What it does |
|---|---|---|
| `POST` | `/score` | Score a transaction. Velocity features are computed server-side — client can't influence them. |
| `GET` | `/transactions` | Recent scored transactions (`limit`, `fraud_only` params). |
| `GET` | `/transactions/{transaction_id}` | Single transaction, `404` if unknown. |
| `GET` | `/alerts` | Open fraud alerts. |
| `POST` | `/alerts/{alert_id}/review` | Mark an alert reviewed. |
| `POST` | `/drift/check` | Compare recent traffic to the training reference set. |
| `GET` | `/health` | Liveness + whether the model is loaded. |
| `GET` | `/metrics` | Prometheus metrics. |

Example:

```bash
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "txn-001",
    "user_id": "user_42",
    "timestamp": "2026-01-01T10:00:00",
    "amount": 850.0,
    "merchant_category": "crypto",
    "device_type": "web",
    "country": "RU"
  }'
```

## Dashboard

Streamlit app with five pages: live overview, manual scoring, transaction
history, open alerts, and an on-demand drift check that renders the
Evidently HTML report inline.

## Testing

```bash
pytest tests/ -v
```

14 tests across unit (`test_services.py` — mocked repos, no DB/HTTP) and
integration (`test_api.py` — real `TestClient`, real SQLite) layers,
plus isolated Kafka consumer tests (`test_consumer.py`) that don't
require a running broker.

## Model

Trained on synthetic data with injected velocity-burst fraud patterns
(card-testing / account-takeover style). XGBoost and LightGBM are both
trained; the one with the higher PR-AUC on a held-out split wins.

| Metric | Value |
|---|---|
| Best model | LightGBM |
| PR-AUC | 0.233 |
| Fraud prevalence | ~7.6% |

PR-AUC, not accuracy or ROC-AUC alone, is the metric that matters here —
the classes are imbalanced and false negatives (missed fraud) are far
more expensive than false positives. 0.233 isn't a leaderboard number;
it's an honest result on synthetic data with no real behavioral signal
to exploit — the point of this project is the system around the model,
not squeezing out the last percentage point on invented data.

## Known limitations

- No authentication on the API (see above — intentional for this stage).
- Velocity features cap at the last 200 transactions per user; no proper
  feature store.
- Single-broker Kafka setup in Compose — no partitioning/replication
  story, fine for a demo, not for production throughput.
- Synthetic data — real fraud has correlations no synthetic generator
  fully captures.

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, ship it.

