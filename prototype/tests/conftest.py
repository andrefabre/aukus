from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from disp_evidence.config import Policy, Settings


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "var", tenant_seed=2026, today_override="2026-11-24", policy=Policy())


@pytest.fixture()
def today() -> date:
    return date(2026, 11, 24)
