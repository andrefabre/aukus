"""Stream 6 - Visitor register completeness."""

from __future__ import annotations

from datetime import datetime, timezone

from ..config import Policy
from ..connectors.base import Connector
from ..models import StreamResult
from ..simulator import month_bounds
from .common import ExceptionBuilder, pct, status_from

STREAM = "visitors"


def collect(conn: Connector, period: str, as_of: datetime, policy: Policy) -> StreamResult:
    start, end = month_bounds(period)
    rows = conn.visitor_log(start, min(end, as_of))
    ex = ExceptionBuilder(STREAM, period)
    records = []
    for v in rows:
        issues = []
        if not v.get("signOut"):
            issues.append("no sign-out")
            ex.add("DISP-PHYSICAL-VISITORS", "low", "Visitor not signed out", v["entryId"], f"{v['visitorName']} ({v['company']}), {v['signIn'][:10]}")
        if not v.get("idChecked"):
            issues.append("ID not checked")
            ex.add("DISP-PHYSICAL-VISITORS", "medium", "Visitor ID not verified", v["entryId"], f"{v['visitorName']} ({v['company']}), {v['area']}")
        if v.get("restrictedArea") and v.get("escorted") is False:
            issues.append("restricted area unescorted")
            ex.add("DISP-PHYSICAL-VISITORS", "high", "Unescorted visitor in restricted area", v["entryId"],
                   f"{v['visitorName']} ({v['company']}) in {v['area']} on {v['signIn'][:10]}, host {v['host']}")
        records.append({"entry": v["entryId"], "date": v["signIn"][:10], "visitor": v["visitorName"], "company": v["company"],
                        "host": v["host"], "area": v["area"], "signed_out": bool(v.get("signOut")),
                        "id_checked": v.get("idChecked"), "escorted": v.get("escorted"), "issues": "; ".join(issues)})
    complete = sum(1 for r in records if not r["issues"])
    restricted = sum(1 for v in rows if v.get("restrictedArea"))
    return StreamResult(
        stream=STREAM, period=period, as_of=as_of, collected_at=datetime.now(timezone.utc),
        control_ids=["DISP-PHYSICAL-VISITORS"], sources=["SharePoint list: Visitor Register (Microsoft Forms)"],
        status=status_from(ex.items),
        headline=f"{len(rows)} visits ({restricted} to restricted areas); {pct(complete, len(rows))}% of entries complete",
        metrics={"visits": len(rows), "restricted_area_visits": restricted, "complete_entries_pct": pct(complete, len(rows)),
                 "missing_sign_out": sum(1 for r in records if not r["signed_out"]),
                 "id_not_checked": sum(1 for r in records if not r["id_checked"]),
                 "unescorted_restricted": sum(1 for r in records if r["escorted"] is False)},
        records=records, raw={"visitorRegister": rows}, exceptions=ex.items,
    )
