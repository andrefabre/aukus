"""End-to-end: demo setup -> every page renders -> sign-off -> analysis -> packs -> tamper -> live cycle."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from disp_evidence.cli import demo_setup


@pytest.fixture()
def client(settings, monkeypatch):
    monkeypatch.setenv("DISP_DATA_DIR", str(settings.data_dir))
    monkeypatch.setenv("DISP_TODAY", "2026-11-24")
    done = demo_setup(settings)
    assert done == ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
    from disp_evidence.web.app import app

    return TestClient(app)


def test_pages_render(client):
    for url in ["/", "/month/2026-10", "/month/2026-10/stream/jml", "/month/2026-10/stream/patch", "/month/2026-10/analysis",
                "/vault", "/asr", "/connectors", "/about"]:
        r = client.get(url)
        assert r.status_code == 200, url
    assert "Leaver account still enabled" in client.get("/month/2026-10/stream/jml").text


def test_signoff_analysis_and_packs(client):
    r = client.post("/month/2026-10/stream/jml/attest", data={"decision": "approved_with_comments", "comment": "Orphan account disabled today"})
    assert r.status_code == 200 and "Attestation #1 sealed" in r.text
    r = client.post("/month/2026-10/stream/jml/attest", data={"decision": "rejected", "comment": ""})
    assert "comment is required" in r.text
    r = client.post("/month/2026-10/analysis/run", data={"engine": "rules"})
    assert "gate PASSED" in r.text
    r = client.post("/month/2026-10/analysis/approve", data={"comment": "ok"})
    assert "approved" in r.text.lower()
    pdf = client.get("/pack/2026-10.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    j = client.get("/pack/2026-10.json").json()
    assert j["verification"]["ok"] and j["analysis"]["status"] == "APPROVED BY SO"
    assert client.get("/asr.pdf").content.startswith(b"%PDF")


def test_unavailable_paid_engine_is_refused(client, monkeypatch):
    monkeypatch.delenv("DISP_ENABLE_PAID_LLM", raising=False)
    r = client.post("/month/2026-10/analysis/run", data={"engine": "claude"})
    assert "Paid option, off by default" in r.text


def test_tamper_flow_and_live_cycle(client):
    r = client.post("/vault/tamper", data={"period": "2026-08", "stream": "jml"})
    assert "FAILED" in r.text
    r = client.post("/vault/untamper", data={"period": "2026-08", "stream": "jml"})
    assert "FAILED" not in r.text
    r = client.post("/run")
    assert "Monthly cycle ran" in r.text and "2026-10" in r.text
    r = client.post("/run")
    assert "already sealed" in r.text


def test_artifact_path_traversal_blocked(client):
    assert client.get("/artifact", params={"id": "../keys/signing_key.pem"}).status_code == 400


def test_faulty_llm_demo_is_blocked_by_gate(client):
    r = client.post("/month/2026-10/analysis/run", data={"engine": "faulty-llm-demo"})
    assert "gate FAILED" in r.text and "Overclaim" in r.text and "access-control-policy-v3.pdf" in r.text
    r = client.post("/month/2026-10/analysis/approve", data={"comment": ""})
    assert "cannot be approved" in r.text
