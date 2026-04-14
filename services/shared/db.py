# services/shared/db.py
from __future__ import annotations
import time as _time
import logging as _logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings, SettingsConfigDict

_retry_log = _logging.getLogger(__name__)

class DBSettings(BaseSettings):
    PGHOST: str = "localhost"
    PGPORT: int = 5432
    PGUSER: str = "postgres"
    PGPASSWORD: str = "postgres"
    PGDATABASE: str = "culinary"
    ANTHROPIC_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

_cfg = DBSettings()

PG_URL = f"postgresql+psycopg2://{_cfg.PGUSER}:{_cfg.PGPASSWORD}@{_cfg.PGHOST}:{_cfg.PGPORT}/{_cfg.PGDATABASE}"

# --- engine + sessionmaker (this is what you asked about)
engine = create_engine(PG_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, autocommit=False)

def ping_db() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def with_retry(fn, retries: int = 3, delay: float = 0.1):
    """Call fn() up to `retries` times with exponential backoff on OperationalError."""
    from sqlalchemy.exc import OperationalError
    last_exc = None
    for attempt in range(retries):
        try:
            return fn()
        except OperationalError as exc:
            last_exc = exc
            wait = delay * (2 ** attempt)
            _retry_log.warning(
                "DB retry %d/%d after OperationalError: %s (sleeping %.2fs)",
                attempt + 1, retries, exc, wait,
            )
            _time.sleep(wait)
    raise last_exc
