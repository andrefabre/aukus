"""Stream 1 - Access review log (privileged roles, group owners, guests, stale accounts)."""

from __future__ import annotations

from datetime import datetime, timezone

from ..config import Policy
from ..connectors.base import Connector
from ..models import StreamResult
from .common import ExceptionBuilder, days_between, parse_dt, status_from

STREAM = "access_review"


def collect(conn: Connector, period: str, as_of: datetime, policy: Policy) -> StreamResult:
    users = conn.users(as_of)
    by_upn = {u["userPrincipalName"]: u for u in users}
    roles = conn.role_assignments(as_of)
    groups = conn.privileged_groups(as_of)
    ex = ExceptionBuilder(STREAM, period)
    records: list[dict] = []

    def last_seen(upn: str) -> tuple[datetime | None, float | None]:
        u = by_upn.get(upn) or {}
        last = parse_dt((u.get("signInActivity") or {}).get("lastSignInDateTime"))
        return last, days_between(last, as_of)

    privileged = sorted({r["principalUserPrincipalName"] for r in roles})
    stale_priv = []
    for r in roles:
        upn = r["principalUserPrincipalName"]
        u = by_upn.get(upn, {})
        last, idle = last_seen(upn)
        kind = u.get("extension_accountKind", "member")
        flag = ""
        if kind == "breakglass":
            flag = "break-glass: excluded from inactivity rule (documented exception)"
        elif idle is None or idle > policy.privileged_inactive_days:
            flag = f"privileged account inactive > {policy.privileged_inactive_days} days"
            if upn not in stale_priv:
                stale_priv.append(upn)
                ex.add("E8-ADMIN-ML2", "high", "Stale privileged account", upn,
                       f"Holds privileged role(s); last sign-in {last:%Y-%m-%d} ({idle:.0f} days). E8 ML2 expects privileged access disabled after {policy.privileged_inactive_days} days of inactivity."
                       if last else "Holds privileged role(s); no sign-in recorded.")
        records.append({"type": "role", "principal": upn, "assignment": r["roleDisplayName"],
                        "account_enabled": u.get("accountEnabled"), "last_sign_in": last.isoformat() if last else "",
                        "days_inactive": idle if idle is not None else "", "flag": flag})

    gas = [r for r in roles if r["roleDisplayName"] == "Global Administrator"]
    if len(gas) > policy.max_global_admins:
        ex.add("E8-ADMIN-ML2", "high", "Global Administrator count above policy",
               ", ".join(r["principalUserPrincipalName"] for r in gas),
               f"{len(gas)} Global Administrators (policy maximum {policy.max_global_admins}). Validate each assignment.")
    elif len(gas) < policy.min_global_admins:
        ex.add("E8-ADMIN-ML2", "medium", "Too few Global Administrators", "", f"{len(gas)} assigned (minimum {policy.min_global_admins}).")

    for g in groups:
        if not g["owners"]:
            ex.add("DISP-ACCESS-REVIEW", "medium", "Privileged group has no active owner", g["displayName"],
                   "No accountable owner to review membership. Assign an owner.")
        for upn in g["owners"]:
            records.append({"type": "group-owner", "principal": upn, "assignment": g["displayName"],
                            "account_enabled": by_upn.get(upn, {}).get("accountEnabled"), "last_sign_in": "", "days_inactive": "", "flag": ""})
        for upn in g["members"]:
            u = by_upn.get(upn, {})
            last, idle = last_seen(upn)
            flag = ""
            if u and not u.get("accountEnabled"):
                flag = "disabled account still a member"
                ex.add("DISP-ACCESS-REVIEW", "low", "Disabled account retained in privileged group", upn, g["displayName"])
            records.append({"type": "group-member", "principal": upn, "assignment": g["displayName"],
                            "account_enabled": u.get("accountEnabled"), "last_sign_in": last.isoformat() if last else "",
                            "days_inactive": idle if idle is not None else "", "flag": flag})

    guests = [u for u in users if u.get("userType") == "Guest" and u.get("accountEnabled")]
    stale_guests = 0
    for g in guests:
        last, idle = last_seen(g["userPrincipalName"])
        flag = ""
        if idle is None or idle > policy.guest_inactive_days:
            flag = f"guest inactive > {policy.guest_inactive_days} days"
            stale_guests += 1
            ex.add("DISP-ACCESS-REVIEW", "medium", "Stale guest account", g["userPrincipalName"],
                   f"{g.get('companyName') or 'external'}; last sign-in {last:%Y-%m-%d}." if last else "Never signed in.")
        records.append({"type": "guest", "principal": g["userPrincipalName"], "assignment": g.get("companyName") or "",
                        "account_enabled": True, "last_sign_in": last.isoformat() if last else "",
                        "days_inactive": idle if idle is not None else "", "flag": flag})

    members = [u for u in users if u.get("userType") == "Member" and u.get("accountEnabled")
               and u.get("extension_accountKind") == "member"]
    stale_std = 0
    for u in members:
        if u["userPrincipalName"] in privileged:
            continue
        last, idle = last_seen(u["userPrincipalName"])
        if idle is not None and idle > policy.standard_inactive_days:
            stale_std += 1
            ex.add("DISP-ACCESS-REVIEW", "low", "Inactive standard account", u["userPrincipalName"], f"{idle:.0f} days since sign-in.")

    items = ex.items
    return StreamResult(
        stream=STREAM, period=period, as_of=as_of, collected_at=datetime.now(timezone.utc),
        control_ids=["DISP-ACCESS-REVIEW", "E8-ADMIN-ML2"],
        sources=["users (signInActivity)", "roleManagement/directory/roleAssignments", "groups owners/members"],
        status=status_from(items),
        headline=f"{len(privileged)} privileged principals, {len(gas)} Global Admins, {len(stale_priv)} stale privileged, {stale_guests} stale guests",
        metrics={"enabled_accounts": sum(1 for u in users if u.get("accountEnabled")), "privileged_principals": len(privileged),
                 "global_admins": len(gas), "stale_privileged": len(stale_priv), "guests": len(guests),
                 "stale_guests": stale_guests, "stale_standard": stale_std, "privileged_groups": len(groups),
                 "groups_without_owner": sum(1 for g in groups if not g["owners"])},
        records=records, raw={"users": users, "roleAssignments": roles, "privilegedGroups": groups},
        exceptions=items, requires_attestation=True,
    )
