"""Stream 7 input - security incident register (feeds the ASR data pack)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from ..config import Policy
from ..connectors.base import Connector
from ..models import StreamResult
from ..simulator import month_bounds
from .common import ExceptionBuilder, status_from

STREAM = "incidents"
REPORT_WITHIN_DAYS = 1


def collect(conn: Connector, period: str, as_of: datetime, policy: Policy) -> StreamResult:
    start, end = month_bounds(period)
    rows = conn.incident_register(start, min(end, as_of))
    ex = ExceptionBuilder(STREAM, period)
    records = []
    for i in rows:
        lag = None
        if i.get("reportable_to_defence"):
            if i.get("reported_on"):
                lag = (date.fromisoformat(i["reported_on"]) - date.fromisoformat(i["date"])).days
                if lag > REPORT_WITHIN_DAYS:
                    ex.add("DISP-INCIDENT-REPORTING", "medium", "Reportable incident reported late", i["id"], f"Reported after {lag} days.")
            else:
                ex.add("DISP-INCIDENT-REPORTING", "high", "Reportable incident not reported to Defence", i["id"], i["category"])
        records.append({"id": i["id"], "date": i["date"], "category": i["category"], "summary": i["summary"],
                        "reportable": i.get("reportable_to_defence", False), "reported_on": i.get("reported_on", ""),
                        "days_to_report": lag if lag is not None else ""})
    reportable = sum(1 for i in rows if i.get("reportable_to_defence"))
    return StreamResult(
        stream=STREAM, period=period, as_of=as_of, collected_at=datetime.now(timezone.utc),
        control_ids=["DISP-INCIDENT-REPORTING"], sources=["SharePoint list: Incident Register"],
        status=status_from(ex.items),
        headline=f"{len(rows)} incident(s) logged, {reportable} reportable to Defence",
        metrics={"incidents": len(rows), "reportable": reportable,
                 "reported_on_time": sum(1 for r in records if r["days_to_report"] != "" and r["days_to_report"] <= REPORT_WITHIN_DAYS)},
        records=records, raw={"incidentRegister": rows}, exceptions=ex.items,
    )
