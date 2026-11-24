# aukus

Compliance tooling for WA SMEs in AUKUS / defence supply chains.

## What's here

| Path | What it is |
|---|---|
| [`prototype/`](prototype/README.md) | **DISP Continuous Evidence Plumbing**: a working local demo of the managed evidence pipeline (collect → seal → analyse → SO sign-off → evidence pack / ASR data pack). Runs on a laptop for $0. |
| [`docs/business-case-review.md`](docs/business-case-review.md) | Review of the two evidence-plumbing business cases: where they agree and conflict, fixes needed, and how the prototype resolves each point. |
| [`docs/aegis-bridge/`](docs/aegis-bridge/) | Earlier "Aegis-Bridge" plan (Obsidian-based gap-analysis advisory), kept for reference. |
| `.claude/`, `.squad/`, `bin/`, `.githooks/`, `AGENTS.md` | Agentic-workflow scaffold (from [andrefabre/agentic-workflow](https://github.com/andrefabre/agentic-workflow)): skills, personas, squad task queue, git guardrails. |

## Quick start

```powershell
cd prototype
.\scripts\start-demo.ps1      # Windows; use scripts/start-demo.sh on macOS/Linux
```

Open <http://127.0.0.1:8000>. The talk track is in [`prototype/README.md`](prototype/README.md).

## Working in this repo

Read [`AGENTS.md`](AGENTS.md) first. One-time setup in a fresh clone enables the
git guardrails (no direct commits to `main`, no force-push):

```bash
bash scripts/install-aliases.sh   # or: git config core.hooksPath .githooks
```
