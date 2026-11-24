"""Monthly evidence pack and ASR data pack (JSON + PDF).

Packs are *derived* from sealed evidence and can be regenerated at any time;
the PDF carries the manifest hash, signature key id and a fresh integrity check
so an assessor can tie it back to the immutable store.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from fpdf import FPDF
from fpdf.fonts import FontFace

from .analysis import approved_analysis, attested_streams, load_draft
from .analysis.rules import baseline_status
from .config import Settings
from .controls import CONTROLS, STREAMS, STREAMS_BY_ID
from .vault import Vault

DISCLAIMER = ("Prototype output. This pack evidences that controls operated; it does not certify DISP compliance and does "
              "not replace the Security Officer's judgement or a Defence assessment.")


# ------------------------------------------------------------------ data
def control_statuses(settings: Settings, vault: Vault, period: str) -> dict[str, str]:
    """Status of each control as at the period's own evidence cut-off."""
    sums = vault.summaries(period)
    ref = datetime.fromisoformat(vault.manifest(period)["as_of"]).date()
    return {c.control_id: baseline_status(sums.get(c.stream), c.control_id, ref, settings.policy.evidence_stale_days)
            for c in CONTROLS}


def monthly_pack(settings: Settings, vault: Vault, period: str) -> dict[str, Any]:
    pdir = vault.period_dir(period)
    approved = approved_analysis(vault, period)
    draft = load_draft(settings, period)
    sums = vault.summaries(period)
    return {
        "pack": "DISP monthly evidence pack",
        "tenant": vault.manifest(period)["tenant"],
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": vault.manifest(period),
        "manifest_sha256": vault.manifest_sha256(period),
        "manifest_signature_b64": (pdir / "manifest.sig").read_text(),
        "verification": vault.verify(period).__dict__,
        "control_status_baseline": control_statuses(settings, vault, period),
        "attestations": [a["payload"] | {"seq": a["seq"]} for a in vault.addenda(period, "attestation")],
        "analysis": {"approved": approved["payload"] if approved else None,
                     "latest_draft": draft, "status": "APPROVED BY SO" if approved else "DRAFT - PENDING SO REVIEW"},
        "streams": sums,
        "disclaimer": DISCLAIMER,
    }


def asr_pack(settings: Settings, vault: Vault, periods: list[str] | None = None) -> dict[str, Any]:
    periods = periods or vault.periods()[-12:]
    statuses = {p: control_statuses(settings, vault, p) for p in periods}
    sev_by_month: dict[str, Counter] = {}
    persistent: Counter = Counter()
    trends: dict[str, list] = defaultdict(list)
    personnel = Counter()
    incidents, attest = [], []
    for p in periods:
        sums = vault.summaries(p)
        sev_by_month[p] = Counter(e["severity"] for s in sums.values() for e in s["exceptions"])
        for s in sums.values():
            for e in s["exceptions"]:
                if e["severity"] in ("critical", "high"):
                    persistent[(e["stream"], e["title"], e["subject"])] += 1
        m = {k: s["metrics"] for k, s in sums.items()}
        trends["mfa_coverage_pct"].append(m.get("mfa", {}).get("mfa_coverage_pct"))
        trends["device_compliance_pct"].append(m.get("patch", {}).get("device_compliance_pct"))
        trends["patch_on_time_pct"].append(m.get("patch", {}).get("remediated_on_time_pct"))
        trends["training_coverage_pct"].append(m.get("training", {}).get("coverage_pct"))
        for k in ("joiners", "movers", "leavers", "late_removals"):
            personnel[k] += m.get("jml", {}).get(k, 0)
        if "incidents" in sums:
            incidents.extend(vault.records(p, "incidents"))
        need = {s.stream_id for s in STREAMS if s.requires_attestation}
        done = attested_streams(vault, p)
        attest.append({"period": p, "required": sorted(need), "attested": sorted(done & need), "missing": sorted(need - done)})
    latest = periods[-1]
    lm = vault.summaries(latest)
    return {
        "pack": "ASR data pack (inputs for the Annual Security Report)",
        "tenant": vault.manifest(latest)["tenant"],
        "reporting_periods": periods,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "control_status_by_month": statuses,
        "exceptions_by_month": {p: dict(c) for p, c in sev_by_month.items()},
        "persistent_critical_high": [{"stream": s, "title": t, "subject": subj, "months": n}
                                     for (s, t, subj), n in persistent.most_common() if n >= 3],
        "trends": dict(trends),
        "personnel_changes": dict(personnel) | {"leavers_still_enabled_at_latest": lm.get("jml", {}).get("metrics", {}).get("leavers_still_enabled", 0)},
        "incidents": incidents,
        "attestations": attest,
        "integrity": {p: vault.verify(p).ok for p in periods},
        "notes": ["The Security Officer completes and submits the ASR in the DISP Member Portal; this pack supplies the evidence.",
                  "Verify current ASR questions against Defence's DISP guidance before use."],
        "disclaimer": DISCLAIMER,
    }


