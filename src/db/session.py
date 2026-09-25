from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.core.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Session:
    """FastAPI dependency — yields a scoped session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from src.models.base import Base
    import src.models.transaction, src.models.alert  # noqa: register metadata
    Base.metadata.create_all(bind=engine)