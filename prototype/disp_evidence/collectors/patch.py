"""Stream 2 - Patch compliance log, scored against E8 ML2 patch timeframes."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from ..config import Policy
from ..connectors.base import Connector
from ..models import StreamResult
from ..simulator import month_bounds
from .common import ExceptionBuilder, parse_dt, pct, status_from

STREAM = "patch"
UNSUPPORTED = {("Windows", "10")}   # Windows 10 reached end of support 14 Oct 2025


def window_days(item: dict, policy: Policy) -> int:
    cat = item["category"]
    if cat == "internet_facing":
        return policy.patch_exploited_days if item.get("exploitAvailable") else policy.patch_internet_facing_days
    if cat == "os":
        return policy.patch_os_days
    if cat == "priority_app":
        return policy.patch_priority_apps_days
    return policy.patch_other_apps_days


def control_for(item: dict) -> str:
    return "E8-PATCH-OS-ML2" if item["category"] in ("os", "internet_facing") else "E8-PATCH-APP-ML2"


def collect(conn: Connector, period: str, as_of: datetime, policy: Policy) -> StreamResult:
    start, _ = month_bounds(period)
    devices = conn.managed_devices(as_of)
    vulns = conn.vulnerabilities(as_of)
    ex = ExceptionBuilder(STREAM, period)

    overdue_by_dev: dict[str, list[dict]] = defaultdict(list)
    late_by_dev: dict[str, list[dict]] = defaultdict(list)
    open_by_dev: dict[str, int] = defaultdict(int)
    fixed_in_period = fixed_on_time = 0
    cat_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"remediated": 0, "on_time": 0, "open_overdue": 0})

    for v in vulns:
        released = parse_dt(v["releasedDateTime"])
        fixed = parse_dt(v.get("remediatedDateTime"))
        window = timedelta(days=window_days(v, policy))
        if fixed is None or fixed > as_of:
            open_by_dev[v["deviceName"]] += 1
            if as_of - released > window:
                overdue_by_dev[v["deviceName"]].append(v)
                cat_stats[v["category"]]["open_overdue"] += 1
        elif fixed >= start:
            fixed_in_period += 1
            cat_stats[v["category"]]["remediated"] += 1
            if fixed - released <= window:
                fixed_on_time += 1
                cat_stats[v["category"]]["on_time"] += 1
            else:
                late_by_dev[v["deviceName"]].append(v)

    records = []
    compliant = 0
    for d in devices:
        name = d["deviceName"]
        major = (d.get("osVersion") or "").split(" ")[0]
        unsupported = (d["operatingSystem"], major) in UNSUPPORTED
        last_sync = parse_dt(d.get("lastSyncDateTime"))
        stale_sync = last_sync is not None and (as_of - last_sync).days > 14
        overdue = overdue_by_dev.get(name, [])
        is_ok = not overdue and not unsupported and not stale_sync
        compliant += is_ok
        if unsupported:
            ex.add("E8-PATCH-OS-ML2", "high", "Unsupported operating system", name,
                   f"{d['operatingSystem']} {d.get('osVersion')} no longer receives security fixes; replace or upgrade (owner {d.get('userPrincipalName')}).")
        if stale_sync:
            ex.add("E8-PATCH-OS-ML2", "medium", "Device not checking in", name, f"Last sync {last_sync:%Y-%m-%d}; patch state unknown.")
        if overdue:
            worst = max(overdue, key=lambda v: (v["category"] == "internet_facing", v.get("exploitAvailable"), as_of - parse_dt(v["releasedDateTime"])))
            sev = "critical" if worst["category"] == "internet_facing" else "high"
            age = (as_of - parse_dt(worst["releasedDateTime"])).days
            ex.add(control_for(worst), sev, f"{len(overdue)} patch(es) overdue", name,
                   f"Oldest: {worst['product']} ({worst['vulnId']}), {age} days since release vs {window_days(worst, policy)}-day window.")
        late = late_by_dev.get(name, [])
        internet_late = [v for v in late if v["category"] == "internet_facing"]
        if internet_late:
            v = internet_late[0]
            took = (parse_dt(v["remediatedDateTime"]) - parse_dt(v["releasedDateTime"])).total_seconds() / 86400
            ex.add("E8-PATCH-OS-ML2", "high", "Internet-facing patch applied outside window", name,
                   f"{v['product']} ({v['vulnId']}){' - exploit available' if v.get('exploitAvailable') else ''}: applied after {took:.1f} days vs {window_days(v, policy) * 24 if v.get('exploitAvailable') else window_days(v, policy)}{' hours' if v.get('exploitAvailable') else ' days'}.")
        records.append({"device": name, "os": f"{d['operatingSystem']} {d.get('osVersion', '')}".strip(),
                        "owner": d.get("userPrincipalName", ""), "last_sync": last_sync.isoformat() if last_sync else "",
                        "open_vulns": open_by_dev.get(name, 0), "overdue": len(overdue), "remediated_late_in_period": len(late),
                        "unsupported_os": unsupported, "compliant": is_ok})

    items = ex.items
    total_overdue = sum(len(v) for v in overdue_by_dev.values())
    return StreamResult(
        stream=STREAM, period=period, as_of=as_of, collected_at=datetime.now(timezone.utc),
        control_ids=["E8-PATCH-OS-ML2", "E8-PATCH-APP-ML2"],
        sources=["deviceManagement/managedDevices", "Defender TVM SoftwareVulnerabilitiesByMachine"],
        status=status_from(items),
        headline=f"{pct(compliant, len(devices))}% of {len(devices)} devices compliant; {total_overdue} overdue patches; {pct(fixed_on_time, fixed_in_period)}% remediated within window",
        metrics={"devices": len(devices), "devices_compliant": compliant, "device_compliance_pct": pct(compliant, len(devices)),
                 "open_vulns": sum(open_by_dev.values()), "overdue_open": total_overdue,
                 "remediated_in_period": fixed_in_period, "remediated_on_time_pct": pct(fixed_on_time, fixed_in_period),
                 "unsupported_os_devices": sum(1 for r in records if r["unsupported_os"]),
                 "by_category": {k: dict(v) for k, v in cat_stats.items()}},
        records=records, raw={"managedDevices": devices, "vulnerabilities": vulns},
        exceptions=items,
    )
