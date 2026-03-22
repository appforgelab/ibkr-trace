from __future__ import annotations

from pathlib import Path

import pytest

from ibkr_trace.db import get_engine


@pytest.fixture()
def fixture_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures"


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "ibkr_test.sqlite"


@pytest.fixture()
def engine(db_path: Path):
    return get_engine(str(db_path))
