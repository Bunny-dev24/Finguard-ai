from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    database_url: str = "sqlite:///./finguard.db"
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic: str = "transactions"
    kafka_alerts_topic: str = "fraud-alerts"
    kafka_dlq_topic: str = "fraud-detection-dlq"
    model_path: str = "artifacts/model.joblib"
    reference_data_path: str = "artifacts/reference.parquet"
    fraud_threshold: float = 0.5
    high_risk_threshold: float = 0.85

    @model_validator(mode="after")
    def _resolve_paths(self) -> "Settings":
        self.model_path = str(resolve_path(self.model_path))
        self.reference_data_path = str(resolve_path(self.reference_data_path))
        if self.database_url.startswith("sqlite:///./"):
            db_file = self.database_url.removeprefix("sqlite:///./")
            self.database_url = f"sqlite:///{resolve_path(db_file)}"
        return self


settings = Settings()