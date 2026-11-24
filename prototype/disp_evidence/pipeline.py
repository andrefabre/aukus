"""Monthly cycle orchestration: collect every stream -> seal into the vault."""

from __future__ import annotations

from datetime import datetime, time, timezone

from .collectors import COLLECTORS
from .config import Settings
from .connectors import get_connector
from .simulator import month_bounds
from .vault import Vault


def now_utc(settings: Settings) -> datetime:
    if settings.today_override:
        return datetime.combine(settings.today(), time(12, 0), timezone.utc)
    return datetime.now(timezone.utc)


def cutoff_for(settings: Settings, period: str) -> datetime:
    """End of the period, or 'now' for the current (open) month."""
    _, end = month_bounds(period)
    return min(end, now_utc(settings))


def current_period(settings: Settings) -> str:
    return f"{settings.today():%Y-%m}"


def run_cycle(settings: Settings, period: str, vault: Vault | None = None) -> dict:
    vault = vault or Vault(settings)
    start, _ = month_bounds(period)
    as_of = cutoff_for(settings, period)
    if as_of <= start:
        raise ValueError(f"{period} has not started yet")
    conn = get_connector(settings.tenant_seed)
    results = [fn(conn, period, as_of, settings.policy) for fn in COLLECTORS.values()]
    return vault.seal(period, results, as_of)


def periods_between(first: str, last: str) -> list[str]:
    y, m = (int(x) for x in first.split("-"))
    out = []
    while f"{y:04d}-{m:02d}" <= last:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def backfill(settings: Settings, first: str, last: str) -> list[str]:
    vault = Vault(settings)
    done = []
    for p in periods_between(first, last):
        if not vault.is_sealed(p):
            run_cycle(settings, p, vault)
            done.append(p)
    return done
