"""Optional LLM engines. Both see only the minimised evidence digest, never raw
evidence or personal identifiers, and both are gated by `gate.run_gate`.

* Ollama (local, $0): needs Ollama running on this laptop with a pulled model.
  `ollama pull llama3.2` (~2 GB). DISP_OLLAMA_MODEL / DISP_OLLAMA_URL to change.
* Claude (hosted, PAID per token): disabled unless BOTH the `anthropic` package
  is installed AND DISP_ENABLE_PAID_LLM=1 is set, plus Anthropic credentials
  (ANTHROPIC_API_KEY or an `ant auth login` profile). Off by default.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from ..models import CompliancePackDraft

SYSTEM_PROMPT = (
    "You are a compliance evidence analyst assisting the Security Officer of a small Australian defence supplier "
    "preparing for DISP assurance. You are given a digest of sealed monthly evidence, one entry per control. "
    "For each control produce an assessment with status COMPLIANT, PARTIAL, GAP or STALE. Base every judgement only "
    "on the digest. cited_artifact_ids must be copied exactly from that control's evidence_artifacts; never invent ids. "
    "Any critical or high exception means GAP; medium-only means PARTIAL. If evidence is missing, use GAP. "
    "Write a concise rationale (1-2 sentences) and a concrete recommended_action. "
    "List open questions the Security Officer must answer. requires_human_signoff must be true. "
    "You do not certify compliance; you draft for human review."
)


def _user_prompt(period: str, digest: list[dict[str, Any]]) -> str:
    return (f"Period: {period}\nEvidence digest (JSON):\n{json.dumps(digest, indent=1, default=str)}\n\n"
            f"Return a CompliancePackDraft with pack_title 'Control assessment {period}', "
            f"generated_at_utc '{datetime.now(timezone.utc).isoformat()}', and one assessment per control_id above.")


# --------------------------------------------------------------------- Ollama
def ollama_status() -> tuple[bool, str]:
    url = os.environ.get("DISP_OLLAMA_URL", "http://localhost:11434")
    model = os.environ.get("DISP_OLLAMA_MODEL", "llama3.2")
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=1.5) as r:
            tags = [m["name"] for m in json.load(r).get("models", [])]
    except (urllib.error.URLError, OSError, ValueError):
        return False, "Ollama not running on this laptop (free option: install from ollama.com, then `ollama pull llama3.2`)."
    if not any(t == model or t.startswith(model + ":") for t in tags):
        return False, f"Ollama is running but model '{model}' is not pulled (`ollama pull {model}`)."
    return True, f"Local model '{model}' via Ollama ($0, data stays on this laptop)."


def analyse_ollama(period: str, digest: list[dict[str, Any]]) -> CompliancePackDraft:
    url = os.environ.get("DISP_OLLAMA_URL", "http://localhost:11434")
    model = os.environ.get("DISP_OLLAMA_MODEL", "llama3.2")
    body = {"model": model, "stream": False, "format": CompliancePackDraft.model_json_schema(),
            "options": {"temperature": 0},
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": _user_prompt(period, digest)}]}
    req = urllib.request.Request(f"{url}/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        content = json.load(r)["message"]["content"]
    draft = CompliancePackDraft.model_validate_json(content)
    draft.engine = f"ollama:{model} (local)"
    return draft


# --------------------------------------------------------------------- Claude (paid, opt-in)
def claude_status() -> tuple[bool, str]:
    if os.environ.get("DISP_ENABLE_PAID_LLM") != "1":
        return False, "Paid option, off by default. Set DISP_ENABLE_PAID_LLM=1 and Anthropic credentials to enable (billed per token)."
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False, "Install the optional package: pip install -e .[claude]"
    return True, f"Claude ({os.environ.get('DISP_CLAUDE_MODEL', 'claude-opus-5-5')}) - PAID, sends the minimised digest only."


def analyse_claude(period: str, digest: list[dict[str, Any]]) -> CompliancePackDraft:
    import anthropic

    model = os.environ.get("DISP_CLAUDE_MODEL", "claude-opus-5-5")
    client = anthropic.Anthropic()
    response = client.beta.messages.parse(
        model=model,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",   # server-side refusal fallback
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _user_prompt(period, digest)}],
        output_format=CompliancePackDraft,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined the request (stop_reason=refusal).")
    draft = response.parsed_output
    if draft is None:
        raise RuntimeError(f"No structured output returned (stop_reason={response.stop_reason}).")
    draft.engine = f"claude:{response.model} (hosted, paid)"
    return draft
