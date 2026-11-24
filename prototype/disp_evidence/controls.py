"""Control catalogue: the evidence streams and the controls they evidence.

Control ids are internal to this prototype. The `reference` field points at the
framework text a DISP-experienced reviewer should check the mapping against; it
is not a claim that the prototype satisfies that framework.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Control:
    control_id: str
    name: str
    framework: str
    reference: str
    stream: str
    description: str


@dataclass(frozen=True)
class Stream:
    stream_id: str
    number: int
    name: str
    short: str
    in_core_scope: bool          # business case section 5: prototype scope (streams 1-3)
    requires_attestation: bool
    description: str


STREAMS: list[Stream] = [
    Stream("access_review", 1, "Access review log", "Access", True, True,
           "Monthly snapshot of privileged roles, group owners, guests and stale accounts, attested by the Security Officer."),
    Stream("patch", 2, "Patch compliance log", "Patch", True, False,
           "Device compliance, OS/app update status and vulnerability exposure against E8 ML2 patch windows."),
    Stream("jml", 3, "Joiner / mover / leaver log", "JML", True, True,
           "Entra audit events reconciled against the HR list; late removals and orphan accounts flagged."),
    Stream("mfa", 4, "MFA & Conditional Access posture", "MFA", False, False,
           "Authentication-method coverage, admin MFA and Conditional Access policy state."),
    Stream("training", 5, "Security awareness training", "Training", False, False,
           "Completions from Attack Simulation Training / LMS export against the annual requirement."),
    Stream("visitors", 6, "Visitor log", "Visitors", False, False,
           "Forms / SharePoint visitor register: sign-out, ID check and escort completeness."),
    Stream("incidents", 7, "Incident register (ASR input)", "Incidents", False, False,
           "Security incidents and Defence reporting dates; rolled up with streams 1-6 into the ASR data pack."),
]

STREAMS_BY_ID = {s.stream_id: s for s in STREAMS}


CONTROLS: list[Control] = [
    Control("DISP-ACCESS-REVIEW", "Periodic access review", "DISP / DSPF", "DSPF Principle 16 (DISP membership obligations); ISM access control guidance",
            "access_review", "Privileged and standard access is reviewed and attested on a regular cycle."),
    Control("E8-ADMIN-ML2", "Restrict administrative privileges", "Essential Eight ML2", "E8 Maturity Model - Restrict administrative privileges, ML2",
            "access_review", "Privileged accounts are validated and disabled after 45 days of inactivity; admin count kept minimal."),
    Control("E8-PATCH-OS-ML2", "Patch operating systems", "Essential Eight ML2", "E8 Maturity Model - Patch operating systems, ML2",
            "patch", "OS patches applied within the ML2 timeframes; unsupported operating systems replaced."),
    Control("E8-PATCH-APP-ML2", "Patch applications", "Essential Eight ML2", "E8 Maturity Model - Patch applications, ML2",
            "patch", "Office, browser, email, PDF and security product patches within two weeks; other apps within one month."),
    Control("DISP-PERSONNEL-JML", "Personnel security - timely access removal", "DISP / DSPF", "DSPF personnel security; DISP ASR personnel-change reporting",
            "jml", "Leavers' access removed within the target window; every account maps to an HR record."),
    Control("E8-MFA-ML2", "Multi-factor authentication", "Essential Eight ML2", "E8 Maturity Model - Multi-factor authentication, ML2",
            "mfa", "MFA enforced for all users of online services and for privileged users; legacy auth blocked."),
    Control("DISP-TRAINING", "Security awareness training", "DISP / DSPF", "DISP membership obligation: annual security awareness training",
            "training", "All personnel complete security awareness training annually; new starters within 30 days."),
    Control("DISP-PHYSICAL-VISITORS", "Visitor management", "DISP / DSPF", "DSPF physical security (visitor control)",
            "visitors", "Visitors are identified, escorted where required, and signed out; register retained."),
    Control("DISP-INCIDENT-REPORTING", "Security incident reporting", "DISP / DSPF", "DISP member obligation to report security incidents to Defence",
            "incidents", "Reportable security incidents are logged and reported to Defence promptly."),
]

CONTROLS_BY_ID = {c.control_id: c for c in CONTROLS}


def controls_for_stream(stream_id: str) -> list[Control]:
    return [c for c in CONTROLS if c.stream == stream_id]
