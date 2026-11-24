"""Connector contract + the published permission map.

The permission map is a client-facing artefact (see the business case's risk
"client reluctance to grant tenant access"): every Graph permission the pipeline
asks for is listed against the evidence it produces. All are read-only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol


class Connector(Protocol):
    name: str
    tenant_name: str

    def users(self, as_of: datetime) -> list[dict[str, Any]]: ...
    def role_assignments(self, as_of: datetime) -> list[dict[str, Any]]: ...
    def privileged_groups(self, as_of: datetime) -> list[dict[str, Any]]: ...
    def directory_audits(self, start: datetime, end: datetime) -> list[dict[str, Any]]: ...
    def hr_records(self, as_of: datetime) -> list[dict[str, Any]]: ...
    def managed_devices(self, as_of: datetime) -> list[dict[str, Any]]: ...
    def vulnerabilities(self, as_of: datetime) -> list[dict[str, Any]]: ...
    def registration_details(self, as_of: datetime) -> list[dict[str, Any]]: ...
    def conditional_access(self, as_of: datetime) -> list[dict[str, Any]]: ...
    def training_records(self, as_of: datetime) -> list[dict[str, Any]]: ...
    def visitor_log(self, start: datetime, end: datetime) -> list[dict[str, Any]]: ...
    def incident_register(self, start: datetime, end: datetime) -> list[dict[str, Any]]: ...


PERMISSION_MAP: list[dict[str, str]] = [
    {"stream": "access_review", "source": "GET /users?$select=...,signInActivity", "permission": "User.Read.All, AuditLog.Read.All",
     "evidence": "Account inventory, guest list, last sign-in (stale accounts)"},
    {"stream": "access_review", "source": "GET /roleManagement/directory/roleAssignments?$expand=principal", "permission": "RoleManagement.Read.Directory",
     "evidence": "Privileged role holders"},
    {"stream": "access_review", "source": "GET /groups/{id}/owners, /members", "permission": "GroupMember.Read.All",
     "evidence": "Privileged group owners and members"},
    {"stream": "patch", "source": "GET /deviceManagement/managedDevices", "permission": "DeviceManagementManagedDevices.Read.All",
     "evidence": "Device inventory, OS version, last sync"},
    {"stream": "patch", "source": "Defender API: GET /api/machines/SoftwareVulnerabilitiesByMachine", "permission": "Vulnerability.Read.All (WindowsDefenderATP)",
     "evidence": "Open vulnerabilities, release / remediation dates, exploit flag"},
    {"stream": "jml", "source": "GET /auditLogs/directoryAudits", "permission": "AuditLog.Read.All",
     "evidence": "Account create / disable / update / group and role changes"},
    {"stream": "jml", "source": "SharePoint list 'HR Register' (Sites.Selected) or CSV drop", "permission": "Sites.Selected (read)",
     "evidence": "Joiners, movers, leavers from HR"},
    {"stream": "mfa", "source": "GET /reports/authenticationMethods/userRegistrationDetails", "permission": "AuditLog.Read.All",
     "evidence": "MFA / phishing-resistant method registration per user"},
    {"stream": "mfa", "source": "GET /identity/conditionalAccess/policies", "permission": "Policy.Read.All",
     "evidence": "Conditional Access policy state"},
    {"stream": "training", "source": "GET /security/attackSimulation/... or LMS CSV drop", "permission": "AttackSimulation.Read.All",
     "evidence": "Training completions"},
    {"stream": "visitors", "source": "SharePoint list 'Visitor Register' (Forms)", "permission": "Sites.Selected (read)",
     "evidence": "Visitor entries, sign-out, ID check, escort"},
    {"stream": "asr", "source": "SharePoint list 'Incident Register'", "permission": "Sites.Selected (read)",
     "evidence": "Security incidents and Defence reporting dates"},
]
