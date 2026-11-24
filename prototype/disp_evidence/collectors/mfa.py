"""Stream 4 - MFA and Conditional Access posture."""

from __future__ import annotations

from datetime import datetime, timezone

from ..config import Policy
from ..connectors.base import Connector
from ..models import StreamResult
from .common import ExceptionBuilder, pct, status_from

STREAM = "mfa"


def collect(conn: Connector, period: str, as_of: datetime, policy: Policy) -> StreamResult:
    regs = conn.registration_details(as_of)
    ca = conn.conditional_access(as_of)
    ex = ExceptionBuilder(STREAM, period)
    records = []

    people = [r for r in regs if r["accountKind"] == "member"]
    admins = [r for r in regs if r["isAdmin"]]
    for r in regs:
        flag = ""
        if r["isAdmin"] and not r["isMfaRegistered"]:
            flag = "admin without MFA"
            ex.add("E8-MFA-ML2", "critical", "Privileged user without MFA", r["userPrincipalName"])
        elif r["isAdmin"] and not r["isPhishingResistant"]:
            flag = "admin without phishing-resistant method"
            ex.add("E8-MFA-ML2", "medium", "Privileged user without phishing-resistant MFA", r["userPrincipalName"],
                   f"Registered: {', '.join(r['methodsRegistered'])}. CA03 targets phishing-resistant strength for admin roles.")
        elif r["accountKind"] == "member" and not r["isMfaRegistered"]:
            flag = "no MFA method registered"
            ex.add("E8-MFA-ML2", "high", "User without MFA registered", r["userPrincipalName"])
        elif r["accountKind"] == "service" and not r["isMfaRegistered"]:
            flag = "excluded from MFA (service account)"
            ex.add("E8-MFA-ML2", "medium", "Service account excluded from MFA", r["userPrincipalName"],
                   "Document compensating controls (named location, no interactive sign-in) or move to workload identity.")
        records.append({"upn": r["userPrincipalName"], "kind": r["accountKind"], "admin": r["isAdmin"],
                        "methods": " ".join(r["methodsRegistered"]), "mfa_registered": r["isMfaRegistered"],
                        "phishing_resistant": r["isPhishingResistant"], "flag": flag})

    states = {p["displayName"]: p["state"] for p in ca}
    for p in ca:
        records.append({"upn": f"[policy] {p['displayName']}", "kind": "conditional-access", "admin": "",
                        "methods": p["grantControl"], "mfa_registered": "", "phishing_resistant": "", "flag": p["state"]})
    mfa_all = next((s for n, s in states.items() if "Require MFA for all users" in n), None)
    if mfa_all != "enabled":
        ex.add("E8-MFA-ML2", "critical", "MFA-for-all-users policy not enforced", "CA01", f"State: {mfa_all}")
    legacy = next((s for n, s in states.items() if "legacy authentication" in n), None)
    if legacy != "enabled":
        ex.add("E8-MFA-ML2", "high", "Legacy authentication not blocked", "CA02",
               f"Policy state is '{legacy}'. Legacy protocols bypass MFA.")

    covered = sum(1 for r in people if r["isMfaRegistered"])
    items = ex.items
    return StreamResult(
        stream=STREAM, period=period, as_of=as_of, collected_at=datetime.now(timezone.utc),
        control_ids=["E8-MFA-ML2"],
        sources=["reports/authenticationMethods/userRegistrationDetails", "identity/conditionalAccess/policies"],
        status=status_from(items),
        headline=f"MFA coverage {pct(covered, len(people))}% of {len(people)} staff; admins phishing-resistant "
                 f"{pct(sum(1 for a in admins if a['isPhishingResistant']), len(admins))}%; legacy auth {'blocked' if legacy == 'enabled' else 'NOT blocked'}",
        metrics={"staff_accounts": len(people), "mfa_registered": covered, "mfa_coverage_pct": pct(covered, len(people)),
                 "admins": len(admins), "admin_mfa_pct": pct(sum(1 for a in admins if a["isMfaRegistered"]), len(admins)),
                 "admin_phishing_resistant_pct": pct(sum(1 for a in admins if a["isPhishingResistant"]), len(admins)),
                 "legacy_auth_blocked": legacy == "enabled", "ca_policies": states},
        records=records, raw={"userRegistrationDetails": regs, "conditionalAccessPolicies": ca},
        exceptions=items,
    )
