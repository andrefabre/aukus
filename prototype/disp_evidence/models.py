"""Typed records shared across collectors, vault, analysis and reporting."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "high", "medium", "low"]
StreamStatus = Literal["PASS", "WARN", "FAIL"]
AssessmentStatus = Literal["COMPLIANT", "PARTIAL", "GAP", "STALE"]


class EvidenceException(BaseModel):
    """A control exception raised by a collector (becomes a Planner/Teams task)."""

    exception_id: str
    stream: str
    control_id: str
    severity: Severity
    title: str
    subject: str = ""
    detail: str = ""


class StreamResult(BaseModel):
    """Output of one collector for one monthly period."""

    stream: str
    period: str                      # YYYY-MM
    as_of: datetime                  # collection cut-off (end of period or "now")
    collected_at: datetime
    control_ids: list[str]
    sources: list[str]               # source endpoints / lists the data came from
    status: StreamStatus
    headline: str
    metrics: dict[str, Any]
    records: list[dict[str, Any]]    # normalised rows (-> records.csv)
    raw: dict[str, Any]              # raw source payload (-> raw.json)
    exceptions: list[EvidenceException]
    requires_attestation: bool = False


class EvidenceArtifact(BaseModel):
    """A sealed artifact as the analysis layer sees it (metadata only)."""

    artifact_id: str
    source_system: str
    collected_at: datetime
    sha256_hash: str
    summary: str


class ControlAssessment(BaseModel):
    control_id: str = Field(..., description="Control id from the catalogue, e.g. E8-MFA")
    status: AssessmentStatus
    confidence: float = Field(..., ge=0.0, le=1.0)
    cited_artifact_ids: list[str] = Field(
        ..., description="Must reference existing EvidenceArtifact.artifact_id values"
    )
    rationale: str
    recommended_action: str


class CompliancePackDraft(BaseModel):
    pack_title: str
    generated_at_utc: str
    engine: str = "rules"
    requires_human_signoff: bool = True
    assessments: list[ControlAssessment]
    open_questions_for_so: list[str]


class GateFinding(BaseModel):
    level: Literal["error", "warning", "info"]
    control_id: str
    message: str


class GateResult(BaseModel):
    passed: bool
    findings: list[GateFinding]


class Attestation(BaseModel):
    period: str
    subject: str                      # stream id, or "analysis"
    decision: Literal["approved", "approved_with_comments", "rejected"]
    signed_by: str
    role: str = "Security Officer"
    comment: str = ""
    signed_at: datetime
    manifest_sha256: str              # binds the sign-off to the sealed evidence it covers
