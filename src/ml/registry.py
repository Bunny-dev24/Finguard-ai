"""Thin model registry — abstracts artifact load so services stay ML-agnostic."""
import joblib
from src.core.config import settings
from src.core.exceptions import ModelNotLoadedError


class ModelRegistry:
    _bundle: dict | None = None

    @classmethod
    def load(cls) -> None:
        cls._bundle = joblib.load(settings.model_path)

    @classmethod
    def get(cls) -> dict:
        if cls._bundle is None:
            try:
                cls.load()
            except FileNotFoundError as e:
                raise ModelNotLoadedError("Model artifact not found") from e
        return cls._bundle

    @classmethod
    def is_loaded(cls) -> bool:
        return cls._bundle is not None