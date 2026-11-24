from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone

import pytest

from disp_evidence.models import Attestation, StreamResult
from disp_evidence.vault import Vault, VaultError


def _result(stream: str, period: str) -> StreamResult:
    now = datetime(2026, 10, 31, tzinfo=timezone.utc)
    return StreamResult(stream=stream, period=period, as_of=now, collected_at=now, control_ids=["X"], sources=["test"],
                        status="PASS", headline="h", metrics={"a": 1}, records=[{"k": "v", "n": 1}], raw={"raw": [1, 2]},
                        exceptions=[])


def test_seal_writes_manifest_with_hashes_and_signature(settings):
    v = Vault(settings)
    manifest = v.seal("2026-09", [_result("patch", "2026-09")], as_of=datetime(2026, 9, 30, tzinfo=timezone.utc))
    ids = [a["artifact_id"] for a in manifest["artifacts"]]
    assert "2026-09/patch/raw.json" in ids and "2026-09/patch/records.csv" in ids
    assert all(len(a["sha256"]) == 64 for a in manifest["artifacts"])
    assert manifest["prev_manifest_sha256"] is None
    assert v.verify("2026-09").ok


def test_sealed_files_are_write_once(settings):
    v = Vault(settings)
    v.seal("2026-09", [_result("patch", "2026-09")], as_of=datetime(2026, 9, 30, tzinfo=timezone.utc))
    path = v.period_dir("2026-09") / "patch" / "records.csv"
    assert not os.stat(path).st_mode & stat.S_IWRITE
    with pytest.raises(VaultError):
        v.seal("2026-09", [_result("patch", "2026-09")], as_of=datetime(2026, 9, 30, tzinfo=timezone.utc))


def test_hash_chain_links_months_and_rejects_out_of_order(settings):
    v = Vault(settings)
    m9 = v.seal("2026-09", [_result("patch", "2026-09")], as_of=datetime(2026, 9, 30, tzinfo=timezone.utc))
    m10 = v.seal("2026-10", [_result("patch", "2026-10")], as_of=datetime(2026, 10, 31, tzinfo=timezone.utc))
    assert m10["prev_period"] == "2026-09"
    assert m10["prev_manifest_sha256"] == v.manifest_sha256("2026-09")
    assert m9["period"] == "2026-09"
    with pytest.raises(VaultError):
        v.seal("2026-08", [_result("patch", "2026-08")], as_of=datetime(2026, 8, 31, tzinfo=timezone.utc))


def test_tamper_is_detected_and_breaks_nothing_else(settings):
    v = Vault(settings)
    v.seal("2026-09", [_result("patch", "2026-09")], as_of=datetime(2026, 9, 30, tzinfo=timezone.utc))
    v.seal("2026-10", [_result("patch", "2026-10")], as_of=datetime(2026, 10, 31, tzinfo=timezone.utc))
    v.tamper("2026-09", "patch")
    report = v.verify("2026-09")
    assert not report.ok
    assert any("records.csv" in c["detail"] for c in report.checks if not c["ok"])
    assert v.verify("2026-10").ok          # chain still verifies: the manifest itself was not touched
    v.untamper("2026-09", "patch")
    assert v.verify("2026-09").ok


def test_manifest_edit_breaks_signature_and_chain(settings):
    v = Vault(settings)
    v.seal("2026-09", [_result("patch", "2026-09")], as_of=datetime(2026, 9, 30, tzinfo=timezone.utc))
    v.seal("2026-10", [_result("patch", "2026-10")], as_of=datetime(2026, 10, 31, tzinfo=timezone.utc))
    path = v.period_dir("2026-09") / "manifest.json"
    os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    data = json.loads(path.read_text())
    data["artifacts"][0]["sha256"] = "0" * 64
    path.write_text(json.dumps(data))
    assert not v.verify("2026-09").ok
    assert not v.verify("2026-10").ok      # next month's chain link no longer matches


def test_attestation_is_appended_signed_and_bound_to_manifest(settings):
    v = Vault(settings)
    v.seal("2026-09", [_result("patch", "2026-09")], as_of=datetime(2026, 9, 30, tzinfo=timezone.utc))
    att = Attestation(period="2026-09", subject="patch", decision="approved", signed_by="Riley Okafor",
                      signed_at=datetime(2026, 10, 2, tzinfo=timezone.utc), manifest_sha256=v.manifest_sha256("2026-09"))
    v.add_addendum("2026-09", "attestation", att.model_dump(mode="json"))
    adds = v.addenda("2026-09")
    assert adds[0]["kind"] == "attestation" and adds[0]["payload"]["signed_by"] == "Riley Okafor"
    assert v.verify("2026-09").ok
