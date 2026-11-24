"""Analysis layer: deterministic first, agent second, gate always.

Engines draft a CompliancePackDraft from sealed evidence; the deterministic gate
then checks citations and over-claims. Drafts live outside the vault (they are
not evidence) until the Security Officer approves one, at which point the
approved draft is appended to the vault as a signed addendum.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..config import Settings
from ..controls import CONTROLS
from ..models import CompliancePackDraft, EvidenceArtifact, GateResult
from ..vault import Vault
from . import llm, rules
from .gate import run_gate

ENGINES = ["rules", "faulty-llm-demo", "ollama", "claude"]


def engine_status() -> dict[str, tuple[bool, str]]:
    return {"rules": (True, "Deterministic rules engine ($0, always available)."),
            "faulty-llm-demo": (True, "DEMO ONLY ($0): imitates a hallucinating model (invents a citation, over-claims a control) so you can watch the gate block it."),
            "ollama": llm.ollama_status(), "claude": llm.claude_status()}


def artifacts_for(vault: Vault, period: str) -> list[EvidenceArtifact]:
    m = vault.manifest(period)
    sums = vault.summaries(period)
    return [EvidenceArtifact(artifact_id=a["artifact_id"], source_system=", ".join(a["sources"]),
                             collected_at=datetime.fromisoformat(a["collected_at"]), sha256_hash=a["sha256"],
                             summary=sums.get(a["stream"], {}).get("headline", "")) for a in m["artifacts"]]


def attested_streams(vault: Vault, period: str) -> set[str]:
    return {a["payload"]["subject"] for a in vault.addenda(period, "attestation") if a["payload"]["decision"] != "rejected"}


def run_analysis(settings: Settings, vault: Vault, period: str, engine: str = "rules") -> tuple[CompliancePackDraft, GateResult]:
    summaries = vault.summaries(period)
    # Evaluate the evidence as at the period's own cut-off (so history is not "stale" by
    # definition); staleness of the *latest* evidence is surfaced on the dashboard.
    today = datetime.fromisoformat(vault.manifest(period)["as_of"]).date()
    stale = settings.policy.evidence_stale_days
    baseline = {c.control_id: rules.baseline_status(summaries.get(c.stream), c.control_id, today, stale) for c in CONTROLS}
    if engine == "rules":
        draft = rules.analyse(period, summaries, attested_streams(vault, period), today, stale)
    elif engine == "faulty-llm-demo":
        draft = _faulty(rules.analyse(period, summaries, attested_streams(vault, period), today, stale), period)
    else:
        ok, why = engine_status()[engine]
        if not ok:
            raise RuntimeError(why)
        digest = rules.evidence_digest(summaries, period)
        draft = llm.analyse_ollama(period, digest) if engine == "ollama" else llm.analyse_claude(period, digest)
    gate = run_gate(draft, artifacts_for(vault, period), baseline)
    save_draft(settings, period, draft, gate)
    return draft, gate


def _faulty(draft: CompliancePackDraft, period: str) -> CompliancePackDraft:
    """Mimic typical LLM failure modes so the gate can be demonstrated for free."""
    draft.engine = "faulty-llm-demo (simulated hallucination)"
    gap = next((a for a in draft.assessments if a.status == "GAP"), None)
    if gap:
        gap.status = "COMPLIANT"
        gap.rationale = "All requirements appear to be met based on the evidence reviewed."
        gap.recommended_action = "No action required."
        gap.cited_artifact_ids = gap.cited_artifact_ids[:1] + [f"{period}/policies/access-control-policy-v3.pdf"]
    return draft


def _draft_path(settings: Settings, period: str):
    return settings.drafts_dir / f"{period}.json"


def save_draft(settings: Settings, period: str, draft: CompliancePackDraft, gate: GateResult) -> None:
    settings.drafts_dir.mkdir(parents=True, exist_ok=True)
    _draft_path(settings, period).write_text(json.dumps({"draft": draft.model_dump(mode="json"), "gate": gate.model_dump(mode="json"),
                                                         "saved_at": datetime.now(timezone.utc).isoformat()}, indent=1), encoding="utf-8")


def load_draft(settings: Settings, period: str) -> dict[str, Any] | None:
    p = _draft_path(settings, period)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def approved_analysis(vault: Vault, period: str) -> dict[str, Any] | None:
    items = vault.addenda(period, "approved_analysis")
    return items[-1] if items else None
