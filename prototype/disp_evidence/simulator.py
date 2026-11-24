"""Deterministic simulated Microsoft 365 tenant for a fictional WA defence SME.

Everything here is invented. The company, people, partners and vulnerability ids
are fictional; domains use the reserved `.example` TLD. The tenant is built as a
*timeline* for calendar 2026 from a seed, so any month can be "collected" at any
cut-off and the same inputs always give the same evidence.

The shapes returned by `SimulatedTenant` loosely follow Microsoft Graph
resources (users, directoryRoles, managedDevices, directoryAudits,
userRegistrationDetails, conditionalAccess policies) so the real Graph connector
can map onto the same collector code.

Seeded control failures (so the demo has something to find):
  * leaver accounts disabled late (30 hours, 9 days) and one never disabled
  * an account with no HR record (temporary contractor) from July
  * a mover who kept membership of the Defence project group
  * an Exchange admin who stops signing in (stale privileged account)
  * Global Admin count above policy in September
  * Windows 10 devices (unsupported since Oct 2025) and laggard field laptops
  * an internet-facing VPN appliance patched 6 days after an exploited fix (Aug)
  * MFA registration gaps that close over the year; an MSP admin on SMS only
  * Block-legacy-auth Conditional Access policy in report-only until July
  * overdue annual security training; visitor sign-outs / escorts missed
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

UTC = timezone.utc
TENANT_NAME = "Banksia Marine Fabrication Pty Ltd (fictional)"
TENANT_SHORT = "banksia"
DOMAIN = "banksiamarine.example"
YEAR = 2026

FIRST = ["Alex", "Bree", "Callum", "Dana", "Eli", "Fiona", "Gus", "Hana", "Isaac", "Jade",
         "Kai", "Lena", "Mason", "Nina", "Owen", "Priya", "Quinn", "Rosa", "Sam", "Tara",
         "Umar", "Vera", "Will", "Xena", "Yusuf", "Zoe", "Ari", "Beau", "Cleo", "Drew",
         "Esme", "Finn", "Gemma", "Hugo", "Ivy", "Jack", "Kira", "Liam", "Maya", "Noah",
         "Orla", "Pete", "Ruby", "Seth", "Tess", "Theo", "Uma", "Vic", "Wren", "Zac"]
LAST = ["Abbott", "Barker", "Chen", "Doyle", "Evans", "Fraser", "Gill", "Hart", "Ito", "Jones",
        "Khan", "Lowe", "Moss", "Ng", "Oakes", "Patel", "Quill", "Reid", "Singh", "Tran",
        "Usman", "Vaughan", "Walsh", "Xu", "Young", "Zhou"]
DEPTS = [("Engineering", ["Design Engineer", "Structural Engineer", "Drafter", "Project Engineer"]),
         ("Fabrication", ["Boilermaker", "Welder", "Fitter", "Workshop Supervisor"]),
         ("Operations", ["Operations Coordinator", "Logistics Officer", "Planner"]),
         ("Commercial", ["Contracts Officer", "Estimator", "Business Development"]),
         ("Corporate", ["Accounts Officer", "HR Advisor", "Office Manager"])]
PARTNERS = ["Tasman Prime Systems (fictional)", "Westcoast Naval Services (fictional)",
            "Coral Bay Logistics (fictional)", "Swan River Calibration (fictional)",
            "Leeuwin Cranes (fictional)", "Pilbara Coatings (fictional)"]


def dt(y: int, m: int, d: int, h: int = 9, mi: int = 0) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=UTC)


def month_bounds(period: str) -> tuple[datetime, datetime]:
    """Return [start, end) datetimes for a YYYY-MM period."""
    y, m = (int(x) for x in period.split("-"))
    start = datetime(y, m, 1, tzinfo=UTC)
    end = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=UTC)
    return start, end


@dataclass
class Person:
    emp_id: str
    name: str
    upn: str
    department: str
    title: str
    start: date
    end: date | None = None
    moves: list[tuple[date, str, str]] = field(default_factory=list)   # (date, dept, title)
    account_created: datetime | None = None
    account_disabled: datetime | None = None
    stops_signing_in: date | None = None
    in_hr: bool = True
    kind: str = "member"            # member | guest | service | breakglass
    company: str = ""
    mfa_methods: list[tuple[date, str]] = field(default_factory=list)  # (registered on, method)
    training: list[date] = field(default_factory=list)

    def dept_title_at(self, d: date) -> tuple[str, str]:
        dept, title = self.department, self.title
        for when, new_dept, new_title in sorted(self.moves):
            if when <= d:
                dept, title = new_dept, new_title
        return dept, title

    def exists_at(self, t: datetime) -> bool:
        return self.account_created is not None and self.account_created <= t

    def enabled_at(self, t: datetime) -> bool:
        return self.exists_at(t) and (self.account_disabled is None or self.account_disabled > t)


@dataclass
class Device:
    name: str
    owner_upn: str
    os: str
    os_version: str
    profile: str                     # good | average | laggard
    internet_facing: bool = False
    engineering: bool = False
    sync_gaps: list[tuple[date, date]] = field(default_factory=list)


@dataclass
class Release:
    vuln_id: str
    product: str
    category: str                    # os | priority_app | other_app | internet_facing
    severity: str
    released: datetime
    exploit: bool
    applies_to: str                  # windows | mac | ios | all_desktop | engineering | vpn


class SimulatedTenant:
    """Timeline-backed fake tenant. Construct via `get_tenant(seed)`."""

    def __init__(self, seed: int = 2026):
        self.seed = seed
        self.rng = random.Random(seed)
        self.name = TENANT_NAME
        self.short = TENANT_SHORT
        self.people: list[Person] = []
        self.devices: list[Device] = []
        self.releases: list[Release] = []
        self.remediation: dict[tuple[str, str], datetime | None] = {}
        self.roles: list[dict[str, Any]] = []        # {role, upn, from, to}
        self.group_members: list[dict[str, Any]] = []  # {group, upn, from, to, owner}
        self.ca_policies: list[dict[str, Any]] = []
        self.incidents: list[dict[str, Any]] = []
        self._build()

    # ------------------------------------------------------------------ build
    def _upn(self, first: str, last: str) -> str:
        base = f"{first[0]}.{last}".lower()
        upn, n = f"{base}@{DOMAIN}", 2
        existing = {p.upn for p in self.people}
        while upn in existing:
            upn, n = f"{base}{n}@{DOMAIN}", n + 1
        return upn

    def _person(self, first: str, last: str, dept: str, title: str, start: date, **kw: Any) -> Person:
        p = Person(emp_id=f"E{len(self.people) + 1001}", name=f"{first} {last}",
                   upn=self._upn(first, last), department=dept, title=title, start=start, **kw)
        if p.account_created is None:
            lead = self.rng.randint(1, 5)
            p.account_created = datetime.combine(start - timedelta(days=lead), datetime.min.time(), UTC) + timedelta(hours=9)
        self.people.append(p)
        return p

    def _build(self) -> None:
        rng = self.rng
        names = [(f, l) for f in FIRST for l in LAST]
        rng.shuffle(names)
        it = iter(names)

        # Key named roles first.
        it_mgr = self._person("Morgan", "Hale", "Corporate", "IT Manager", date(2019, 3, 4))
        so = self._person("Riley", "Okafor", "Corporate", "Security Officer", date(2020, 7, 13))
        cso = self._person("Jordan", "Blake", "Corporate", "Managing Director / CSO", date(2015, 1, 5))
        exch = self._person("Jamie", "Ng", "Corporate", "Systems Administrator", date(2021, 5, 17))
        exch.stops_signing_in = date(2026, 6, 20)
        ops_dir = self._person("Casey", "Doyle", "Operations", "Operations Director", date(2017, 9, 1))

        # Base roster (employed before 2026).
        for _ in range(38):
            f, l = next(it)
            dept, titles = rng.choice(DEPTS)
            self._person(f, l, dept, rng.choice(titles), date(rng.randint(2016, 2025), rng.randint(1, 12), rng.randint(1, 28)))

        # 2026 joiners.
        joiner_dates = [date(2026, 2, 9), date(2026, 3, 16), date(2026, 5, 4), date(2026, 6, 15),
                        date(2026, 7, 6), date(2026, 8, 17), date(2026, 9, 7), date(2026, 10, 12), date(2026, 11, 2)]
        joiners = []
        for jd in joiner_dates:
            f, l = next(it)
            dept, titles = rng.choice(DEPTS)
            joiners.append(self._person(f, l, dept, rng.choice(titles), jd))

        # 2026 leavers with seeded removal delays (None = never disabled -> orphan).
        base = [p for p in self.people[5:43]]
        leaver_plan = [(date(2026, 1, 30), timedelta(hours=2)), (date(2026, 3, 13), timedelta(hours=30)),
                       (date(2026, 4, 24), timedelta(hours=1)), (date(2026, 6, 5), timedelta(days=9)),
                       (date(2026, 7, 31), None), (date(2026, 9, 18), timedelta(hours=3)),
                       (date(2026, 10, 23), timedelta(hours=26)), (date(2026, 11, 13), timedelta(hours=1))]
        leavers = rng.sample(base, len(leaver_plan))
        for p, (end, delay) in zip(leavers, leaver_plan):
            p.end = end
            p.account_disabled = None if delay is None else datetime.combine(end, datetime.min.time(), UTC) + timedelta(hours=17) + delay
        self.orphan_upn = leavers[4].upn

        # Movers. One Engineering person moves to Commercial but keeps Defence group access.
        eng = [p for p in base if p.department == "Engineering" and p not in leavers]
        non_eng = [p for p in base if p.department != "Engineering" and p not in leavers]
        self.sticky_mover = eng[0]
        eng[0].moves.append((date(2026, 7, 15), "Commercial", "Estimator"))
        non_eng[0].moves.append((date(2026, 4, 6), "Operations", "Planner"))
        non_eng[1].moves.append((date(2026, 9, 21), "Engineering", "Project Engineer"))

        # Accounts with no HR record.
        self._person("Temp", "Contractor", "Fabrication", "Contract Welder (no HR record)", date(2026, 7, 20),
                     in_hr=False, account_created=dt(2026, 7, 20, 7))
        self._person("Svc", "Scanner", "Corporate", "Service account - MFD scan-to-email", date(2022, 2, 1),
                     in_hr=False, kind="service")
        self._person("Break", "Glass", "Corporate", "Emergency access account", date(2021, 1, 1),
                     in_hr=False, kind="breakglass")
        msp = self._person("Msp", "Admin", "Corporate", "MSP administrator (Perth MSP, fictional)", date(2023, 6, 1),
                           in_hr=False, kind="service")

        # Guests.
        for i, company in enumerate(PARTNERS[:5]):
            f, l = next(it)
            g = Person(emp_id=f"G{i + 1}", name=f"{f} {l}", upn=f"{f.lower()}.{l.lower()}_{company.split()[0].lower()}.example#EXT#@{DOMAIN}",
                       department="External", title="Guest", start=date(2025, rng.randint(1, 12), 10), in_hr=False,
                       kind="guest", company=company)
            g.account_created = datetime.combine(g.start, datetime.min.time(), UTC)
            if i in (1, 3):
                g.stops_signing_in = date(2026, rng.choice([2, 4]), 15)
            self.people.append(g)

        # Directory roles.
        def role(name: str, upn: str, start: datetime, end: datetime | None = None) -> None:
            self.roles.append({"role": name, "upn": upn, "from": start, "to": end})

        bg = next(p for p in self.people if p.kind == "breakglass")
        role("Global Administrator", it_mgr.upn, dt(2019, 3, 10))
        role("Global Administrator", bg.upn, dt(2021, 1, 1))
        role("Global Administrator", msp.upn, dt(2023, 6, 1))
        role("Global Administrator", ops_dir.upn, dt(2026, 9, 2), dt(2026, 10, 6))
        role("Global Administrator", exch.upn, dt(2026, 9, 2), dt(2026, 10, 6))
        role("Exchange Administrator", exch.upn, dt(2021, 6, 1))
        role("Intune Administrator", it_mgr.upn, dt(2020, 1, 1))
        role("Security Reader", so.upn, dt(2020, 8, 1))
        role("User Administrator", so.upn, dt(2026, 1, 1))
        self.breakglass_upn = bg.upn
        self.it_manager, self.security_officer, self.cso = it_mgr, so, cso

        # Privileged groups (Defence technical data / site access).
        def member(group: str, upn: str, start: datetime, end: datetime | None = None, owner: bool = False) -> None:
            self.group_members.append({"group": group, "upn": upn, "from": start, "to": end, "owner": owner})

        member("SG-Defence-Projects", so.upn, dt(2020, 8, 1), owner=True)
        member("SG-Defence-Projects", it_mgr.upn, dt(2020, 8, 1), owner=True)
        for p in self.people:
            if p.kind != "member" or p.department != "Engineering":
                continue
            start = max(p.account_created or dt(2020, 1, 1), dt(2020, 1, 1))
            end = p.account_disabled if p.end else None
            if p.upn == self.orphan_upn:
                end = None
            member("SG-Defence-Projects", p.upn, start, end)
        mover_in = non_eng[1]
        member("SG-Defence-Projects", mover_in.upn, dt(2026, 9, 22))
        site_owner = leavers[3]  # owner leaves in June -> group has no active owner
        member("SG-Henderson-Site", site_owner.upn, dt(2022, 1, 1), site_owner.account_disabled, owner=True)
        for p in rng.sample([p for p in base if p.department == "Fabrication"], 6):
            member("SG-Henderson-Site", p.upn, dt(2022, 1, 1), p.account_disabled if p.end else None)
        self.site_group_owner = site_owner.upn

        # MFA registration. Coverage closes over the year; a few never register.
        members = [p for p in self.people if p.kind == "member"]
        late = set(rng.sample([p.upn for p in members if p not in (it_mgr, so, exch)], 9))
        never = set(list(late)[:2])
        for p in self.people:
            if p.kind == "breakglass":
                p.mfa_methods.append((date(2021, 1, 1), "fido2"))
                continue
            if p.kind == "guest":
                p.mfa_methods.append((p.start, "microsoftAuthenticatorPush"))
                continue
            if p is msp:
                p.mfa_methods.append((date(2023, 6, 1), "mobilePhone"))
                p.mfa_methods.append((date(2026, 8, 12), "fido2"))
                continue
            if p.kind == "service":
                continue  # service account: excluded from MFA (CA exclusion) -> flagged
            if p.upn in never:   # chased via exception tasks; finally register in November
                p.mfa_methods.append((date(2026, 11, 5), "microsoftAuthenticatorPush"))
                continue
            if p.upn in late:
                p.mfa_methods.append((date(2026, rng.randint(2, 9), rng.randint(1, 28)), "microsoftAuthenticatorPush"))
                continue
            reg = max(p.start, date(2024, 1, 1)) + timedelta(days=rng.randint(0, 3))
            p.mfa_methods.append((reg, "microsoftAuthenticatorPush"))
            if p in (it_mgr, so, cso, exch):
                p.mfa_methods.append((date(2025, 11, 3), "fido2"))
        # one joiner registers MFA late
        joiners[3].mfa_methods = [(joiners[3].start + timedelta(days=40), "microsoftAuthenticatorPush")]

        # Conditional Access policies.
        self.ca_policies = [
            {"displayName": "CA01 - Require MFA for all users", "grant": "mfa", "excludes": ["service accounts", "break-glass"],
             "timeline": [(dt(2024, 2, 1), "enabled")]},
            {"displayName": "CA02 - Block legacy authentication", "grant": "block",  "excludes": [],
             "timeline": [(dt(2025, 10, 1), "enabledForReportingButNotEnforced"), (dt(2026, 7, 14), "enabled")]},
            {"displayName": "CA03 - Phishing-resistant MFA for admin roles", "grant": "authenticationStrength:phishingResistant",
             "excludes": ["break-glass"], "timeline": [(dt(2026, 3, 2), "enabledForReportingButNotEnforced"), (dt(2026, 8, 13), "enabled")]},
            {"displayName": "CA04 - Require compliant device for Defence project site", "grant": "compliantDevice", "excludes": [],
             "timeline": [(dt(2025, 5, 1), "enabled")]},
        ]

        # Training: annual awareness module.
        for p in self.people:
            if p.kind != "member":
                continue
            if p.start < date(2025, 12, 1):
                last = date(2025, rng.randint(1, 12), rng.randint(1, 28))
                if last < p.start:
                    last = p.start + timedelta(days=10)
                p.training.append(last)
                roll = rng.random()
                if roll < 0.80:
                    nxt = last + timedelta(days=365 - rng.randint(5, 40))
                elif roll < 0.95:
                    nxt = last + timedelta(days=365 + rng.randint(10, 70))
                else:
                    nxt = None
                if nxt:
                    p.training.append(nxt)
            else:
                delay = 45 if p is joiners[5] else rng.randint(3, 21)
                p.training.append(p.start + timedelta(days=delay))

        # Devices.
        win10 = 0
        for p in self.people:
            if p.kind != "member" or p.end and p.end < date(2026, 1, 1):
                continue
            prefix = "BMF-LT" if p.department != "Fabrication" else "BMF-WS"
            os_name, ver = "Windows", "11 24H2"
            if p.department == "Fabrication" and win10 < 3:
                os_name, ver = "Windows", "10 22H2"
                win10 += 1
            elif rng.random() < 0.08:
                os_name, ver = "macOS", "15.5"
            profile = rng.choices(["good", "average", "laggard"], [0.72, 0.23, 0.05])[0]
            d = Device(f"{prefix}{len(self.devices) + 101:03d}", p.upn, os_name, ver, profile,
                       engineering=p.department == "Engineering")
            if p.department == "Fabrication" and rng.random() < 0.25:
                d.profile = "laggard"
                d.sync_gaps.append((date(2026, rng.randint(2, 10), 3), date(2026, rng.randint(2, 10), 3) + timedelta(days=21)))
            self.devices.append(d)
            if rng.random() < 0.6:
                self.devices.append(Device(f"BMF-PH{len(self.devices) + 101:03d}", p.upn, "iOS", "18.5", "good"))
        self.devices.append(Device("BMF-VPN01", it_mgr.upn, "Appliance", "GW firmware 9.1", "good", internet_facing=True))

        # Releases (patches) through 2026.
        def second_tuesday(y: int, m: int) -> date:
            d0 = date(y, m, 1)
            first_tue = d0 + timedelta(days=(1 - d0.weekday()) % 7)
            return first_tue + timedelta(days=7)

        for m in range(1, 13):
            pt = second_tuesday(YEAR, m)
            self._release("Windows cumulative update", "os", "critical", pt, False, "windows")
            self._release("Microsoft 365 Apps", "priority_app", "high", pt, False, "all_desktop")
            self._release("Adobe Acrobat Reader", "priority_app", "high", pt + timedelta(days=1), m in (4, 9), "all_desktop")
            self._release("Google Chrome", "priority_app", "high", date(YEAR, m, 5), m == 6, "all_desktop")
            self._release("Google Chrome", "priority_app", "medium", date(YEAR, m, 20), False, "all_desktop")
            self._release("macOS security update", "os", "high", date(YEAR, m, 22), False, "mac")
            self._release("iOS security update", "os", "high", date(YEAR, m, 18), False, "ios")
            if m % 3 == 1:
                self._release("7-Zip", "other_app", "medium", date(YEAR, m, 26), False, "all_desktop")
            if m % 2 == 0:
                self._release("CAD design suite", "other_app", "medium", date(YEAR, m, 8), False, "engineering")
        for m, d, exploit in ((3, 10, False), (8, 4, True), (11, 3, False)):
            self._release("Edge VPN gateway firmware", "internet_facing", "critical", date(YEAR, m, d), exploit, "vpn")

        self._schedule_remediation()

        # Incident register (SharePoint list) for the ASR roll-up.
        self.incidents = [
            {"id": "INC-2026-01", "date": "2026-03-11", "category": "Phishing (reported, no compromise)",
             "summary": "Credential-harvest email reported by 4 staff; message purged tenant-wide.", "reportable_to_defence": False},
            {"id": "INC-2026-02", "date": "2026-06-02", "category": "Lost device",
             "summary": "Company iPhone lost on site; remote wipe confirmed via Intune within 2 hours.", "reportable_to_defence": True,
             "reported_on": "2026-06-02"},
            {"id": "INC-2026-03", "date": "2026-08-07", "category": "Exploitation attempt (blocked)",
             "summary": "Scanning of VPN appliance for newly exploited flaw before patch applied; no access gained.",
             "reportable_to_defence": True, "reported_on": "2026-08-08"},
            {"id": "INC-2026-04", "date": "2026-10-15", "category": "Contact reporting",
             "summary": "Unsolicited approach via professional networking site to an engineer; reported to SO.",
             "reportable_to_defence": True, "reported_on": "2026-10-16"},
        ]

    def _release(self, product: str, category: str, severity: str, released: date, exploit: bool, applies: str) -> None:
        code = "".join(w[0] for w in product.split()).upper()
        self.releases.append(Release(f"SIM-{code}-{released:%Y%m%d}", product, category, severity,
                                     datetime.combine(released, datetime.min.time(), UTC) + timedelta(hours=18),
                                     exploit, applies))

    def _applies(self, r: Release, d: Device) -> bool:
        if r.applies_to == "vpn":
            return d.internet_facing
        if d.internet_facing:
            return False
        if r.applies_to == "windows":
            return d.os == "Windows" and d.os_version.startswith("11")   # Win10: no more fixes
        if r.applies_to == "mac":
            return d.os == "macOS"
        if r.applies_to == "ios":
            return d.os == "iOS"
        if r.applies_to == "all_desktop":
            return d.os in ("Windows", "macOS")
        if r.applies_to == "engineering":
            return d.engineering and d.os in ("Windows", "macOS")
        return False

    def _schedule_remediation(self) -> None:
        rng = random.Random(self.seed + 1)
        for r in self.releases:
            month_factor = max(0.45, 1 - 0.07 * (r.released.month - 1))
            for d in self.devices:
                if not self._applies(r, d):
                    continue
                if d.internet_facing:
                    delay = timedelta(days=6) if r.exploit else timedelta(days=5)
                else:
                    lo, hi = {"good": (1, 9), "average": (6, 26), "laggard": (18, 60)}[d.profile]
                    base = rng.uniform(lo, hi) * month_factor
                    if r.category == "other_app":
                        base *= 1.6
                    delay = timedelta(days=base)
                when = r.released + delay
                for gs, ge in d.sync_gaps:      # offline devices patch after they reconnect
                    if gs <= when.date() <= ge:
                        when = datetime.combine(ge, datetime.min.time(), UTC) + timedelta(hours=10)
                self.remediation[(r.vuln_id, d.name)] = when

    # ------------------------------------------------------------------ queries
    def person(self, upn: str) -> Person | None:
        return next((p for p in self.people if p.upn == upn), None)

    def last_sign_in(self, p: Person, t: datetime) -> datetime | None:
        if not p.exists_at(t) or p.kind == "breakglass":
            return None
        cutoff = t
        if p.account_disabled and p.account_disabled < cutoff:
            cutoff = p.account_disabled
        if p.end and p.upn == self.orphan_upn:
            cutoff = min(cutoff, datetime.combine(p.end, datetime.min.time(), UTC) + timedelta(hours=16))
        if p.stops_signing_in:
            cutoff = min(cutoff, datetime.combine(p.stops_signing_in, datetime.min.time(), UTC) + timedelta(hours=11))
        if p.kind == "service":
            return cutoff - timedelta(hours=3)
        jitter = random.Random(f"{self.seed}|{p.upn}|{t.date().isoformat()}").randint(1, 40)
        result = cutoff - timedelta(hours=jitter)
        return max(result, p.account_created) if p.account_created else result

    def users(self, t: datetime) -> list[dict[str, Any]]:
        out = []
        for p in self.people:
            if not p.exists_at(t):
                continue
            dept, title = p.dept_title_at(t.date())
            last = self.last_sign_in(p, t)
            out.append({
                "id": f"sim-{p.emp_id.lower()}",
                "displayName": p.name,
                "userPrincipalName": p.upn,
                "userType": "Guest" if p.kind == "guest" else "Member",
                "accountEnabled": p.enabled_at(t),
                "createdDateTime": p.account_created.isoformat(),
                "department": dept,
                "jobTitle": title,
                "companyName": p.company or None,
                "employeeId": p.emp_id if p.in_hr else None,
                "signInActivity": {"lastSignInDateTime": last.isoformat() if last else None},
                "extension_accountKind": p.kind,
            })
        return out

    def role_assignments(self, t: datetime) -> list[dict[str, Any]]:
        return [{"roleDisplayName": r["role"], "principalUserPrincipalName": r["upn"],
                 "assignedDateTime": r["from"].isoformat()}
                for r in self.roles if r["from"] <= t and (r["to"] is None or r["to"] > t)]

    def privileged_groups(self, t: datetime) -> list[dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        for gm in self.group_members:
            g = groups.setdefault(gm["group"], {"displayName": gm["group"], "owners": [], "members": []})
            if gm["from"] <= t and (gm["to"] is None or gm["to"] > t):
                (g["owners"] if gm["owner"] else g["members"]).append(gm["upn"])
        return list(groups.values())

    def directory_audits(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        events = []
        for p in self.people:
            if p.kind == "guest":
                continue
            if p.account_created and start <= p.account_created < end:
                events.append({"activityDateTime": p.account_created.isoformat(), "activityDisplayName": "Add user",
                               "targetUserPrincipalName": p.upn, "initiatedBy": self.it_manager.upn})
            if p.account_disabled and start <= p.account_disabled < end:
                events.append({"activityDateTime": p.account_disabled.isoformat(), "activityDisplayName": "Disable account",
                               "targetUserPrincipalName": p.upn, "initiatedBy": self.it_manager.upn})
            for when, dept, title in p.moves:
                w = datetime.combine(when, datetime.min.time(), UTC) + timedelta(hours=10)
                if start <= w < end:
                    events.append({"activityDateTime": w.isoformat(), "activityDisplayName": "Update user",
                                   "targetUserPrincipalName": p.upn, "initiatedBy": self.it_manager.upn,
                                   "modifiedProperties": {"department": dept, "jobTitle": title}})
        for r in self.roles:
            for key, verb in (("from", "Add member to role"), ("to", "Remove member from role")):
                w = r[key]
                if w and start <= w < end:
                    events.append({"activityDateTime": w.isoformat(), "activityDisplayName": verb,
                                   "targetUserPrincipalName": r["upn"], "role": r["role"], "initiatedBy": self.it_manager.upn})
        for gm in self.group_members:
            for key, verb in (("from", "Add member to group"), ("to", "Remove member from group")):
                w = gm[key]
                if w and start <= w < end:
                    events.append({"activityDateTime": w.isoformat(), "activityDisplayName": verb,
                                   "targetUserPrincipalName": gm["upn"], "group": gm["group"], "initiatedBy": self.it_manager.upn})
        return sorted(events, key=lambda e: e["activityDateTime"])

    def hr_records(self, t: datetime) -> list[dict[str, Any]]:
        out = []
        for p in self.people:
            if not p.in_hr or p.start > t.date() + timedelta(days=14):
                continue
            dept, title = p.dept_title_at(t.date())
            out.append({"employeeId": p.emp_id, "name": p.name, "upn": p.upn, "department": dept, "title": title,
                        "startDate": p.start.isoformat(), "endDate": p.end.isoformat() if p.end and p.end <= t.date() + timedelta(days=14) else None,
                        "moves": [{"date": w.isoformat(), "department": d, "title": ti} for w, d, ti in p.moves if w <= t.date()]})
        return out

    def managed_devices(self, t: datetime) -> list[dict[str, Any]]:
        out = []
        for d in self.devices:
            owner = self.person(d.owner_upn)
            if owner and owner.account_disabled and owner.account_disabled < t and not d.internet_facing:
                continue  # retired with the leaver
            last_sync = t - timedelta(hours=6)
            for gs, ge in d.sync_gaps:
                gs_dt = datetime.combine(gs, datetime.min.time(), UTC)
                ge_dt = datetime.combine(ge, datetime.min.time(), UTC)
                if gs_dt <= t < ge_dt:
                    last_sync = gs_dt
            out.append({"deviceName": d.name, "operatingSystem": d.os, "osVersion": d.os_version,
                        "userPrincipalName": d.owner_upn, "lastSyncDateTime": last_sync.isoformat(),
                        "internetFacing": d.internet_facing, "managementAgent": "appliance" if d.internet_facing else "mdm"})
        return out

    def vulnerabilities(self, t: datetime, lookback_days: int = 62) -> list[dict[str, Any]]:
        """Open items at t, plus items remediated in the lookback window (TVM-like)."""
        devices = {d["deviceName"] for d in self.managed_devices(t)}
        out = []
        for r in self.releases:
            if r.released > t:
                continue
            for d in self.devices:
                if d.name not in devices:
                    continue
                key = (r.vuln_id, d.name)
                if key not in self.remediation:
                    continue
                fixed = self.remediation[key]
                if fixed and fixed <= t and fixed < t - timedelta(days=lookback_days):
                    continue
                out.append({"vulnId": r.vuln_id, "product": r.product, "category": r.category, "severity": r.severity,
                            "deviceName": d.name, "releasedDateTime": r.released.isoformat(), "exploitAvailable": r.exploit,
                            "remediatedDateTime": fixed.isoformat() if fixed and fixed <= t else None})
        return out

    def registration_details(self, t: datetime) -> list[dict[str, Any]]:
        admins = {r["principalUserPrincipalName"] for r in self.role_assignments(t)}
        out = []
        for p in self.people:
            if not p.enabled_at(t):
                continue
            methods = sorted({m for when, m in p.mfa_methods if when <= t.date()})
            out.append({"userPrincipalName": p.upn, "userDisplayName": p.name, "isAdmin": p.upn in admins,
                        "userType": "guest" if p.kind == "guest" else "member", "accountKind": p.kind,
                        "methodsRegistered": methods, "isMfaRegistered": bool(methods),
                        "isPhishingResistant": "fido2" in methods or "windowsHelloForBusiness" in methods})
        return out

    def conditional_access(self, t: datetime) -> list[dict[str, Any]]:
        out = []
        for pol in self.ca_policies:
            state = None
            for when, s in pol["timeline"]:
                if when <= t:
                    state = s
            if state:
                out.append({"displayName": pol["displayName"], "state": state, "grantControl": pol["grant"],
                            "excludes": pol["excludes"]})
        return out

    def training_records(self, t: datetime) -> list[dict[str, Any]]:
        out = []
        for p in self.people:
            if p.kind != "member" or not p.enabled_at(t) or not p.in_hr:
                continue
            done = [d for d in p.training if d <= t.date()]
            out.append({"upn": p.upn, "name": p.name, "startDate": p.start.isoformat(),
                        "course": "DISP Security Awareness (annual)",
                        "lastCompleted": max(done).isoformat() if done else None})
        return out

    def visitor_log(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        rng = random.Random(f"{self.seed}-visitors-{start:%Y-%m}")
        hosts = [p for p in self.people if p.kind == "member" and p.in_hr]
        out = []
        day = start.date()
        n = 0
        while day < end.date():
            if day.weekday() < 5:
                for _ in range(rng.choice([0, 1, 1, 2, 2, 3])):
                    n += 1
                    area = rng.choices(["Reception / office", "Workshop floor", "Defence project room"], [0.5, 0.35, 0.15])[0]
                    sign_in = datetime.combine(day, datetime.min.time(), UTC) + timedelta(hours=rng.randint(7, 15), minutes=rng.choice([0, 15, 30, 45]))
                    sign_out = sign_in + timedelta(hours=rng.randint(1, 4))
                    restricted = area == "Defence project room"
                    out.append({
                        "entryId": f"V{start:%y%m}-{n:03d}", "visitorName": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
                        "company": rng.choice(PARTNERS), "host": rng.choice(hosts).name, "area": area,
                        "purpose": rng.choice(["Inspection", "Delivery", "Project meeting", "Maintenance", "Audit"]),
                        "signIn": sign_in.isoformat(),
                        "signOut": None if rng.random() < 0.04 else sign_out.isoformat(),
                        "idChecked": rng.random() > 0.03,
                        "restrictedArea": restricted,
                        "escorted": (rng.random() > 0.08) if restricted else None,
                    })
            day += timedelta(days=1)
        return [v for v in out if datetime.fromisoformat(v["signIn"]) < end]

    def incident_register(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        return [i for i in self.incidents if start.date() <= date.fromisoformat(i["date"]) < end.date()]


@lru_cache(maxsize=4)
def get_tenant(seed: int = 2026) -> SimulatedTenant:
    return SimulatedTenant(seed)
