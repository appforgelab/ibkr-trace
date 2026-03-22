from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
IBKR_ACTIVITY_DIR = DATA_DIR / "ibkr" / "activity"
FX_DIR = DATA_DIR / "fx"
DB_DIR = DATA_DIR / "db"
DEFAULT_DB_PATH = DB_DIR / "ibkr.sqlite"
DEFAULT_REPORTS_DIR = DATA_DIR / "reports"


def ensure_runtime_dirs() -> None:
    IBKR_ACTIVITY_DIR.mkdir(parents=True, exist_ok=True)
    FX_DIR.mkdir(parents=True, exist_ok=True)
    DB_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
