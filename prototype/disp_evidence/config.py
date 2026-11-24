"""Runtime settings and control-policy thresholds.

Every threshold here is a *policy parameter*, not a statement of law. The
defaults follow the ASD Essential Eight Maturity Model (ML2) as we read it;
verify them against the current published model before relying on them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

PROTOTYPE_ROOT = Path(__file__).resolve().parent.parent


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value) if value else default


@dataclass(frozen=True)
class Policy:
    # Patching (E8 ML2): days from release/publication to remediation.
    patch_os_days: int = 30                # OS of workstations / non-internet-facing servers
    patch_internet_facing_days: int = 14   # internet-facing services
    patch_exploited_days: int = 2          # internet-facing with a known exploit (48 hours)
    patch_priority_apps_days: int = 14     # office, browsers, email, PDF, security products
    patch_other_apps_days: int = 30        # other applications
    # Privileged access
    privileged_inactive_days: int = 45     # disable privileged access after 45 days inactivity
    standard_inactive_days: int = 90
    guest_inactive_days: int = 90
    max_global_admins: int = 4
    min_global_admins: int = 2
    # Joiner / mover / leaver
    leaver_removal_hours: int = 24
    # Training
    training_validity_days: int = 365
    new_starter_training_days: int = 30
    # MFA
    mfa_coverage_target: float = 1.0
    # Evidence freshness (ASR / assurance)
    evidence_stale_days: int = 45
    # WORM retention applied to sealed evidence (years)
    retention_years: int = 7


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: _env_path("DISP_DATA_DIR", PROTOTYPE_ROOT / "var"))
    tenant_seed: int = int(os.environ.get("DISP_TENANT_SEED", "2026"))
    # "today" can be pinned for reproducible demos (YYYY-MM-DD).
    today_override: str | None = os.environ.get("DISP_TODAY")
    policy: Policy = field(default_factory=Policy)

    @property
    def vault_dir(self) -> Path:
        return self.data_dir / "vault"

    @property
    def keys_dir(self) -> Path:
        return self.data_dir / "keys"

    @property
    def drafts_dir(self) -> Path:
        return self.data_dir / "drafts"

    @property
    def packs_dir(self) -> Path:
        return self.data_dir / "packs"

    def today(self) -> date:
        if self.today_override:
            return date.fromisoformat(self.today_override)
        return date.today()


def get_settings() -> Settings:
    return Settings()
