# Review of the two DISP evidence-plumbing business cases

Sources reviewed (24 Nov 2026):

- **BC1**: *DISP Continuous Evidence Plumbing — Business Case (WA)*: a managed,
  Microsoft-native pipeline running in the client's tenant.
- **BC2**: *Business Case & Strategy: DISP & Industrial Compliance Evidence
  Plumbing*: an AI-assisted, SDK-driven pipeline with an agentic mapping layer.

This document covers what they agree on, where they conflict, the issues worth
fixing before anyone uses either externally, and how the local prototype
(`prototype/`) resolves each point.

## 1. Where they agree (the product core)

- **Buyer:** WA defence-supply-chain SMEs (about 15–200 staff) holding or seeking DISP
  Entry Level / Level 1, mostly on Microsoft 365, with no dedicated security team.
- **Pain:** evidence is collected as a scramble before ASRs and audits. Policies show
  intent, but operational evidence is what shows a control actually operated.
- **Product:** scheduled, read-only collectors → hashed, immutable, client-owned
  evidence store → monthly packs and ASR inputs → human (SO/CSO) sign-off.
- **Guardrails:** least-privilege read-only access, Australian data residency,
  no compliance certification claims, and the SO keeps accountability.

The prototype implements this shared core end to end.

## 2. Where they conflict, and the call the prototype makes

| Topic | BC1 | BC2 | Prototype decision |
|---|---|---|---|
| Where data lives | Entirely in the client tenant; "we hold no copy" | n8n on "dedicated Australian cloud/VPS" + hosted LLM routing | **BC1 wins.** A vendor-hosted orchestrator, or a hosted LLM fed raw evidence, breaks the main trust promise. The analysis layer sees only a **minimised digest** (metrics and exception titles, no names or UPNs). Hosted LLMs are opt-in, and local Ollama is the free in-tenant option |
| Role of AI | None; deterministic pipeline | Core: agent maps evidence to controls and drafts narratives | **Deterministic first, agent second, gate always.** Collectors never use an LLM. Any engine's draft goes through a deterministic gate (fabricated citations, uncited claims, over-claims against the rule baseline), and only the SO can approve |
| Pricing | Setup A$9.5k–18k + A$1.2k–2.5k/month | Audit A$3.5k–6k + build A$6k–14k + A$750–1,800/month | Not a prototype question, but the gap is about 40% on recurring revenue. Pick one for the discovery calls. BC2's lower retainer does not cover BC1's 4 h/client/month run cost at fully loaded rates |
| Scope of streams | 7 named streams; prototype = streams 1–3 | Broader (policies, risk register, backup status, screening records) | All 7 BC1 streams are built, with 1–3 marked "core". BC2's extra sources (policy docs, screening records) are a later phase |
| E8 ML2 premise | Flagged as **unverified** (top risk) | Stated as fact: "full E8 ML2 controls apply across DISP cyber assessments" | Treated as a **policy parameter**. All thresholds live in `config.py` and are labelled "verify against current E8 Maturity Model" |
| Orchestration | Azure Functions + Durable Functions | n8n or Power Automate | Azure Functions (BC1). Simpler to put in the client tenant |

## 3. Issues to fix in the documents

**BC1**

1. **The break-even claim only holds at 1 FTE.** "Recurring fees cover fixed running
   costs from about 9 clients" works for year 1 (A$190k cost ÷ A$22.8k per client per year ≈ 8.3).
   At the planned 2.5 FTE in year 3 (A$420k), recurring break-even is about **19 clients**.
   State the staffing level behind the "9 clients" figure.
2. **The arithmetic checks out:** setup revenue (8/10/7 × A$14k), recurring revenue (average
   clients × A$1.9k × 12), net (−32 / 101 / 168) and ARR at 25 clients (A$570k) all
   reconcile. The 70% gross margin is plausible but not shown. Add the delivery-hours
   build-up (4 h × 25 clients ≈ 0.6 FTE).
3. **Azure Lighthouse covers Azure resources, not Microsoft 365 / Graph data.**
   Lighthouse delegates the client's *Azure subscription* (the Function App and
   storage). Graph read access comes from the multi-tenant app registration's
   admin consent, or GDAP for partner-led access. The architecture is right, but the
   wording "Our team reaches the collectors only through … Lighthouse" should name both.
4. **Log Analytics is not free.** Keeping Entra sign-in and audit logs beyond 30 days
   costs ingestion and retention on the client's bill. Include it in the A$30–80/month estimate.
5. **The sign-in data needs Entra ID P1** (`signInActivity`, sign-in logs), which
   Business Premium includes. Say so next to the existing P2 / Access Reviews caveat.

**BC2**

1. **It contradicts its own residency guardrail.** The reference code uses
   `openai:gpt-4o-mini` and "LLM routing" while promising Australian-hosted
   storage. If any hosted model sees evidence, it is a cross-border disclosure
   (APP 8) unless the provider's region and terms are confirmed. Send only
   minimised metadata, as the prototype does.
2. **The privacy point is real and should be prominent:** APP 1.7–1.9
   (automated-decision transparency, commencing 10 Dec 2026). JML and
   access-review flags are about identifiable staff. Even with an SO in the loop,
   clients may need to mention automated flagging in their privacy policy. The
   prototype's design (flags only, human decides) helps, but it doesn't remove the
   obligation.
3. **The legal-practice boundary is good and BC1 should adopt it:** position the
   work as *technical evidence engineering*, not advice on statutory liability.
4. **The 90-day plan is optimistic:** a pilot within 30 days plus connectors and an
   agent within 60 days, at a lower price point than BC1. BC1's 10-week, 3-stream
   prototype with explicit exit criteria is more realistic.
5. **Two source-specific facts should be verified before use:** the "XP188" incident
   reporting reference, and ASR submission "via the DISP Member Portal".

## 4. Validation still owed (from BC1 §10, unchanged)

The prototype makes the discovery calls concrete, but it does not remove them:

- [ ] Verify current DISP Entry Level / Level 1 cyber and reporting requirements (DSPF Principle 16)
- [ ] 8–10 discovery calls with WA subcontractors + 2–3 prime supplier-assurance contacts, **using this demo**
- [ ] Ask the primes directly whether they would accept the monthly pack (with hash chain and SO sign-off) as supplier-assurance evidence
- [ ] A DISP-experienced reviewer rates the evidence pack PDF as assessor-ready, or lists the gaps
- [ ] Pick one pricing model (BC1 vs BC2)
- [ ] Run the Graph connector against a real M365 sandbox or design-partner tenant (the step that needs Microsoft licensing or a partner)

## 5. How the prototype maps to BC1's exit criteria

| BC1 exit criterion | Prototype status |
|---|---|
| Three streams run unattended for a full monthly cycle with zero manual collection | Met on simulated data (all 7 streams). A real tenant is still to be tested |
| New tenant onboarded from template in < 1 day | Not demonstrable locally (needs Bicep + a real tenant). The connector interface and permission map are ready |
| SO confirms the pack replaces manual evidence gathering | Use the demo in discovery calls to test this |
| Independent reviewer rates the pack assessor-ready | Send `evidence-pack-YYYY-MM.pdf` to a reviewer |
