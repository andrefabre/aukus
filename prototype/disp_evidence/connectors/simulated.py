"""Connector backed by the deterministic simulated tenant."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..simulator import get_tenant


class SimulatedConnector:
    name = "simulated"

    def __init__(self, seed: int = 2026):
        self.tenant = get_tenant(seed)
        self.tenant_name = self.tenant.name

    def users(self, as_of: datetime) -> list[dict[str, Any]]:
        return self.tenant.users(as_of)

    def role_assignments(self, as_of: datetime) -> list[dict[str, Any]]:
        return self.tenant.role_assignments(as_of)

    def privileged_groups(self, as_of: datetime) -> list[dict[str, Any]]:
        return self.tenant.privileged_groups(as_of)

    def directory_audits(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        return self.tenant.directory_audits(start, end)

    def hr_records(self, as_of: datetime) -> list[dict[str, Any]]:
        return self.tenant.hr_records(as_of)

    def managed_devices(self, as_of: datetime) -> list[dict[str, Any]]:
        return self.tenant.managed_devices(as_of)

    def vulnerabilities(self, as_of: datetime) -> list[dict[str, Any]]:
        return self.tenant.vulnerabilities(as_of)

    def registration_details(self, as_of: datetime) -> list[dict[str, Any]]:
        return self.tenant.registration_details(as_of)

    def conditional_access(self, as_of: datetime) -> list[dict[str, Any]]:
        return self.tenant.conditional_access(as_of)

    def training_records(self, as_of: datetime) -> list[dict[str, Any]]:
        return self.tenant.training_records(as_of)

    def visitor_log(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        return self.tenant.visitor_log(start, end)

    def incident_register(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        return self.tenant.incident_register(start, end)
