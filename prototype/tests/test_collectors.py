"""Each seeded control failure in the simulated tenant must be caught by its collector."""

from __future__ import annotations

from datetime import datetime, timezone

from disp_evidence.collectors import COLLECTORS
from disp_evidence.config import Policy
from disp_evidence.connectors import SimulatedConnector
from disp_evidence.simulator import get_tenant, month_bounds

CONN = SimulatedConnector(2026)
P = Policy()


def run(stream: str, period: str):
    _, end = month_bounds(period)
    return COLLECTORS[stream](CONN, period, end, P)


def titles(result) -> list[str]:
    return [e.title for e in result.exceptions]


def test_simulator_is_deterministic():
    a = SimulatedConnector(2026).users(datetime(2026, 8, 31, tzinfo=timezone.utc))
    b = get_tenant(2026).users(datetime(2026, 8, 31, tzinfo=timezone.utc))
    assert a == b


def test_late_leaver_removal_detected_in_june():
    r = run("jml", "2026-06")
    late = [e for e in r.exceptions if e.title == "Leaver access removed late"]
    assert late and late[0].severity == "high"          # 9 days late
    assert r.metrics["late_removals"] == 1


def test_orphan_leaver_still_enabled_is_critical_and_persists():
    for period in ("2026-08", "2026-09", "2026-10"):
        r = run("jml", period)
        crit = [e for e in r.exceptions if e.title == "Leaver account still enabled"]
        assert crit and crit[0].severity == "critical", period
        assert crit[0].subject == get_tenant(2026).orphan_upn


def test_account_without_hr_record_and_sticky_mover():
    r = run("jml", "2026-08")
    assert "Enabled account with no HR record" in titles(r)
    sticky = [e for e in r.exceptions if e.title == "Mover retained restricted access"]
    assert sticky and sticky[0].subject == get_tenant(2026).sticky_mover.upn


def test_global_admin_spike_and_stale_admin_in_september():
    r = run("access_review", "2026-09")
    assert r.metrics["global_admins"] == 5
    assert "Global Administrator count above policy" in titles(r)
    assert any(e.title == "Stale privileged account" and e.subject.startswith("j.ng") for e in r.exceptions)
    assert r.requires_attestation


def test_breakglass_exempt_from_inactivity():
    r = run("access_review", "2026-10")
    bg = get_tenant(2026).breakglass_upn
    assert not any(e.subject == bg for e in r.exceptions)


def test_exploited_vpn_patch_outside_48h_window_in_august():
    r = run("patch", "2026-08")
    vpn = [e for e in r.exceptions if e.subject == "BMF-VPN01"]
    assert vpn and "outside window" in vpn[0].title and "exploit" in vpn[0].detail


def test_unsupported_windows10_flagged():
    r = run("patch", "2026-02")   # before any Win10 owner leaves
    assert r.metrics["unsupported_os_devices"] == 3
    assert titles(r).count("Unsupported operating system") == 3
    # devices of leavers are retired with them; at least one Win10 device remains in October
    assert run("patch", "2026-10").metrics["unsupported_os_devices"] >= 1


def test_legacy_auth_flag_clears_when_policy_enforced():
    assert "Legacy authentication not blocked" in titles(run("mfa", "2026-06"))
    assert "Legacy authentication not blocked" not in titles(run("mfa", "2026-08"))


def test_mfa_coverage_improves_over_year():
    assert run("mfa", "2026-05").metrics["mfa_coverage_pct"] < run("mfa", "2026-08").metrics["mfa_coverage_pct"]


def test_visitor_and_incident_streams_produce_records():
    v = run("visitors", "2026-07")
    assert v.metrics["visits"] > 10 and v.records
    i = run("incidents", "2026-08")
    assert i.metrics["incidents"] == 1 and i.metrics["reportable"] == 1
