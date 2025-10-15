# services/shared/db.py
from __future__ import annotations
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings, SettingsConfigDict

class DBSettings(BaseSettings):
    PGHOST: str = "localhost"
    PGPORT: int = 5432
    PGUSER: str = "postgres"
    PGPASSWORD: str = "postgres"
    PGDATABASE: str = "culinary"
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