# ------------------------------------------------------------------ PDF
def _t(s: Any) -> str:
    """fpdf core fonts are latin-1 only."""
    text = str(s).replace("—", "-").replace("–", "-").replace("’", "'").replace("≤", "<=").replace("≥", ">=")
    return text.encode("latin-1", "replace").decode("latin-1")


class _PDF(FPDF):
    def __init__(self, title: str):
        super().__init__(format="A4")
        self.doc_title = title
        self.set_auto_page_break(True, margin=16)
        self.set_margins(14, 14, 14)

    def header(self) -> None:
        self.set_font("Helvetica", "", 8)
        self.set_text_color(110)
        self.cell(0, 5, _t(self.doc_title), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(130)
        self.cell(0, 5, _t(f"{DISCLAIMER}  |  Page {self.page_no()}"), align="C")

    def h1(self, s: str) -> None:
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(20)
        self.multi_cell(0, 8, _t(s), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def h2(self, s: str) -> None:
        self.ln(2)
        self.set_font("Helvetica", "B", 11.5)
        self.set_text_color(20)
        self.multi_cell(0, 6, _t(s), new_x="LMARGIN", new_y="NEXT")

    def p(self, s: str, size: float = 9, color: int = 40) -> None:
        self.set_font("Helvetica", "", size)
        self.set_text_color(color)
        self.multi_cell(0, 4.6, _t(s), new_x="LMARGIN", new_y="NEXT")

    def kv(self, rows: list[tuple[str, Any]]) -> None:
        for k, v in rows:
            self.set_font("Helvetica", "B", 8.5)
            self.set_text_color(60)
            self.cell(48, 4.8, _t(k))
            self.set_font("Courier" if isinstance(v, str) and len(v) >= 32 and " " not in v else "Helvetica", "", 8.5)
            self.set_text_color(20)
            self.multi_cell(0, 4.8, _t(v), new_x="LMARGIN", new_y="NEXT")

    def table(self, headers: list[str], rows: list[list[Any]], widths: list[float]) -> None:
        self.set_font("Helvetica", "", 7.8)
        with super().table(col_widths=widths, text_align="LEFT", line_height=4.2, first_row_as_headings=True,
                           headings_style=FontFace(emphasis="BOLD", fill_color=(236, 236, 230))) as tbl:
            r = tbl.row()
            for h in headers:
                r.cell(_t(h))
            for row in rows:
                r = tbl.row()
                for c in row:
                    r.cell(_t(c))


SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def monthly_pdf(pack: dict[str, Any]) -> bytes:
    period = pack["period"]
    pdf = _PDF(f"DISP monthly evidence pack - {pack['tenant']} - {period}")
    pdf.add_page()
    pdf.h1(f"Monthly evidence pack: {period}")
    m = pack["manifest"]
    ver = pack["verification"]
    pdf.kv([("Organisation", pack["tenant"]), ("Evidence cut-off", m["as_of"]), ("Sealed at", m["sealed_at"]),
            ("Retain until (WORM)", m["retain_until"]), ("Manifest SHA-256", pack["manifest_sha256"]),
            ("Signing key id", m["key_id"]), ("Chained to", f"{m['prev_period']}  {m['prev_manifest_sha256'] or ''}" if m["prev_period"] else "genesis period"),
            ("Integrity check", "PASSED - all checks" if ver["ok"] else "FAILED - see integrity section"),
            ("Analysis status", pack["analysis"]["status"])])

    pdf.h2("Control status (deterministic baseline from collected exceptions)")
    approved = (pack["analysis"]["approved"] or {}).get("draft") if pack["analysis"]["approved"] else None
    approved_map = {a["control_id"]: a for a in (approved or {}).get("assessments", [])}
    rows = []
    for c in CONTROLS:
        a = approved_map.get(c.control_id)
        rows.append([c.control_id, c.name, pack["control_status_baseline"][c.control_id], (a or {}).get("status", "-"),
                     ((a or {}).get("recommended_action") or "")[:90]])
    pdf.table(["Control", "Name", "Baseline", "SO-approved", "Action"], rows, [34, 40, 20, 22, 66])

    pdf.h2("Security Officer attestations")
    if pack["attestations"]:
        pdf.table(["Stream", "Decision", "Signed by", "Signed at", "Comment"],
                  [[STREAMS_BY_ID.get(a["subject"]).name if a["subject"] in STREAMS_BY_ID else a["subject"], a["decision"],
                    a["signed_by"], a["signed_at"][:16], a.get("comment", "")[:60]] for a in pack["attestations"]], [40, 30, 30, 28, 54])
    else:
        pdf.p("No attestations recorded yet for this period.")

    for s in STREAMS:
        sm = pack["streams"].get(s.stream_id)
        if not sm:
            continue
        pdf.add_page()
        pdf.h1(f"{s.number}. {s.name}  [{sm['status']}]")
        pdf.p(sm["headline"], 10, 30)
        pdf.p("Sources: " + ", ".join(sm["sources"]), 8, 100)
        pdf.h2("Metrics")
        pdf.kv([(k.replace("_", " "), v if not isinstance(v, dict) else ", ".join(f"{a}: {b}" for a, b in v.items()))
                for k, v in sm["metrics"].items()])
        ex = sorted(sm["exceptions"], key=lambda e: SEV_ORDER[e["severity"]])
        pdf.h2(f"Exceptions ({len(ex)})")
        if ex:
            pdf.table(["Severity", "Control", "Exception", "Subject", "Detail"],
                      [[e["severity"].upper(), e["control_id"], e["title"], e["subject"][:40], e["detail"][:110]] for e in ex[:30]],
                      [17, 30, 38, 40, 57])
            if len(ex) > 30:
                pdf.p(f"... {len(ex) - 30} more in summary.json")
        else:
            pdf.p("No exceptions.")

    pdf.add_page()
    pdf.h1("Integrity verification")
    pdf.table(["Check", "Result", "Detail"], [[c["check"], "PASS" if c["ok"] else "FAIL", c["detail"][:120]] for c in ver["checks"]], [55, 14, 113])
    pdf.h2("Sealed artifacts")
    pdf.table(["Artifact id", "SHA-256", "Bytes"], [[a["artifact_id"], a["sha256"], a["bytes"]] for a in m["artifacts"]], [56, 112, 14])
    return bytes(pdf.output())


def asr_pdf(asr: dict[str, Any]) -> bytes:
    periods = asr["reporting_periods"]
    pdf = _PDF(f"ASR data pack - {asr['tenant']}")
    pdf.add_page()
    pdf.h1(f"ASR data pack: {periods[0]} to {periods[-1]}")
    for n in asr["notes"]:
        pdf.p("- " + n)
    pdf.h2("Control status by month")
    short = [p[2:] for p in periods]
    w = (182 - 44) / max(1, len(periods))
    pdf.table(["Control"] + short, [[c.control_id] + [asr["control_status_by_month"][p][c.control_id] for p in periods] for c in CONTROLS],
              [44] + [w] * len(periods))
    pdf.h2("Trends")
    pdf.table(["Measure"] + short, [[k.replace("_", " ")] + [("-" if v is None else v) for v in vals] for k, vals in asr["trends"].items()],
              [44] + [w] * len(periods))
    pdf.h2("Exceptions raised by severity")
    pdf.table(["Severity"] + short, [[s] + [asr["exceptions_by_month"][p].get(s, 0) for p in periods] for s in SEV_ORDER],
              [44] + [w] * len(periods))
    pdf.h2("Personnel changes")
    pdf.kv([(k.replace("_", " "), v) for k, v in asr["personnel_changes"].items()])
    pdf.h2("Security incidents")
    if asr["incidents"]:
        pdf.table(["Id", "Date", "Category", "Reportable", "Reported", "Summary"],
                  [[i["id"], i["date"], i["category"], i["reportable"], i["reported_on"], i["summary"]] for i in asr["incidents"]],
                  [22, 18, 34, 18, 18, 72])
    else:
        pdf.p("No incidents logged.")
    pdf.h2("Persistent critical/high findings (3+ months)")
    if asr["persistent_critical_high"]:
        pdf.table(["Stream", "Finding", "Subject", "Months"], [[x["stream"], x["title"], x["subject"][:50], x["months"]] for x in asr["persistent_critical_high"]],
                  [24, 60, 84, 14])
    else:
        pdf.p("None.")
    pdf.h2("Attestations and integrity")
    pdf.table(["Period", "Attested", "Missing", "Vault integrity"],
              [[a["period"], ", ".join(a["attested"]) or "-", ", ".join(a["missing"]) or "-", "OK" if asr["integrity"][a["period"]] else "FAILED"]
               for a in asr["attestations"]], [24, 60, 60, 38])
    return bytes(pdf.output())


__all__ = ["monthly_pack", "monthly_pdf", "asr_pack", "asr_pdf", "control_statuses"]
