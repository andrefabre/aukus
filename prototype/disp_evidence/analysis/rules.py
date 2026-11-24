"""Deterministic analysis engine (default, $0).

Maps each control to its stream's sealed summary and derives a status purely
from the collector exceptions. This is also the *baseline* every other engine is
gated against.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from ..controls import CONTROLS, STREAMS_BY_ID
from ..models import CompliancePackDraft, ControlAssessment


def baseline_status(summary: dict[str, Any] | None, control_id: str, today: date, stale_days: int) -> str:
    if summary is None:
        return "GAP"
    as_of = datetime.fromisoformat(summary["as_of"]).date()
    if (today - as_of).days > stale_days:
        return "STALE"
    sev = {e["severity"] for e in summary["exceptions"] if e["control_id"] == control_id}
    if sev & {"critical", "high"}:
        return "GAP"
    if "medium" in sev:
        return "PARTIAL"
    return "COMPLIANT"


def evidence_digest(summaries: dict[str, dict[str, Any]], period: str) -> list[dict[str, Any]]:
    """Minimised per-control evidence: metrics + exception titles/counts, no personal identifiers.

    This is exactly what an LLM engine is allowed to see (data minimisation for
    APP 11 / APP 8 if a hosted model is switched on).
    """
    out = []
    for c in CONTROLS:
        s = summaries.get(c.stream)
        ex = [e for e in (s or {}).get("exceptions", []) if e["control_id"] == c.control_id]
        titles: dict[str, dict[str, Any]] = {}
        for e in ex:
            t = titles.setdefault(e["title"], {"title": e["title"], "severity": e["severity"], "count": 0})
            t["count"] += 1
        out.append({"control_id": c.control_id, "control_name": c.name, "framework": c.framework, "expectation": c.description,
                    "stream": c.stream, "evidence_artifacts": [f"{period}/{c.stream}/summary.json", f"{period}/{c.stream}/records.csv"] if s else [],
                    "headline": (s or {}).get("headline", "NO EVIDENCE COLLECTED"), "metrics": (s or {}).get("metrics", {}),
                    "exceptions": list(titles.values()), "as_of": (s or {}).get("as_of")})
    return out


def analyse(period: str, summaries: dict[str, dict[str, Any]], attested: set[str], today: date, stale_days: int) -> CompliancePackDraft:
    assessments = []
    questions = []
    for c in CONTROLS:
        s = summaries.get(c.stream)
        status = baseline_status(s, c.control_id, today, stale_days)
        ex = [e for e in (s or {}).get("exceptions", []) if e["control_id"] == c.control_id]
        crit = [e for e in ex if e["severity"] in ("critical", "high")]
        cites = [f"{period}/{c.stream}/summary.json", f"{period}/{c.stream}/records.csv"] if s else []
        if s is None:
            rationale = "No evidence was collected for this control in the period."
            action = "Run the collector or record why the control is out of scope."
        else:
            rationale = f"{s['headline']}. {len(ex)} exception(s) for this control ({len(crit)} critical/high)."
            action = "; ".join(sorted({e['title'] for e in crit})) or ("Review medium findings" if ex else "No action - maintain")
            if crit:
                action = "Remediate: " + action
        assessments.append(ControlAssessment(control_id=c.control_id, status=status, confidence=0.95 if s else 0.5,  # type: ignore[arg-type]
                                             cited_artifact_ids=cites, rationale=rationale, recommended_action=action))
        for e in ex:
            if e["severity"] == "critical":
                questions.append(f"[{c.control_id}] {e['title']} - {e['subject']}: confirm remediation owner and date.")
        stream = STREAMS_BY_ID[c.stream]
        if s is not None and stream.requires_attestation and c.stream not in attested:
            q = f"[{c.stream}] {stream.name} for {period} is awaiting your attestation."
            if q not in questions:
                questions.append(q)
    return CompliancePackDraft(pack_title=f"Control assessment {period}", generated_at_utc=datetime.now(timezone.utc).isoformat(),
                               engine="rules (deterministic)", assessments=assessments, open_questions_for_so=questions)
