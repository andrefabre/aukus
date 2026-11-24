"""Stream 3 - Joiner / mover / leaver reconciliation (Entra audit vs HR register)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from ..config import Policy
from ..connectors.base import Connector
from ..models import StreamResult
from ..simulator import month_bounds
from .common import ExceptionBuilder, parse_dt, status_from

STREAM = "jml"
RESTRICTED_GROUP = "SG-Defence-Projects"
RESTRICTED_DEPTS = {"Engineering"}


def _end_of_day(d: str) -> datetime:
    """Leaver's last day is treated as ending 17:00 (UTC in the prototype)."""
    return datetime.combine(date.fromisoformat(d), datetime.min.time(), timezone.utc) + timedelta(hours=17)


def collect(conn: Connector, period: str, as_of: datetime, policy: Policy) -> StreamResult:
    start, end = month_bounds(period)
    hr = conn.hr_records(as_of)
    users = conn.users(as_of)
    by_upn = {u["userPrincipalName"]: u for u in users}
    audits = conn.directory_audits(start - timedelta(days=45), min(end, as_of) + timedelta(seconds=1))
    groups = {g["displayName"]: g for g in conn.privileged_groups(as_of)}
    ex = ExceptionBuilder(STREAM, period)
    records: list[dict] = []
    window = timedelta(hours=policy.leaver_removal_hours)

    disables = {}
    for a in audits:
        if a["activityDisplayName"] == "Disable account":
            disables.setdefault(a["targetUserPrincipalName"], parse_dt(a["activityDateTime"]))

    leavers_in_period = late = 0
    for h in hr:
        if not h.get("endDate"):
            continue
        last_day = _end_of_day(h["endDate"])
        if last_day > as_of:
            continue
        u = by_upn.get(h["upn"])
        still_enabled = bool(u and u.get("accountEnabled"))
        in_period = start <= last_day < end
        disabled_at = disables.get(h["upn"])
        if in_period:
            leavers_in_period += 1
        if still_enabled:
            overdue = as_of - last_day
            if overdue > window:
                ex.add("DISP-PERSONNEL-JML", "critical", "Leaver account still enabled", h["upn"],
                       f"{h['name']} left {h['endDate']}; account still enabled {overdue.days} days later.")
                records.append({"event": "leaver", "upn": h["upn"], "name": h["name"], "hr_date": h["endDate"],
                                "entra_action": "", "hours_to_action": "", "result": "NOT REMOVED"})
            continue
        if not in_period:
            continue
        hours = (disabled_at - last_day).total_seconds() / 3600 if disabled_at else None
        result = "on time"
        if hours is not None and hours > policy.leaver_removal_hours:
            late += 1
            result = "LATE"
            ex.add("DISP-PERSONNEL-JML", "high" if hours > 72 else "medium", "Leaver access removed late", h["upn"],
                   f"{h['name']} left {h['endDate']}; disabled {disabled_at:%Y-%m-%d %H:%M} ({hours:.0f} h vs {policy.leaver_removal_hours} h target).")
        records.append({"event": "leaver", "upn": h["upn"], "name": h["name"], "hr_date": h["endDate"],
                        "entra_action": disabled_at.isoformat() if disabled_at else "", "hours_to_action": round(hours, 1) if hours is not None else "",
                        "result": result})

    joiners = 0
    for h in hr:
        sd = h["startDate"]
        if start.date().isoformat() <= sd < end.date().isoformat():
            joiners += 1
            u = by_upn.get(h["upn"])
            created = parse_dt(u.get("createdDateTime")) if u else None
            records.append({"event": "joiner", "upn": h["upn"], "name": h["name"], "hr_date": sd,
                            "entra_action": created.isoformat() if created else "", "hours_to_action": "",
                            "result": "account provisioned" if created else "no account yet"})

    movers = 0
    for h in hr:
        for mv in h.get("moves", []):
            if start.date().isoformat() <= mv["date"] < end.date().isoformat():
                movers += 1
                records.append({"event": "mover", "upn": h["upn"], "name": h["name"], "hr_date": mv["date"],
                                "entra_action": "Update user", "hours_to_action": "", "result": f"now {mv['department']} / {mv['title']}"})

    hr_upns = {h["upn"] for h in hr}
    no_hr = 0
    for u in users:
        if u.get("userType") != "Member" or not u.get("accountEnabled") or u["userPrincipalName"] in hr_upns:
            continue
        kind = u.get("extension_accountKind", "member")
        if kind in ("service", "breakglass"):
            ex.add("DISP-PERSONNEL-JML", "low", "Non-personal account (no HR record)", u["userPrincipalName"],
                   f"{u.get('jobTitle')}: confirm named owner and purpose.")
            continue
        no_hr += 1
        ex.add("DISP-PERSONNEL-JML", "high", "Enabled account with no HR record", u["userPrincipalName"],
               f"Created {u.get('createdDateTime', '')[:10]} ({u.get('jobTitle')}). Confirm identity, screening and sponsor, or disable.")

    retained = 0
    grp = groups.get(RESTRICTED_GROUP)
    if grp:
        hr_by_upn = {h["upn"]: h for h in hr}
        for upn in grp["members"]:
            h = hr_by_upn.get(upn)
            if h and h["department"] not in RESTRICTED_DEPTS and h.get("moves"):
                retained += 1
                ex.add("DISP-PERSONNEL-JML", "high", "Mover retained restricted access", upn,
                       f"{h['name']} moved to {h['department']} on {h['moves'][-1]['date']} but is still in {RESTRICTED_GROUP}.")

    items = ex.items
    return StreamResult(
        stream=STREAM, period=period, as_of=as_of, collected_at=datetime.now(timezone.utc),
        control_ids=["DISP-PERSONNEL-JML"],
        sources=["auditLogs/directoryAudits", "users", "SharePoint list: HR Register", f"group: {RESTRICTED_GROUP}"],
        status=status_from(items),
        headline=f"{joiners} joiners, {movers} movers, {leavers_in_period} leavers; {late} late removals; "
                 f"{sum(1 for e in items if e.title == 'Leaver account still enabled')} leavers still enabled",
        metrics={"joiners": joiners, "movers": movers, "leavers": leavers_in_period, "late_removals": late,
                 "leavers_still_enabled": sum(1 for e in items if e.title == "Leaver account still enabled"),
                 "accounts_without_hr": no_hr, "movers_retaining_restricted_access": retained},
        records=records, raw={"hrRegister": hr, "directoryAudits": audits},
        exceptions=items, requires_attestation=True,
    )
