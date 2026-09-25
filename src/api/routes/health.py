from fastapi import APIRouter
from src.ml.registry import ModelRegistry

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    loaded = ModelRegistry.is_loaded()
    return {"status": "ok", "model_loaded": loaded,
            "model": ModelRegistry.get().get("name") if loaded else None}