# DISP Continuous Evidence Plumbing — local prototype

A working, laptop-only demo of the managed evidence pipeline described in
[`docs/business-case-review.md`](../docs/business-case-review.md). It runs for
**$0**: no cloud, no Microsoft 365 tenant, no API keys.

```
collect (7 streams) → seal (WORM + SHA-256 manifest + signature + hash chain)
   → analyse (rules / optional LLM, citation + over-claim gate)
   → Security Officer sign-off → monthly evidence pack + ASR data pack
```

## Run the demo

Requires Python 3.11+.

```powershell
# Windows
cd prototype
.\scripts\start-demo.ps1          # first run: creates .venv, installs, seeds May–Oct 2026, opens the browser
.\scripts\start-demo.ps1 -Reset   # wipe and re-seed
```

```bash
# macOS / Linux / Git Bash
cd prototype && scripts/start-demo.sh        # add --reset to re-seed
```

Then open <http://127.0.0.1:8000>.

`demo-setup` seals every closed month from May 2026 up to last month. All but the
latest month are pre-signed by the (fictional) Security Officer, so the latest
month is left for you to sign off live.

## 5-minute talk track

1. **Dashboard.** Seven evidence streams × six months, with a status for each cell. Hover a cell for its headline, click it for the evidence.
2. **Latest month → Joiner/mover/leaver.** A leaver's account was never
   disabled (critical, carried every month). A contractor account has no HR
   record, and a mover kept access to the Defence project group. Sign off in the
   Teams-style card. The decision is signed, bound to the month's manifest and
   appended to the vault.
3. **Control analysis.** Draft with the rules engine. The gate checks every
   citation exists and that no control is rated above what the evidence
   supports. Approve as the Security Officer, and the approval is sealed. Then pick the
   **faulty-llm-demo** engine ($0). It imitates a hallucinating model that invents a
   policy PDF and rates a GAP control as COMPLIANT. The gate blocks it and the
   Approve button is disabled.
4. **Evidence pack (PDF).** It shows the manifest hash, signing key, chain link
   to the previous month, a live integrity check, controls, exceptions and every
   artifact hash.
5. **Evidence vault → Tamper.** Edit a sealed JML file "behind the vault's back".
   Integrity flips to ✕ FAILED with the exact file named. Restore it.
6. **Run this month's cycle now.** November is collected as of today, then hashed,
   signed and chained in about a second.
7. **ASR data pack.** The year's roll-up: control status by month, trends,
   personnel changes, incidents and persistent findings.

## CLI

```bash
python -m disp_evidence demo-setup            # reset + backfill with sign-offs
python -m disp_evidence run [--period YYYY-MM] # collect + seal one month (default: current, as of now)
python -m disp_evidence verify [all|YYYY-MM]  # re-check hashes, signatures, chain, addenda (exit 1 on failure)
python -m disp_evidence analyse 2026-10 --engine rules|faulty-llm-demo|ollama|claude
python -m disp_evidence pack 2026-10          # var/packs/evidence-pack-2026-10.pdf + .json
python -m disp_evidence asr                   # var/packs/asr-data-pack.pdf + .json
python -m disp_evidence tamper 2026-08 jml    # demo only; `untamper` restores
python -m disp_evidence serve --port 8000
python -m disp_evidence reset --yes
```

## What is real and what is simulated

| Part | Status |
|---|---|
| Collectors (7 streams), E8 ML2 patch windows, JML reconciliation, MFA/CA posture, training, visitors, incidents | **Real logic**, run against simulated data |
| Simulated tenant | Fictional WA fabrication SME ("Banksia Marine", `.example` domain). A deterministic 2026 timeline with seeded failures: late/never leaver removal, account without HR record, mover keeping restricted access, stale admin, Global Admin spike, Windows 10 devices, an exploited VPN fix applied late, MFA gaps, legacy auth in report-only, overdue training, visitor and escort gaps |
| Immutable store | **Real** local implementation: exclusive-create, read-only files, ordered sealing, SHA-256 manifest, Ed25519 signature, monthly hash chain, signed append-only addenda |
| Analysis gate | **Real**: rejects invented citations, uncited positive claims and over-claims against the deterministic baseline |
| Microsoft Graph connector | Written (`connectors/graph.py`, client-credentials, read-only) but **not yet run against a real tenant** |
| Ollama engine | Real code. Needs Ollama installed and `ollama pull llama3.2` (free, ~2 GB). Not exercised in CI |
| Claude engine | Real code using the Anthropic SDK. **Paid, off by default**: needs `pip install -e .[claude]`, `DISP_ENABLE_PAID_LLM=1` and Anthropic credentials. Default model `claude-opus-5-5` with server-side refusal fallback. Sends only the minimised digest (no names or UPNs). Not exercised in CI |
| Power BI / Teams / Planner | Stood in for by the local web UI |

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `DISP_DATA_DIR` | `prototype/var` | Vault, keys, drafts, packs |
| `DISP_TODAY` | real date | Pin "today" (YYYY-MM-DD) for a reproducible demo |
| `DISP_TENANT_SEED` | `2026` | Simulated tenant seed |
| `DISP_CONNECTOR` | `simulated` | `graph` to use the Graph connector (`DISP_GRAPH_TENANT_ID`, `DISP_GRAPH_CLIENT_ID`, `DISP_GRAPH_CLIENT_SECRET`, `DISP_DROP_DIR`, `DISP_PRIVILEGED_GROUPS`) |
| `DISP_OLLAMA_MODEL` / `DISP_OLLAMA_URL` | `llama3.2` / `http://localhost:11434` | Local LLM |
| `DISP_ENABLE_PAID_LLM`, `DISP_CLAUDE_MODEL` | off / `claude-opus-5-5` | Paid hosted LLM opt-in |

Policy thresholds (patch windows, 45-day privileged inactivity, 24 h leaver
removal and so on) are in `disp_evidence/config.py`. They are **policy parameters to verify
against the current Essential Eight Maturity Model**, not legal statements.

## Tests

```bash
.venv/Scripts/python -m pytest -q     # Windows (bin/python elsewhere)
```

There are 27 tests: vault immutability, tamper and chain detection, signed addenda, the gate (fabricated
citation, over-claim, uncited claim, faulty-LLM demo blocked), one test per seeded control failure, and an
end-to-end web flow (sign-off → analysis → approve → packs → tamper → live cycle).

## Layout

```
disp_evidence/
  simulator.py        fictional tenant timeline (Graph-shaped outputs)
  connectors/         Connector protocol, simulated, Graph; published permission map
  collectors/         one module per evidence stream (deterministic, no LLM)
  vault.py, keys.py   WORM store, manifest, signature, chain, addenda, verify, tamper demo
  analysis/           rules engine, Ollama/Claude engines, citation + over-claim gate
  reports.py          monthly evidence pack and ASR data pack (JSON + PDF)
  pipeline.py, cli.py orchestration + CLI
  web/                FastAPI + Jinja UI (dashboard, vault, sign-off, analysis, packs)
```
