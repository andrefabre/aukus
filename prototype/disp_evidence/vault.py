"""Immutable evidence store - local emulation of Azure Blob WORM storage.

Layout (one folder per monthly period):

  vault/<YYYY-MM>/<stream>/raw.json        raw source payload
  vault/<YYYY-MM>/<stream>/records.csv     normalised rows
  vault/<YYYY-MM>/<stream>/summary.json    status, metrics, exceptions
  vault/<YYYY-MM>/manifest.json            SHA-256 of every artifact + chain link
  vault/<YYYY-MM>/manifest.sig             Ed25519 signature over manifest.json
  vault/<YYYY-MM>/addenda/NNN-<kind>.json  signed, append-only additions after
                                           sealing (SO attestations, approved
                                           analysis), each bound to the manifest

Emulated WORM semantics: files are created exclusively ('xb') and set
read-only; a sealed period can never be sealed again; periods can only be sealed
in order so the hash chain (each manifest records the SHA-256 of the previous
month's manifest) stays linear. In Azure this maps to a container with a
time-based immutability policy + version-level immutability.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import shutil
import stat
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .keys import Signer
from .models import StreamResult


class VaultError(RuntimeError):
    pass


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def to_csv(rows: list[dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    if rows:
        cols: list[str] = []
        for r in rows:
            for k in r:
                if k not in cols:
                    cols.append(k)
        w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return buf.getvalue().encode("utf-8")


@dataclass
class VerifyReport:
    period: str
    ok: bool = True
    checks: list[dict[str, Any]] = field(default_factory=list)

    def add(self, check: str, ok: bool, detail: str = "") -> None:
        self.checks.append({"check": check, "ok": ok, "detail": detail})
        self.ok = self.ok and ok


class Vault:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.vault_dir
        self.root.mkdir(parents=True, exist_ok=True)
        self.signer = Signer(settings.keys_dir)

    # ---------------------------------------------------------------- paths
    def period_dir(self, period: str) -> Path:
        return self.root / period

    def periods(self) -> list[str]:
        return sorted(p.name for p in self.root.iterdir() if (p / "manifest.json").exists())

    def is_sealed(self, period: str) -> bool:
        return (self.period_dir(period) / "manifest.json").exists()

    # ---------------------------------------------------------------- write-once primitive
    @staticmethod
    def _write_once(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "xb") as f:
                f.write(data)
        except FileExistsError as e:
            raise VaultError(f"WORM violation: {path.name} already exists") from e
        os.chmod(path, stat.S_IREAD)

    # ---------------------------------------------------------------- seal
    def seal(self, period: str, results: list[StreamResult], as_of: datetime) -> dict[str, Any]:
        if self.is_sealed(period):
            raise VaultError(f"{period} is already sealed (immutable)")
        sealed = self.periods()
        if sealed and sealed[-1] > period:
            raise VaultError(f"cannot seal {period} after {sealed[-1]}: hash chain must stay in order")
        pdir = self.period_dir(period)
        if pdir.exists() and any(pdir.rglob("*")):
            raise VaultError(f"{period} has unsealed residue; refusing to overwrite")

        artifacts = []
        for r in results:
            summary = r.model_dump(mode="json", exclude={"raw", "records"})
            files = {"raw.json": json.dumps(r.raw, indent=1, default=str).encode("utf-8"),
                     "records.csv": to_csv(r.records),
                     "summary.json": json.dumps(summary, indent=1).encode("utf-8")}
            for name, data in files.items():
                self._write_once(pdir / r.stream / name, data)
                artifacts.append({"artifact_id": f"{period}/{r.stream}/{name}", "stream": r.stream, "file": name,
                                  "sha256": sha256(data), "bytes": len(data), "sources": r.sources,
                                  "collected_at": r.collected_at.isoformat()})

        prev = sealed[-1] if sealed else None
        sealed_at = datetime.now(timezone.utc)
        manifest = {
            "schema": "disp-evidence-manifest/1",
            "tenant": self.settings_tenant(),
            "period": period,
            "as_of": as_of.isoformat(),
            "sealed_at": sealed_at.isoformat(),
            "retain_until": (sealed_at + timedelta(days=365 * self.settings.policy.retention_years)).date().isoformat(),
            "key_id": self.signer.key_id,
            "prev_period": prev,
            "prev_manifest_sha256": self.manifest_sha256(prev) if prev else None,
            "artifacts": artifacts,
        }
        body = canonical(manifest)
        self._write_once(pdir / "manifest.json", body)
        self._write_once(pdir / "manifest.sig", base64.b64encode(self.signer.sign(body)))
        return manifest

    def settings_tenant(self) -> str:
        from .simulator import TENANT_NAME

        return os.environ.get("DISP_TENANT_NAME", TENANT_NAME)

    # ---------------------------------------------------------------- read
    def manifest(self, period: str) -> dict[str, Any]:
        return json.loads((self.period_dir(period) / "manifest.json").read_bytes())

    def manifest_sha256(self, period: str) -> str:
        return sha256((self.period_dir(period) / "manifest.json").read_bytes())

    def summary(self, period: str, stream: str) -> dict[str, Any]:
        return json.loads((self.period_dir(period) / stream / "summary.json").read_bytes())

    def summaries(self, period: str) -> dict[str, dict[str, Any]]:
        out = {}
        for a in self.manifest(period)["artifacts"]:
            if a["file"] == "summary.json":
                out[a["stream"]] = self.summary(period, a["stream"])
        return out

    def records(self, period: str, stream: str) -> list[dict[str, str]]:
        text = (self.period_dir(period) / stream / "records.csv").read_text(encoding="utf-8")
        return list(csv.DictReader(io.StringIO(text)))

    def artifact_path(self, artifact_id: str) -> Path:
        path = (self.root / artifact_id).resolve()
        if self.root.resolve() not in path.parents:
            raise VaultError("artifact id escapes the vault")
        return path

    # ---------------------------------------------------------------- addenda
    def add_addendum(self, period: str, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.is_sealed(period):
            raise VaultError(f"{period} is not sealed")
        adir = self.period_dir(period) / "addenda"
        existing = sorted(adir.glob("*.json")) if adir.exists() else []
        prev_hash = sha256(existing[-1].read_bytes()) if existing else None
        body = {"kind": kind, "period": period, "seq": len(existing) + 1, "manifest_sha256": self.manifest_sha256(period),
                "prev_addendum_sha256": prev_hash, "recorded_at": datetime.now(timezone.utc).isoformat(), "payload": payload}
        doc = {"body": body, "key_id": self.signer.key_id,
               "signature": base64.b64encode(self.signer.sign(canonical(body))).decode()}
        self._write_once(adir / f"{len(existing) + 1:03d}-{kind}.json", canonical(doc))
        return body

    def addenda(self, period: str, kind: str | None = None) -> list[dict[str, Any]]:
        adir = self.period_dir(period) / "addenda"
        if not adir.exists():
            return []
        out = [json.loads(p.read_bytes())["body"] for p in sorted(adir.glob("*.json"))]
        return [a for a in out if kind is None or a["kind"] == kind]

    # ---------------------------------------------------------------- verify
    def verify(self, period: str) -> VerifyReport:
        rep = VerifyReport(period)
        pdir = self.period_dir(period)
        try:
            body = (pdir / "manifest.json").read_bytes()
            sig = base64.b64decode((pdir / "manifest.sig").read_bytes())
        except FileNotFoundError as e:
            rep.add("manifest present", False, str(e))
            return rep
        rep.add("manifest signature (Ed25519, key " + self.signer.key_id + ")", self.signer.verify(sig, body),
                "signature valid" if self.signer.verify(sig, body) else "signature does not match manifest bytes")
        manifest = json.loads(body)
        bad = []
        for a in manifest["artifacts"]:
            path = pdir / a["stream"] / a["file"]
            actual = sha256(path.read_bytes()) if path.exists() else "missing"
            if actual != a["sha256"]:
                bad.append(f"{a['artifact_id']}: expected {a['sha256'][:12]}..., found {actual[:12]}...")
        rep.add(f"artifact hashes ({len(manifest['artifacts'])} files)", not bad, "; ".join(bad) or "all SHA-256 hashes match")
        prev = manifest.get("prev_period")
        if prev:
            actual_prev = self.manifest_sha256(prev) if self.is_sealed(prev) else "missing"
            ok = actual_prev == manifest["prev_manifest_sha256"]
            rep.add(f"hash chain link to {prev}", ok,
                    "previous manifest unchanged" if ok else f"{prev} manifest hash is {actual_prev[:12]}..., chain expects {manifest['prev_manifest_sha256'][:12]}...")
        else:
            rep.add("hash chain", True, "genesis period (no predecessor)")
        adir = pdir / "addenda"
        prev_hash = None
        for p in sorted(adir.glob("*.json")) if adir.exists() else []:
            doc = json.loads(p.read_bytes())
            ok_sig = self.signer.verify(base64.b64decode(doc["signature"]), canonical(doc["body"]))
            ok_bind = doc["body"]["manifest_sha256"] == sha256(body)
            ok_chain = doc["body"]["prev_addendum_sha256"] == prev_hash
            rep.add(f"addendum {p.name}", ok_sig and ok_bind and ok_chain,
                    "signed, bound to manifest, chained" if ok_sig and ok_bind and ok_chain else
                    f"signature {'ok' if ok_sig else 'INVALID'}, manifest binding {'ok' if ok_bind else 'BROKEN'}, chain {'ok' if ok_chain else 'BROKEN'}")
            prev_hash = sha256(p.read_bytes())
        return rep

    # ---------------------------------------------------------------- demo-only tamper simulation
    def _backup_path(self, period: str, stream: str) -> Path:
        return self.settings.data_dir / "tamper_backup" / period / stream / "records.csv"

    def tamper(self, period: str, stream: str) -> str:
        """Simulate an insider editing sealed evidence (bypassing the WORM API)."""
        path = self.period_dir(period) / stream / "records.csv"
        backup = self._backup_path(period, stream)
        if not backup.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, backup)
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > 1:
            lines[1] = lines[1].replace("True", "False").replace("LATE", "on time").replace("FAIL", "PASS") + " "
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.chmod(path, stat.S_IREAD)
        return f"edited first data row of {period}/{stream}/records.csv"

    def untamper(self, period: str, stream: str) -> bool:
        backup = self._backup_path(period, stream)
        if not backup.exists():
            return False
        path = self.period_dir(period) / stream / "records.csv"
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
        shutil.copyfile(backup, path)
        os.chmod(path, stat.S_IREAD)
        backup.unlink()
        return True

    def tampered(self) -> list[tuple[str, str]]:
        base = self.settings.data_dir / "tamper_backup"
        return [(p.parent.parent.name, p.parent.name) for p in base.glob("*/*/records.csv")] if base.exists() else []
