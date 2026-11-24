from __future__ import annotations

from datetime import datetime, timezone

from disp_evidence.analysis.gate import run_gate
from disp_evidence.models import CompliancePackDraft, ControlAssessment, EvidenceArtifact

NOW = datetime(2026, 10, 31, tzinfo=timezone.utc)
ARTS = [EvidenceArtifact(artifact_id="2026-10/mfa/summary.json", source_system="mfa", collected_at=NOW, sha256_hash="a" * 64, summary="")]


def _draft(status: str, cites: list[str]) -> CompliancePackDraft:
    return CompliancePackDraft(pack_title="t", generated_at_utc=NOW.isoformat(), engine="test",
                               assessments=[ControlAssessment(control_id="E8-MFA-ML2", status=status, confidence=0.9,  # type: ignore[arg-type]
                                                              cited_artifact_ids=cites, rationale="r", recommended_action="a")],
                               open_questions_for_so=[])


def test_gate_rejects_fabricated_citation():
    res = run_gate(_draft("GAP", ["2026-10/mfa/invented.json"]), ARTS, baseline={"E8-MFA-ML2": "GAP"})
    assert not res.passed
    assert any("invented.json" in f.message for f in res.findings)


def test_gate_rejects_overclaim_against_deterministic_baseline():
    res = run_gate(_draft("COMPLIANT", ["2026-10/mfa/summary.json"]), ARTS, baseline={"E8-MFA-ML2": "GAP"})
    assert not res.passed
    assert any("overclaim" in f.message.lower() for f in res.findings)


def test_gate_rejects_positive_status_without_citation():
    res = run_gate(_draft("PARTIAL", []), ARTS, baseline={"E8-MFA-ML2": "PARTIAL"})
    assert not res.passed


def test_gate_passes_grounded_matching_draft_and_warns_on_missing_controls():
    res = run_gate(_draft("GAP", ["2026-10/mfa/summary.json"]), ARTS, baseline={"E8-MFA-ML2": "GAP", "DISP-TRAINING": "COMPLIANT"})
    assert res.passed
    assert any(f.level == "warning" and f.control_id == "DISP-TRAINING" for f in res.findings)
