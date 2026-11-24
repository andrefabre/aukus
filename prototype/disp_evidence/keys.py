"""Signing key - local stand-in for an Azure Key Vault key.

In production the private key never leaves Key Vault (the Function calls the
Key Vault `sign` operation with its managed identity). Locally we keep an
Ed25519 key on disk so the demo is free and offline.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


class Signer:
    def __init__(self, keys_dir: Path):
        keys_dir.mkdir(parents=True, exist_ok=True)
        path = keys_dir / "signing_key.pem"
        if path.exists():
            key = serialization.load_pem_private_key(path.read_bytes(), password=None)
            assert isinstance(key, Ed25519PrivateKey)
        else:
            key = Ed25519PrivateKey.generate()
            path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
        self._key = key
        self.public_key: Ed25519PublicKey = key.public_key()
        raw = self.public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.key_id = hashlib.sha256(raw).hexdigest()[:16]
        (keys_dir / "signing_key.pub.pem").write_bytes(
            self.public_key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))

    def sign(self, data: bytes) -> bytes:
        return self._key.sign(data)

    def verify(self, signature: bytes, data: bytes) -> bool:
        try:
            self.public_key.verify(signature, data)
            return True
        except InvalidSignature:
            return False
