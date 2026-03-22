from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine

from ibkr_trace.config import DEFAULT_DB_PATH, ensure_runtime_dirs
from ibkr_trace.schema import metadata


def resolve_db_path(path: str | None = None) -> Path:
    return Path(path) if path else DEFAULT_DB_PATH


def get_engine(path: str | None = None) -> Engine:
    db_path = resolve_db_path(path)
    ensure_runtime_dirs()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", future=True)


def ensure_database(engine: Engine) -> None:
    metadata.create_all(engine)
