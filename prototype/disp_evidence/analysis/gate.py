"""Policy & citation gate - deterministic checks on any analysis draft.

Whatever engine wrote the draft (rules, local LLM, Claude), nothing reaches the
Security Officer as "ready" unless:
  * every cited artifact id exists in the sealed vault (no invented evidence),
  * COMPLIANT / PARTIAL claims cite at least one artifact,
  * no control is rated better than the deterministic baseline computed from
    the collectors' own exceptions (no over-claiming),
  * the draft still requires human sign-off.
"""

from __future__ import annotations

from ..controls import CONTROLS_BY_ID
from ..models import CompliancePackDraft, EvidenceArtifact, GateFinding, GateResult

RANK = {"STALE": 0, "GAP": 1, "PARTIAL": 2, "COMPLIANT": 3}


def run_gate(draft: CompliancePackDraft, artifacts: list[EvidenceArtifact], baseline: dict[str, str]) -> GateResult:
    valid = {a.artifact_id for a in artifacts}
    findings: list[GateFinding] = []

    def add(level: str, cid: str, msg: str) -> None:
        findings.append(GateFinding(level=level, control_id=cid, message=msg))  # type: ignore[arg-type]

    if not draft.requires_human_signoff:
        add("error", "*", "Draft attempted to waive human sign-off; forced back to DRAFT - PENDING SO REVIEW.")
        draft.requires_human_signoff = True

    seen = set()
    for a in draft.assessments:
        seen.add(a.control_id)
        if a.control_id not in CONTROLS_BY_ID:
            add("error", a.control_id, f"Unknown control id '{a.control_id}'.")
            continue
        missing = [c for c in a.cited_artifact_ids if c not in valid]
        if missing:
            add("error", a.control_id, f"Cites artifact ids that do not exist in the sealed vault: {missing}")
        if a.status in ("COMPLIANT", "PARTIAL") and not a.cited_artifact_ids:
            add("error", a.control_id, f"{a.status} claimed without citing any evidence.")
        base = baseline.get(a.control_id)
        if base and RANK[a.status] > RANK[base]:
            add("error", a.control_id, f"Overclaim: draft says {a.status} but collected evidence supports at most {base}.")
        elif base and RANK[a.status] < RANK[base]:
            add("info", a.control_id, f"Draft is stricter than baseline ({a.status} vs {base}); acceptable, review rationale.")
    for cid in baseline:
        if cid not in seen:
            add("warning", cid, "Control not assessed in this draft.")
    return GateResult(passed=not any(f.level == "error" for f in findings), findings=findings)
