# TASKS.md — Project Aegis-Bridge: Execution Sprints

All sprints assume one part-time founder. Estimated at 15–20 hours/week.

---

## Sprint 0 — Environment Setup (Week 1, ~8 hours)

- [ ] Install Obsidian and create the `aegis-vault/` directory structure per SPEC.md
- [ ] Install plugins: Dataview, Smart Connections, Templater, Canvas
- [ ] Create GitHub repo (`aegis-bridge`) and gitignore the `clients/` folder
- [ ] Set up Python virtual environment for tooling scripts
- [ ] Register domain name (e.g. `aegisbridge.com.au`, ~$20/yr)
- [ ] Create LinkedIn company page and personal founder profile polish

---

## Sprint 1 — Knowledge Base: Frameworks (Weeks 1–2, ~20 hours)

### Goal
Populate the vault with complete, tagged, cross-referenced control notes.

- [ ] **Essential Eight**
  - [ ] Create one note per control × maturity level (ML0–ML3) = ~32 notes
  - [ ] Add YAML frontmatter (`control-id`, `topic`, `effort-estimate`, `disp-relevant`)
  - [ ] Create Dataview query in `mappings/e8-summary.md` showing all controls as a table

- [ ] **ASD ISM (June 2025 Revision)**
  - [ ] Import ISM controls relevant to small organisations (filter by applicability tag)
  - [ ] Tag each with linked E8 control where mapping exists
  - [ ] Priority focus: access control, patch management, MFA, logging, backups

- [ ] **NIST 800-171 rev 2**
  - [ ] Create note per control family (14 families, ~110 controls)
  - [ ] Map each to ISM equivalent in frontmatter (`nist-equivalent` field)

- [ ] **DISP Requirements**
  - [ ] Summarise each DISP tier's requirements in plain English
  - [ ] Link each requirement to the relevant ISM/E8 controls

- [ ] Create `mappings/nist-to-ism.md` and `mappings/disp-to-e8.md` with Dataview tables
- [ ] Validate cross-references: every ISM control cited in a mapping must have a corresponding note

**Deliverable:** A queryable vault where you can ask "what E8 controls satisfy ISM-1631?" and get an accurate answer.

---

## Sprint 2 — Intake & Gap Analysis Tooling (Weeks 2–3, ~15 hours)

### Goal
Build the intake-to-report pipeline so a client engagement can be completed
in under 4 hours of total analyst time.

- [ ] **Intake Form (Tally)**
  - [ ] Draft 40-question intake covering all E8 control areas
  - [ ] Group questions by control family with clear plain-English phrasing
  - [ ] Test form end-to-end with dummy responses
  - [ ] Configure Tally webhook or CSV export

- [ ] **Intake Import Script (`tools/intake_import.py`)**
  - [ ] Read Tally CSV export
  - [ ] Map responses to control status: Met / Partial / Not Met
  - [ ] Write populated `gap-analysis.md` into `clients/<client-name>/` folder
  - [ ] Include effort estimate per gap from control note frontmatter

- [ ] **Gap Analysis Template (`templates/gap-analysis-template.md`)**
  - [ ] Section: Executive Summary (populated manually, 1 paragraph)
  - [ ] Section: Control Status Table (Dataview query on client folder)
  - [ ] Section: Prioritised Remediation Roadmap (ordered by DISP risk weight)
  - [ ] Section: Effort & Cost Estimates
  - [ ] Section: Next Steps

- [ ] **Report Export**
  - [ ] Test Obsidian PDF export of gap analysis template
  - [ ] Confirm output is client-presentable (formatting, no internal links visible)

- [ ] Run a complete test engagement using a fictional SME profile
- [ ] Time the process end-to-end and document bottlenecks

**Deliverable:** A complete dummy gap-analysis report that demonstrates the product to a prospect.

---

## Sprint 3 — Tender Monitor & Market Intelligence (Week 3, ~8 hours)

### Goal
A simple, automated feed of relevant public procurement activity embedded in
the Obsidian vault.

- [ ] **`tools/tender_monitor.py`**
  - [ ] Poll AusTender open data / RSS for new RFTs
  - [ ] Filter by keyword list: `AUKUS`, `DISP`, `ISM`, `Essential Eight`,
        `cyber security`, `Henderson`, `defence industry`
  - [ ] Write filtered results to `vault/tools/tender-watch.json`
  - [ ] Add a Dataview JavaScript block in `tools/tender-watch.md` to render the JSON as a table

- [ ] Set up cron job (or Windows Task Scheduler) to run script daily
- [ ] Test: confirm a known recent AUKUS-related tender appears in the vault

**Deliverable:** Tender watch note in vault auto-updates daily from public AusTender data.

---

## Sprint 4 — Client Portal & Outreach Setup (Week 4, ~10 hours)

### Goal
A presentable client-facing view and a legitimate outreach starting point.

- [ ] **Client Portal (Obsidian Publish — $10/mo)**
  - [ ] Configure Publish for the `templates/` and one anonymised demo client folder
  - [ ] Test that `clients/` (real client data) is excluded from publish
  - [ ] Create a demo workspace showing the Canvas compliance map view

- [ ] **Website (GitHub Pages or Carrd — free/$19yr)**
  - [ ] Home page: what Aegis-Bridge does, for whom, and at what price
  - [ ] Services page: Gap Analysis, Remediation Advisory, Fractional Architect
  - [ ] Free resource: link to "Essential Eight for Defence SMEs" guide PDF
  - [ ] Contact form (Tally embed)

- [ ] **"Essential Eight for Defence SMEs" Guide**
  - [ ] Write 4–6 page plain-English guide covering what E8 is, why it matters
        for DISP, and the most common gaps for small firms
  - [ ] Export as PDF from Obsidian
  - [ ] Host on website as a free download (no email gate — builds trust)

- [ ] **Outreach Template (honest, short)**
  - [ ] Draft 3-sentence LinkedIn message for AUKUS grant recipients
  - [ ] Draft equivalent cold email
  - [ ] Have both reviewed for ACL compliance (no misleading claims)

- [ ] Identify first 10 target firms from published AUKUS SME Readiness Fund
      recipient lists (public government announcements)

**Deliverable:** Website live, free guide published, first outreach list prepared.

---

## Sprint 5 — First Engagement (Week 5+)

- [ ] Send outreach to first 10 firms
- [ ] Conduct at least 2 discovery calls
- [ ] Complete first paid gap analysis (or volunteer engagement for validation)
- [ ] Gather feedback and update intake form / template accordingly
- [ ] Document time spent per engagement phase for future pricing validation

---

## Ongoing Maintenance Tasks (Monthly)

- [ ] Check for ASD ISM updates and update affected vault notes
- [ ] Check for E8 Maturity Model updates (ACSC publishes periodically)
- [ ] Review tender monitor keyword list for relevance
- [ ] Update client portal demo with any template improvements
