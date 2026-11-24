"""Microsoft Graph connector (read-only) - NOT exercised against a live tenant yet.

This is the path from the demo to a real client. It is written against the
documented Graph v1.0 endpoints, but it has only been exercised through the
unit tests' fakes, not against a real tenant. Expect field-mapping fixes on
first contact with a real tenant.

Auth: OAuth2 client-credentials with a client secret, for the prototype only. The
business case calls for certificate auth + managed identity in production; swap
`_token()` for an MSAL certificate credential before any client deployment.

Non-Graph sources (HR register, training LMS export, visitor register, incident
register) are read from a CSV/JSON "drop" folder, mirroring the business case's
"SharePoint list or CSV drop" fallback.

Environment:
  DISP_CONNECTOR=graph
  DISP_GRAPH_TENANT_ID, DISP_GRAPH_CLIENT_ID, DISP_GRAPH_CLIENT_SECRET
  DISP_DROP_DIR  (folder with hr.json, training.json, visitors.json, incidents.json)
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

GRAPH = "https://graph.microsoft.com/v1.0"
DEFENDER = "https://api.securitycenter.microsoft.com"


class GraphConnector:
    name = "graph"

    def __init__(self, tenant_id: str, client_id: str, client_secret: str, drop_dir: Path, tenant_name: str = ""):
        self.tenant_id, self.client_id, self.client_secret = tenant_id, client_id, client_secret
        self.drop_dir = drop_dir
        self.tenant_name = tenant_name or tenant_id
        self._tokens: dict[str, str] = {}

    @classmethod
    def from_env(cls) -> "GraphConnector":
        missing = [k for k in ("DISP_GRAPH_TENANT_ID", "DISP_GRAPH_CLIENT_ID", "DISP_GRAPH_CLIENT_SECRET") if not os.environ.get(k)]
        if missing:
            raise RuntimeError(f"Graph connector needs {', '.join(missing)}")
        return cls(os.environ["DISP_GRAPH_TENANT_ID"], os.environ["DISP_GRAPH_CLIENT_ID"],
                   os.environ["DISP_GRAPH_CLIENT_SECRET"], Path(os.environ.get("DISP_DROP_DIR", "drop")),
                   os.environ.get("DISP_TENANT_NAME", ""))

    # ------------------------------------------------------------- transport
    def _token(self, scope: str) -> str:
        if scope not in self._tokens:
            body = urllib.parse.urlencode({"client_id": self.client_id, "client_secret": self.client_secret,
                                           "scope": scope, "grant_type": "client_credentials"}).encode()
            url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
            with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=30) as resp:
                self._tokens[scope] = json.load(resp)["access_token"]
        return self._tokens[scope]

    def _get_all(self, url: str, scope: str = "https://graph.microsoft.com/.default") -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        while url:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self._token(scope)}",
                                                       "ConsistencyLevel": "eventual"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                page = json.load(resp)
            items.extend(page.get("value", []))
            url = page.get("@odata.nextLink")
        return items

    def _drop(self, name: str) -> list[dict[str, Any]]:
        path = self.drop_dir / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    # ------------------------------------------------------------- Graph sources
    # Graph returns *current* state; `as_of` is honoured only for event/log sources.
    def users(self, as_of: datetime) -> list[dict[str, Any]]:
        sel = "id,displayName,userPrincipalName,userType,accountEnabled,createdDateTime,department,jobTitle,companyName,employeeId,signInActivity"
        users = self._get_all(f"{GRAPH}/users?$select={sel}&$top=999")
        for u in users:
            u.setdefault("extension_accountKind", "guest" if u.get("userType") == "Guest" else "member")
        return users

    def role_assignments(self, as_of: datetime) -> list[dict[str, Any]]:
        rows = self._get_all(f"{GRAPH}/roleManagement/directory/roleAssignments?$expand=principal,roleDefinition")
        return [{"roleDisplayName": r.get("roleDefinition", {}).get("displayName"),
                 "principalUserPrincipalName": r.get("principal", {}).get("userPrincipalName") or r.get("principalId"),
                 "assignedDateTime": None} for r in rows]

    def privileged_groups(self, as_of: datetime) -> list[dict[str, Any]]:
        names = [n.strip() for n in os.environ.get("DISP_PRIVILEGED_GROUPS", "").split(",") if n.strip()]
        out = []
        for name in names:
            q = urllib.parse.quote(f"displayName eq '{name}'")
            groups = self._get_all(f"{GRAPH}/groups?$filter={q}&$select=id,displayName")
            for g in groups:
                owners = self._get_all(f"{GRAPH}/groups/{g['id']}/owners?$select=userPrincipalName")
                members = self._get_all(f"{GRAPH}/groups/{g['id']}/members?$select=userPrincipalName")
                out.append({"displayName": g["displayName"], "owners": [o.get("userPrincipalName") for o in owners],
                            "members": [m.get("userPrincipalName") for m in members]})
        return out

    def directory_audits(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        flt = urllib.parse.quote(f"activityDateTime ge {start:%Y-%m-%dT%H:%M:%SZ} and activityDateTime lt {end:%Y-%m-%dT%H:%M:%SZ}")
        rows = self._get_all(f"{GRAPH}/auditLogs/directoryAudits?$filter={flt}")
        out = []
        for r in rows:
            target = next((t.get("userPrincipalName") for t in r.get("targetResources", []) if t.get("userPrincipalName")), None)
            out.append({"activityDateTime": r.get("activityDateTime"), "activityDisplayName": r.get("activityDisplayName"),
                        "targetUserPrincipalName": target,
                        "initiatedBy": (r.get("initiatedBy", {}).get("user") or {}).get("userPrincipalName")})
        return out

    def managed_devices(self, as_of: datetime) -> list[dict[str, Any]]:
        sel = "deviceName,operatingSystem,osVersion,userPrincipalName,lastSyncDateTime,managementAgent"
        rows = self._get_all(f"{GRAPH}/deviceManagement/managedDevices?$select={sel}")
        for r in rows:
            r.setdefault("internetFacing", False)
        return rows

    def vulnerabilities(self, as_of: datetime) -> list[dict[str, Any]]:
        rows = self._get_all(f"{DEFENDER}/api/machines/SoftwareVulnerabilitiesByMachine",
                             scope="https://api.securitycenter.microsoft.com/.default")
        # Defender does not expose vendor release date directly; firstSeenTimestamp is
        # used as a conservative proxy (it is >= release date).
        return [{"vulnId": r.get("cveId"), "product": r.get("softwareName"), "category": _category(r.get("softwareName", "")),
                 "severity": (r.get("vulnerabilitySeverityLevel") or "").lower(), "deviceName": r.get("deviceName"),
                 "releasedDateTime": r.get("firstSeenTimestamp"), "exploitAvailable": bool(r.get("exploitabilityLevel") not in (None, "NoExploit")),
                 "remediatedDateTime": None} for r in rows]

    def registration_details(self, as_of: datetime) -> list[dict[str, Any]]:
        rows = self._get_all(f"{GRAPH}/reports/authenticationMethods/userRegistrationDetails")
        return [{"userPrincipalName": r.get("userPrincipalName"), "userDisplayName": r.get("userDisplayName"),
                 "isAdmin": r.get("isAdmin", False), "userType": r.get("userType", "member"), "accountKind": "member",
                 "methodsRegistered": r.get("methodsRegistered", []), "isMfaRegistered": r.get("isMfaRegistered", False),
                 "isPhishingResistant": any(m in ("fido2", "windowsHelloForBusiness", "x509Certificate")
                                            for m in r.get("methodsRegistered", []))} for r in rows]

    def conditional_access(self, as_of: datetime) -> list[dict[str, Any]]:
        rows = self._get_all(f"{GRAPH}/identity/conditionalAccess/policies")
        return [{"displayName": r.get("displayName"), "state": r.get("state"),
                 "grantControl": ",".join((r.get("grantControls") or {}).get("builtInControls", [])), "excludes": []} for r in rows]

    # ------------------------------------------------------------- drop-folder sources
    def hr_records(self, as_of: datetime) -> list[dict[str, Any]]:
        return self._drop("hr.json")

    def training_records(self, as_of: datetime) -> list[dict[str, Any]]:
        return self._drop("training.json")

    def visitor_log(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        return [v for v in self._drop("visitors.json") if start.isoformat() <= v.get("signIn", "") < end.isoformat()]

    def incident_register(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        return [i for i in self._drop("incidents.json") if start.date().isoformat() <= i.get("date", "") < end.date().isoformat()]


def _category(product: str) -> str:
    p = product.lower()
    if any(k in p for k in ("windows", "macos", "ios")):
        return "os"
    if any(k in p for k in ("office", "365", "chrome", "edge", "firefox", "outlook", "acrobat", "reader", "defender")):
        return "priority_app"
    return "other_app"
