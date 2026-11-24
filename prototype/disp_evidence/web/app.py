"""Local web UI (stands in for the Power BI dashboard, Teams approval cards and
the evidence-pack download a Security Officer would get in production)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..analysis import approved_analysis, attested_streams, engine_status, load_draft, run_analysis
from ..cli import sign_off
from ..config import get_settings
from ..connectors import PERMISSION_MAP
from ..controls import CONTROLS, CONTROLS_BY_ID, STREAMS, STREAMS_BY_ID
from ..pipeline import current_period, cutoff_for, run_cycle
from ..reports import asr_pack, asr_pdf, control_statuses, monthly_pack, monthly_pdf
from ..simulator import get_tenant
from ..vault import Vault, VaultError

HERE = Path(__file__).resolve().parent
app = FastAPI(title="DISP Evidence Plumbing - prototype")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")

SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
STATUS_ICON = {"PASS": "✓", "WARN": "!", "FAIL": "✕", "COMPLIANT": "✓", "PARTIAL": "!", "GAP": "✕", "STALE": "?"}
TREND_METRICS = [("mfa", "mfa_coverage_pct", "MFA coverage (% of staff)"),
                 ("patch", "device_compliance_pct", "Device patch compliance (%)"),
                 ("patch", "remediated_on_time_pct", "Patches remediated within E8 window (%)"),
                 ("training", "coverage_pct", "Security training current (%)")]


def ctx() -> tuple:
    settings = get_settings()
    return settings, Vault(settings)


def render(request: Request, name: str, **kw):
    settings = get_settings()
    tenant = get_tenant(settings.tenant_seed)
    base = {"request": request, "tenant_name": tenant.name, "so_name": tenant.security_officer.name, "today": settings.today(),
            "icon": STATUS_ICON, "streams": STREAMS, "streams_by_id": STREAMS_BY_ID, "controls": CONTROLS,
            "controls_by_id": CONTROLS_BY_ID, "msg": request.query_params.get("msg"), "err": request.query_params.get("err")}
    return templates.TemplateResponse(request, name, base | kw)


def redirect(url: str, msg: str = "", err: str = "") -> RedirectResponse:
    q = f"?msg={quote(msg)}" if msg else (f"?err={quote(err)}" if err else "")
    return RedirectResponse(url + q, status_code=303)


def need_period(vault: Vault, period: str) -> None:
    if not vault.is_sealed(period):
        raise HTTPException(404, f"No sealed evidence for {period}")


def line_chart(values: list[float | None], labels: list[str], lo: float = 50, hi: float = 100) -> dict:
    """Pre-compute SVG geometry for a single-series line chart."""
    w, h, pl, pr, pt, pb = 320, 150, 34, 10, 12, 24
    pts = []
    n = max(1, len(values) - 1)
    for i, v in enumerate(values):
        if v is None:
            continue
        x = pl + (w - pl - pr) * i / n
        y = pt + (h - pt - pb) * (1 - (max(lo, min(hi, v)) - lo) / (hi - lo))
        pts.append({"x": round(x, 1), "y": round(y, 1), "v": v, "label": labels[i]})
    ticks = [{"v": t, "y": round(pt + (h - pt - pb) * (1 - (t - lo) / (hi - lo)), 1)} for t in (lo, (lo + hi) / 2, hi)]
    return {"w": w, "h": h, "pl": pl, "pr": pr, "pt": pt, "pb": pb, "points": pts, "ticks": ticks,
            "path": " ".join(("M" if i == 0 else "L") + f"{p['x']},{p['y']}" for i, p in enumerate(pts)),
            "last": pts[-1] if pts else None}


# ----------------------------------------------------------------------------- pages
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    settings, vault = ctx()
    periods = vault.periods()
    if not periods:
        return render(request, "empty.html")
    grid = {p: vault.summaries(p) for p in periods}
    latest = periods[-1]
    lsum = grid[latest]
    open_ex = [e for s in lsum.values() for e in s["exceptions"] if e["severity"] in ("critical", "high")]
    pending = sum(1 for p in periods for s in STREAMS if s.requires_attestation and s.stream_id not in attested_streams(vault, p))
    integrity = {p: vault.verify(p).ok for p in periods}
    statuses = control_statuses(settings, vault, latest)
    charts = []
    for stream, key, title in TREND_METRICS:
        vals = [grid[p].get(stream, {}).get("metrics", {}).get(key) for p in periods]
        charts.append({"title": title, "chart": line_chart(vals, periods), "latest": vals[-1]})
    cur = current_period(settings)
    as_of_latest = datetime.fromisoformat(vault.manifest(latest)["as_of"])
    age_days = (datetime.now(timezone.utc) - as_of_latest).days if not settings.today_override else (settings.today() - as_of_latest.date()).days
    return render(request, "dashboard.html", periods=periods, grid=grid, latest=latest, open_ex=sorted(open_ex, key=lambda e: SEV_ORDER[e["severity"]]),
                  pending=pending, integrity=integrity, statuses=statuses, charts=charts, current=cur,
                  current_sealed=vault.is_sealed(cur), current_cutoff=cutoff_for(settings, cur), age_days=age_days,
                  gaps=sum(1 for v in statuses.values() if v == "GAP"))


@app.post("/run")
def run_now():
    settings, vault = ctx()
    period = current_period(settings)
    try:
        m = run_cycle(settings, period, vault)
    except VaultError as e:
        return redirect("/", err=str(e))
    return redirect(f"/month/{period}", msg=f"Monthly cycle ran: {len(m['artifacts'])} artifacts collected, hashed, signed and chained to {m['prev_period']}.")


@app.get("/month/{period}", response_class=HTMLResponse)
def month(request: Request, period: str):
    settings, vault = ctx()
    need_period(vault, period)
    sums = vault.summaries(period)
    attest = {a["payload"]["subject"]: a for a in vault.addenda(period, "attestation")}
    sev = {k: {s: sum(1 for e in v["exceptions"] if e["severity"] == s) for s in SEV_ORDER} for k, v in sums.items()}
    return render(request, "month.html", period=period, sums=sums, sev=sev, attest=attest, manifest=vault.manifest(period),
                  manifest_sha=vault.manifest_sha256(period), verify=vault.verify(period), approved=approved_analysis(vault, period),
                  statuses=control_statuses(settings, vault, period), periods=vault.periods())


@app.get("/month/{period}/stream/{stream}", response_class=HTMLResponse)
def stream_page(request: Request, period: str, stream: str):
    settings, vault = ctx()
    need_period(vault, period)
    if stream not in STREAMS_BY_ID:
        raise HTTPException(404)
    s = vault.summary(period, stream)
    records = vault.records(period, stream)
    arts = [a for a in vault.manifest(period)["artifacts"] if a["stream"] == stream]
    attest = [a for a in vault.addenda(period, "attestation") if a["payload"]["subject"] == stream]
    return render(request, "stream.html", period=period, stream=STREAMS_BY_ID[stream], s=s, records=records[:400], total_records=len(records),
                  exceptions=sorted(s["exceptions"], key=lambda e: SEV_ORDER[e["severity"]]), artifacts=arts, attest=attest)


@app.post("/month/{period}/stream/{stream}/attest")
def attest(period: str, stream: str, decision: str = Form(...), comment: str = Form("")):
    settings, vault = ctx()
    need_period(vault, period)
    if decision not in ("approved", "approved_with_comments", "rejected"):
        raise HTTPException(400)
    if decision != "approved" and not comment.strip():
        return redirect(f"/month/{period}/stream/{stream}", err="A comment is required when approving with comments or rejecting.")
    body = sign_off(settings, vault, period, stream, decision, comment.strip())
    return redirect(f"/month/{period}/stream/{stream}",
                    msg=f"Attestation #{body['seq']} sealed: signed, bound to manifest {body['manifest_sha256'][:12]}..., appended to the vault.")


@app.get("/month/{period}/analysis", response_class=HTMLResponse)
def analysis_page(request: Request, period: str):
    settings, vault = ctx()
    need_period(vault, period)
    return render(request, "analysis.html", period=period, draft=load_draft(settings, period), approved=approved_analysis(vault, period),
                  engines=engine_status(), statuses=control_statuses(settings, vault, period))


@app.post("/month/{period}/analysis/run")
def analysis_run(period: str, engine: str = Form("rules")):
    settings, vault = ctx()
    need_period(vault, period)
    try:
        draft, gate = run_analysis(settings, vault, period, engine)
    except Exception as e:  # engine unavailable / model error -> show it, don't crash the demo
        return redirect(f"/month/{period}/analysis", err=f"{engine}: {e}")
    return redirect(f"/month/{period}/analysis", msg=f"Draft produced by {draft.engine}; gate {'PASSED' if gate.passed else 'FAILED'}.")


@app.post("/month/{period}/analysis/approve")
def analysis_approve(period: str, comment: str = Form("")):
    settings, vault = ctx()
    saved = load_draft(settings, period)
    if not saved:
        return redirect(f"/month/{period}/analysis", err="Run an analysis first.")
    if not saved["gate"]["passed"]:
        return redirect(f"/month/{period}/analysis", err="The gate failed; this draft cannot be approved.")
    so = get_tenant(settings.tenant_seed).security_officer
    body = vault.add_addendum(period, "approved_analysis", {"draft": saved["draft"], "gate": saved["gate"], "approved_by": so.name, "comment": comment})
    return redirect(f"/month/{period}/analysis", msg=f"Analysis approved by {so.name} and sealed as addendum #{body['seq']}.")


@app.get("/vault", response_class=HTMLResponse)
def vault_page(request: Request):
    settings, vault = ctx()
    rows = []
    for p in reversed(vault.periods()):
        m = vault.manifest(p)
        rows.append({"period": p, "m": m, "sha": vault.manifest_sha256(p), "verify": vault.verify(p), "addenda": vault.addenda(p)})
    return render(request, "vault.html", rows=rows, tampered=vault.tampered(), key_id=vault.signer.key_id,
                  vault_dir=str(settings.vault_dir))


@app.post("/vault/tamper")
def tamper(period: str = Form(...), stream: str = Form(...)):
    _, vault = ctx()
    need_period(vault, period)
    what = vault.tamper(period, stream)
    return redirect("/vault", msg=f"Simulated insider edit: {what}. Now look at the integrity column.")


@app.post("/vault/untamper")
def untamper(period: str = Form(...), stream: str = Form(...)):
    _, vault = ctx()
    vault.untamper(period, stream)
    return redirect("/vault", msg=f"Restored original {period}/{stream}/records.csv (demo reset).")


@app.get("/artifact")
def artifact(id: str):
    _, vault = ctx()
    try:
        path = vault.artifact_path(id)
    except VaultError:
        raise HTTPException(400)
    if not path.exists():
        raise HTTPException(404)
    media = "application/json" if path.suffix == ".json" else "text/plain; charset=utf-8"
    return FileResponse(path, media_type=media)


@app.get("/pack/{period}.pdf")
def pack_pdf(period: str):
    settings, vault = ctx()
    need_period(vault, period)
    return Response(monthly_pdf(monthly_pack(settings, vault, period)), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="evidence-pack-{period}.pdf"'})


@app.get("/pack/{period}.json")
def pack_json(period: str):
    settings, vault = ctx()
    need_period(vault, period)
    return JSONResponse(json.loads(json.dumps(monthly_pack(settings, vault, period), default=str)))


@app.get("/asr", response_class=HTMLResponse)
def asr_page(request: Request):
    settings, vault = ctx()
    if not vault.periods():
        return redirect("/")
    return render(request, "asr.html", asr=asr_pack(settings, vault))


@app.get("/asr.pdf")
def asr_download():
    settings, vault = ctx()
    return Response(asr_pdf(asr_pack(settings, vault)), media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="asr-data-pack.pdf"'})


@app.get("/asr.json")
def asr_json():
    settings, vault = ctx()
    return JSONResponse(json.loads(json.dumps(asr_pack(settings, vault), default=str)))


@app.get("/connectors", response_class=HTMLResponse)
def connectors(request: Request):
    import os

    return render(request, "connectors.html", permissions=PERMISSION_MAP, engines=engine_status(),
                  mode=os.environ.get("DISP_CONNECTOR", "simulated"))


@app.get("/about", response_class=HTMLResponse)
def about(request: Request):
    return render(request, "about.html")
