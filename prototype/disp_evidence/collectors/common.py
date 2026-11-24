from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from ..models import EvidenceException, StreamStatus

UTC = timezone.utc


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    d = datetime.fromisoformat(value)
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def days_between(earlier: datetime | None, later: datetime) -> float | None:
    if earlier is None:
        return None
    return round((later - earlier).total_seconds() / 86400, 1)


def status_from(exceptions: Iterable[EvidenceException]) -> StreamStatus:
    sev = {e.severity for e in exceptions}
    if sev & {"critical", "high"}:
        return "FAIL"
    if "medium" in sev:
        return "WARN"
    return "PASS"


def pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 1) if d else 100.0


class ExceptionBuilder:
    """Builds stable exception ids: <stream>-<period>-<nnn>."""

    def __init__(self, stream: str, period: str):
        self.stream, self.period, self.items = stream, period, []  # type: ignore[var-annotated]

    def add(self, control_id: str, severity: str, title: str, subject: str = "", detail: str = "") -> None:
        n = len(self.items) + 1
        self.items.append(EvidenceException(exception_id=f"{self.stream}-{self.period}-{n:03d}", stream=self.stream,
                                            control_id=control_id, severity=severity, title=title,  # type: ignore[arg-type]
                                            subject=subject, detail=detail))
