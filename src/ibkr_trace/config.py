from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
SOURCE_DIR = DATA_DIR / "sources"
DERIVED_DIR = DATA_DIR / "derived"
DEFAULT_DB_PATH = DERIVED_DIR / "db" / "ibkr.sqlite"
DEFAULT_REPORTS_DIR = DERIVED_DIR / "reports"


def ensure_runtime_dirs() -> None:
    (SOURCE_DIR / "ibkr" / "activity").mkdir(parents=True, exist_ok=True)
    (SOURCE_DIR / "fx").mkdir(parents=True, exist_ok=True)
    (DERIVED_DIR / "db").mkdir(parents=True, exist_ok=True)
    DEFAULT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
