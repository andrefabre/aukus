"""Command line: python -m disp_evidence <command>."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
from datetime import datetime, timedelta, timezone

from .analysis import run_analysis
from .config import Settings, get_settings
from .controls import STREAMS
from .models import Attestation
from .pipeline import backfill, current_period, run_cycle
from .reports import asr_pack, asr_pdf, monthly_pack, monthly_pdf
from .simulator import get_tenant, month_bounds
from .vault import Vault


def _previous_period(period: str) -> str:
    y, m = (int(x) for x in period.split("-"))
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def reset(settings: Settings) -> None:
    def onerror(func, path, _exc):  # clear the WORM read-only bit (demo reset only)
        os.chmod(path, stat.S_IWRITE)
        func(path)

    if settings.data_dir.exists():
        shutil.rmtree(settings.data_dir, onerror=onerror)


def sign_off(settings: Settings, vault: Vault, period: str, stream: str, decision: str = "approved",
             comment: str = "", when: datetime | None = None) -> dict:
    so = get_tenant(settings.tenant_seed).security_officer
    att = Attestation(period=period, subject=stream, decision=decision, signed_by=so.name, comment=comment,  # type: ignore[arg-type]
                      signed_at=when or datetime.now(timezone.utc), manifest_sha256=vault.manifest_sha256(period))
    return vault.add_addendum(period, "attestation", att.model_dump(mode="json"))


def approve_analysis(settings: Settings, vault: Vault, period: str, engine: str = "rules", comment: str = "") -> dict:
    draft, gate = run_analysis(settings, vault, period, engine)
    if not gate.passed:
        raise SystemExit(f"Gate failed for {period}; cannot approve: {[f.message for f in gate.findings if f.level == 'error']}")
    so = get_tenant(settings.tenant_seed).security_officer
    return vault.add_addendum(period, "approved_analysis", {"draft": draft.model_dump(mode="json"), "gate": gate.model_dump(mode="json"),
                                                            "approved_by": so.name, "comment": comment})


def demo_setup(settings: Settings, first: str = "2026-05") -> list[str]:
    """Reset and backfill closed months; older months get SO sign-off so the demo starts realistic."""
    reset(settings)
    last = _previous_period(current_period(settings))
    done = backfill(settings, first, last)
    vault = Vault(settings)
    for p in done[:-1]:   # leave the most recent closed month for the live sign-off demo
        _, end = month_bounds(p)
        for s in STREAMS:
            if s.requires_attestation:
                sign_off(settings, vault, p, s.stream_id, "approved_with_comments",
                         "Reviewed in monthly security meeting; exceptions tracked in Planner.", end + timedelta(days=3))
        approve_analysis(settings, vault, p, "rules", "Accepted at monthly review.")
    return done


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="disp-evidence", description="DISP continuous evidence plumbing - local prototype")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo-setup", help="reset data and backfill May..last month with sign-offs")
    r = sub.add_parser("run", help="run the monthly cycle (collect + seal)")
    r.add_argument("--period", help="YYYY-MM (default: current month, as of now)")
    b = sub.add_parser("backfill")
    b.add_argument("first")
    b.add_argument("last")
    v = sub.add_parser("verify")
    v.add_argument("period", nargs="?", default="all")
    t = sub.add_parser("tamper", help="DEMO: edit sealed evidence behind the vault's back")
    t.add_argument("period")
    t.add_argument("stream", nargs="?", default="jml")
    u = sub.add_parser("untamper")
    u.add_argument("period")
    u.add_argument("stream", nargs="?", default="jml")
    a = sub.add_parser("analyse")
    a.add_argument("period")
    a.add_argument("--engine", default="rules", choices=["rules", "faulty-llm-demo", "ollama", "claude"])
    pk = sub.add_parser("pack", help="write monthly evidence pack (PDF + JSON)")
    pk.add_argument("period")
    sub.add_parser("asr", help="write ASR data pack (PDF + JSON)")
    sv = sub.add_parser("serve", help="start the local web app")
    sv.add_argument("--port", type=int, default=8000)
    sv.add_argument("--host", default="127.0.0.1")
    rs = sub.add_parser("reset", help="delete all local demo data")
    rs.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)
    settings = get_settings()

    if args.cmd == "demo-setup":
        done = demo_setup(settings)
        print(f"Sealed {len(done)} months: {', '.join(done)}. Latest closed month left for live sign-off.")
        print("Next: python -m disp_evidence serve   ->  http://127.0.0.1:8000")
    elif args.cmd == "run":
        m = run_cycle(settings, args.period or current_period(settings))
        print(f"Sealed {m['period']} as of {m['as_of']}: {len(m['artifacts'])} artifacts, chained to {m['prev_period']}")
    elif args.cmd == "backfill":
        print("Sealed:", ", ".join(backfill(settings, args.first, args.last)) or "nothing new")
    elif args.cmd == "verify":
        vault = Vault(settings)
        periods = vault.periods() if args.period == "all" else [args.period]
        bad = 0
        for p in periods:
            rep = vault.verify(p)
            bad += not rep.ok
            print(f"{p}: {'OK' if rep.ok else 'FAILED'}")
            for c in rep.checks:
                if not c["ok"]:
                    print(f"   x {c['check']}: {c['detail']}")
        return 1 if bad else 0
    elif args.cmd == "tamper":
        print(Vault(settings).tamper(args.period, args.stream))
    elif args.cmd == "untamper":
        print("restored" if Vault(settings).untamper(args.period, args.stream) else "nothing to restore")
    elif args.cmd == "analyse":
        draft, gate = run_analysis(settings, Vault(settings), args.period, args.engine)
        print(json.dumps({"engine": draft.engine, "gate_passed": gate.passed,
                          "assessments": {a.control_id: a.status for a in draft.assessments},
                          "gate_findings": [f.model_dump() for f in gate.findings]}, indent=1))
    elif args.cmd == "pack":
        vault = Vault(settings)
        pack = monthly_pack(settings, vault, args.period)
        settings.packs_dir.mkdir(parents=True, exist_ok=True)
        (settings.packs_dir / f"evidence-pack-{args.period}.json").write_text(json.dumps(pack, indent=1, default=str), encoding="utf-8")
        (settings.packs_dir / f"evidence-pack-{args.period}.pdf").write_bytes(monthly_pdf(pack))
        print(f"Wrote {settings.packs_dir / f'evidence-pack-{args.period}.pdf'} (+ .json)")
    elif args.cmd == "asr":
        vault = Vault(settings)
        asr = asr_pack(settings, vault)
        settings.packs_dir.mkdir(parents=True, exist_ok=True)
        (settings.packs_dir / "asr-data-pack.json").write_text(json.dumps(asr, indent=1, default=str), encoding="utf-8")
        (settings.packs_dir / "asr-data-pack.pdf").write_bytes(asr_pdf(asr))
        print(f"Wrote {settings.packs_dir / 'asr-data-pack.pdf'} (+ .json)")
    elif args.cmd == "serve":
        import uvicorn

        print(f"DISP evidence prototype on http://{args.host}:{args.port}  (Ctrl+C to stop)")
        uvicorn.run("disp_evidence.web.app:app", host=args.host, port=args.port, log_level="warning")
    elif args.cmd == "reset":
        if not args.yes:
            print("This deletes all local demo data under", settings.data_dir, "- re-run with --yes")
            return 1
        reset(settings)
        print("Deleted", settings.data_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
