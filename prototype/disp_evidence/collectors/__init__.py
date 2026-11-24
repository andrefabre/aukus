"""Evidence collectors, one per stream. Deterministic: no LLM touches raw evidence."""

from __future__ import annotations

from typing import Callable

from . import access_review, incidents, jml, mfa, patch, training, visitors

COLLECTORS: dict[str, Callable] = {
    "access_review": access_review.collect,
    "patch": patch.collect,
    "jml": jml.collect,
    "mfa": mfa.collect,
    "training": training.collect,
    "visitors": visitors.collect,
    "incidents": incidents.collect,
}
