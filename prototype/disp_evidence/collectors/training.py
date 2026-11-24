"""Stream 5 - Security awareness training completion."""

from __future__ import annotations

from datetime import date, datetime, timezone

from ..config import Policy
from ..connectors.base import Connector
from ..models import StreamResult
from .common import ExceptionBuilder, pct

STREAM = "training"


def collect(conn: Connector, period: str, as_of: datetime, policy: Policy) -> StreamResult:
    rows = conn.training_records(as_of)
    today = as_of.date()
    ex = ExceptionBuilder(STREAM, period)
    records = []
    current = 0
    for r in rows:
        started = date.fromisoformat(r["startDate"])
        last = date.fromisoformat(r["lastCompleted"]) if r.get("lastCompleted") else None
        tenure = (today - started).days
        status = "current"
        if last and (today - last).days <= policy.training_validity_days:
            current += 1
        elif tenure <= policy.new_starter_training_days:
            status = "new starter - within grace period"
            current += 1
        else:
            if last:
                status = f"expired {(today - last).days - policy.training_validity_days} days ago"
                ex.add("DISP-TRAINING", "medium", "Annual security training overdue", r["upn"], f"Last completed {last}.")
            else:
                status = f"new starter not trained after {tenure} days"
                ex.add("DISP-TRAINING", "medium", "New starter has not completed training", r["upn"], f"Started {started}.")
        records.append({"upn": r["upn"], "name": r["name"], "course": r["course"], "last_completed": r.get("lastCompleted") or "",
                        "status": status})

    coverage = pct(current, len(rows))
    status = "FAIL" if coverage < 85 else ("WARN" if ex.items else "PASS")
    return StreamResult(
        stream=STREAM, period=period, as_of=as_of, collected_at=datetime.now(timezone.utc),
        control_ids=["DISP-TRAINING"], sources=["Attack Simulation Training / LMS CSV export"],
        status=status,  # type: ignore[arg-type]
        headline=f"{coverage}% of {len(rows)} staff current on annual security awareness training",
        metrics={"staff": len(rows), "current": current, "coverage_pct": coverage, "overdue": len(ex.items)},
        records=records, raw={"trainingRecords": rows}, exceptions=ex.items,
    )
