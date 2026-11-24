# Decision Log

Append-only. Newest entries at the bottom. One entry per decision that
has lasting consequences for the architecture, process, or guardrails —
not a log of every action taken.

Format:

```
## YYYY-MM-DD — <short title>
**Decided by:** <role/agent or human>
**Context:** why this came up
**Decision:** what was decided
**Alternatives considered:** what else was on the table and why it lost
```

---

## 2026-08-07 — Bootstrap the agentic-workflow framework itself
**Decided by:** architect (bootstrap session)
**Context:** Empty repo needed a production-ready agentic framework:
modular skills, persistent agents, a file-backed squad-coordination
layer, and Copilot CLI fleet integration for parallel execution.
**Decision:** Adopted a supervisor/worker coordination model using
plain markdown + shell as the persistence and orchestration substrate
(`.squad/`, `bin/`) rather than a database or bespoke service — the
whole framework needs to be inspectable and editable by both humans and
agents with nothing more than a text editor and git.
**Alternatives considered:** A JSON/SQLite-backed task queue was
considered for stronger structure, but rejected for this bootstrap: it
adds a dependency and a serialization layer for a problem markdown
files solve well at this scale, and file-based state diffs cleanly in
git review. Revisit if task volume outgrows what's comfortable to scan
by hand.

## 2026-11-24 — Repo adopts agentic-workflow scaffold; evidence-plumbing prototype added
**Decided by:** human (Andre) + Claude Code session
**Context:** Two business cases (BC1 Microsoft-native managed pipeline; BC2 AI/agent-SDK pipeline) needed a demoable prototype that costs nothing to run on a laptop.
**Decision:** Copied the agentic-workflow scaffold into this repo; moved the earlier Aegis-Bridge SPEC/PLAN/TASKS to `docs/aegis-bridge/`; built `prototype/` (Python, FastAPI) against a deterministic simulated M365 tenant behind a `Connector` interface.
**Alternatives considered:** A real M365 developer tenant (free sandboxes now restricted to some Visual Studio/partner programs); deploying to Azure (costs money, outside the $0 demo constraint).

## 2026-11-24 — Deterministic first, agent second, gate always
**Decided by:** human (Andre) + Claude Code session
**Context:** BC2 puts an LLM at the centre; BC1 promises client data never leaves the tenant.
**Decision:** Collectors and sealing are fully deterministic. Analysis engines (rules default; Ollama local; Claude paid opt-in via `DISP_ENABLE_PAID_LLM=1`) see only a minimised digest without personal identifiers. Every draft passes a deterministic gate (no invented citations, no uncited positive claims, no rating above the rules baseline), and only the Security Officer can approve.
**Alternatives considered:** LLM-first mapping per BC2 (rejected: residency/APP 8 risk and unverifiable claims); no AI at all (kept as the default engine, but the pluggable layer lets the BC2 story be demoed for $0 via Ollama).

## 2026-11-24 — Local WORM emulation with signed, hash-chained manifests
**Decided by:** human (Andre) + Claude Code session
**Context:** The pitch rests on the claim that evidence cannot be fixed later. That has to be demonstrable without Azure.
**Decision:** Exclusive-create read-only files, in-order sealing, SHA-256 manifest per month signed with Ed25519 (Key Vault stand-in), each manifest chaining the previous month's hash, and post-seal sign-offs appended as signed addenda bound to the manifest. Verification runs on every page load; the tamper demo edits a sealed file to show detection.
**Alternatives considered:** Azurite (Azure Storage emulator) does not enforce immutability policies, so it adds a dependency without making the demo more faithful.
