import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from src.db.session import init_db
from src.ml.registry import ModelRegistry
from src.core.logging import logger
from src.core.exceptions import FinGuardError, ModelNotLoadedError, TransactionNotFoundError
from src.api.routes import scoring, transaction, alerts, health, drift

app = FastAPI(title="FinGuard-AI", version="2.0.0",
              description="Layered real-time fraud detection API")
app.mount("/metrics", make_asgi_app())

app.include_router(health.router)
app.include_router(scoring.router)
app.include_router(transaction.router)
app.include_router(alerts.router)
app.include_router(drift.router)


# Maps our domain exceptions to proper HTTP responses instead of
# letting them fall through to a generic 500.

@app.exception_handler(ModelNotLoadedError)
async def model_not_loaded_handler(request: Request, exc: ModelNotLoadedError):
    return JSONResponse(status_code=503,
                        content={"detail": str(exc) or "Model not loaded yet — try again shortly."})


@app.exception_handler(TransactionNotFoundError)
async def transaction_not_found_handler(request: Request, exc: TransactionNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc) or "Transaction not found."})


@app.exception_handler(FinGuardError)
async def finguard_error_handler(request: Request, exc: FinGuardError):
    logger.error(f"Unhandled domain error ({type(exc).__name__}): {exc}")
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.on_event("startup")
def startup():
    init_db()
    try:
        ModelRegistry.load()
        logger.info("Model loaded on startup")
    except Exception as e:
        logger.warning(f"Model not loaded yet: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)