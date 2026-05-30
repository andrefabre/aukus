# SPEC.md — Project Aegis-Bridge: Technical Infrastructure

## Overview

Aegis-Bridge is a low-overhead compliance advisory service and toolset for
Western Australian SMEs entering AUKUS Pillar II supply chains. The system
helps small firms understand and close genuine gaps against DISP, Essential
Eight, and NIST 800-171 requirements — frameworks they are legally required
to meet but rarely have internal expertise to navigate.

Cost philosophy: favour free/open tooling, local-first processing, and
Obsidian-native workflows over cloud infrastructure until revenue justifies
the upgrade.

---

## 1. The Intelligence Layer — Market & Tender Monitoring

### Purpose
Stay informed about publicly available AUKUS-related procurement activity so
the business can offer relevant, timely services to the right firms.

### Data Sources (all public, no scraping of private data)
| Source | What we read | Update cadence |
|---|---|---|
| AusTender RSS / open data portal | New RFTs tagged with AUKUS/DISP keywords | Daily |
| DSR / AUKUS SME Readiness Fund announcements | Grant recipients (published by govt) | Weekly |
| Henderson Alliance public member list | Member firm names and sectors | Monthly |
| Defence Industry Directory (public) | WA firm profiles | Monthly |

### Implementation
- A lightweight Python script (`tender_monitor.py`) polls AusTender's public
  API and RSS feeds, filters by keyword list, and writes structured results to
  a local JSON file.
- The JSON is imported into Obsidian via the **Dataview** plugin, making
  tender activity browsable alongside compliance notes.
- No personal data is collected. Firm names and tender references are already
  public government records.

### Cost
- Python + cron job on a developer laptop: $0
- AusTender API: free, no key required

---

## 2. The Knowledge Base — Obsidian-Native Compliance Framework

### Purpose
Replace an expensive RAG/vector-database pipeline with a well-structured
Obsidian vault that maps compliance controls, cross-references frameworks, and
surfaces actionable gaps for each client engagement.

### Vault Structure
```
aegis-vault/
├── frameworks/
│   ├── essential-eight/          # One note per maturity level per control
│   ├── asd-ism/                  # ISM controls tagged by topic
│   ├── nist-800-171/             # 110 controls, each linked to ISM equivalents
│   └── disp/                    # DISP requirement summaries
├── mappings/
│   ├── e8-to-ism.md             # Cross-reference table (Dataview query)
│   ├── nist-to-ism.md           # NIST ↔ ISM control mapping
│   └── disp-to-e8.md           # DISP requirement ↔ Essential Eight
├── clients/                     # One folder per client (gitignored)
│   └── template/
│       ├── intake.md
│       ├── gap-analysis.md
│       └── roadmap.md
├── templates/
│   ├── gap-analysis-template.md
│   ├── roadmap-template.md
│   └── report-template.md
└── tools/
    └── tender-watch.md          # Live Dataview embed of tender_monitor output
```

### Key Obsidian Plugins
| Plugin | Purpose | Cost |
|---|---|---|
| Dataview | Query controls and client data as tables | Free |
| Smart Connections | Semantic similarity across notes (local model) | Free |
| Templater | Populate client files from standard templates | Free |
| Canvas | Visual compliance maps for client presentations | Built-in |

### Cross-Reference Logic ("Compliance Primitives")
Each control note carries YAML frontmatter:
```yaml
---
control-id: ISM-1631
framework: ASD-ISM
topic: access-control
essential-eight-ml: 2
nist-equivalent: AC-2
disp-relevant: true
effort-estimate: medium   # low / medium / high for a 20-person firm
---
```
Dataview queries aggregate these tags to produce per-client gap tables and
prioritised remediation lists without any cloud infrastructure.

---

## 3. The Compliance Assessment Tool

### Purpose
A structured, repeatable process for conducting genuine gap analyses that
produce honest, auditable outputs — not manufactured fear.

### Intake Questionnaire
A 40-question intake form (delivered as a Tally form — free tier) covering:
- Current IT asset inventory practices
- Patch management cadence
- MFA coverage
- Backup and recovery posture
- Access control policies
- Incident response capability

Responses are exported to CSV and imported into the client's Obsidian folder
via a small Python script (`intake_import.py`), populating the gap-analysis
template automatically.

### Gap Analysis Output
The populated template produces:
1. A control-by-control status table (Met / Partial / Not Met)
2. A prioritised remediation list ordered by DISP risk weighting
3. Effort and cost estimates for each gap, sized for an SME budget
4. An executive summary in plain English

### Cost
- Tally free tier: $0
- Python scripts: $0
- Obsidian: $0 (personal licence) / $50/yr (commercial)

---

## 4. The Client Portal

### Purpose
Give clients a simple, honest view of their compliance posture over time
without building a custom web application.

### Approach (Phase 1 — pre-revenue)
Use **Obsidian Publish** or a static export to share a read-only client
subfolder. The Canvas plugin provides visual "map of connections" showing
which controls are met, in-progress, or open.

### Approach (Phase 2 — post first retainer)
Migrate to a **Notion** client workspace (free for guests) or a lightweight
**Streamlit** dashboard reading from the Obsidian vault's exported JSON. This
adds real-time status indicators and progress tracking at near-zero hosting
cost (Streamlit Community Cloud is free).

### What the portal shows
- Essential Eight maturity level per control (colour-coded)
- Open vs. closed action items with due dates
- Upcoming tender deadlines relevant to their sector
- Links to relevant ISM guidance notes

---

## 5. Technology Stack Summary

| Layer | Tool | Monthly Cost |
|---|---|---|
| Knowledge base | Obsidian (local) | $0–$4 |
| Tender monitoring | Python + cron | $0 |
| Intake forms | Tally free tier | $0 |
| Client reporting | Obsidian Canvas + PDF export | $0 |
| Client portal (early) | Obsidian Publish | $10 |
| Client portal (growth) | Streamlit Community Cloud | $0 |
| Email (outreach + delivery) | Resend free tier (3k/mo) | $0 |
| Version control | GitHub free | $0 |
| **Total (early stage)** | | **~$10–14/mo** |
