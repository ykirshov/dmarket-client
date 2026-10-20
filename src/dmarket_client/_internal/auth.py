"""DMarket Ed25519 authentication; the signer has no network behavior."""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
from nacl.bindings import crypto_sign
from nacl.signing import SigningKey

from dmarket_client.exceptions import ConfigurationError


@dataclass(frozen=True, repr=False)
class Signer:
    public_key: str
    _secret: bytes = field(repr=False)
    clock: Callable[[], float] = field(default=time.time, repr=False)

    @classmethod
    def from_hex(
        cls,
        public_key: str,
        secret_key: str,
        *,
        secret_key_is_seed: bool = False,
        clock: Callable[[], float] = time.time,
    ) -> Signer:
        size = 64 if secret_key_is_seed else 128
        if not re.fullmatch(r"[0-9a-fA-F]{64}", public_key):
            raise ConfigurationError("public_key must contain 64 hexadecimal characters")
        if not re.fullmatch(rf"[0-9a-fA-F]{{{size}}}", secret_key):
            raise ConfigurationError(f"secret_key must contain {size} hexadecimal characters")
        raw = bytes.fromhex(secret_key)
        key = SigningKey(raw[:32])
        derived = bytes(key.verify_key)
        if derived != bytes.fromhex(public_key):
            raise ConfigurationError("Public and secret keys do not form an Ed25519 keypair")
        if not secret_key_is_seed and raw[32:] != derived:
            raise ConfigurationError("The 64-byte secret must be an Ed25519 seed + public key")
        return cls(public_key.lower(), raw[:32] + derived, clock)

    def headers(self, method: str, url: httpx.URL, body: bytes) -> dict[str, str]:
        # URL.path is decoded; URL.query is the actual encoded query. Decode only once.
        query = b"?" + url.query if url.query else b""
        timestamp = str(int(self.clock()))
        message = (
            method.upper().encode("ascii")
            + url.path.encode("utf-8")
            + query
            + body
            + timestamp.encode("ascii")
        )
        signature = crypto_sign(message, self._secret)[:64].hex()
        return {
            "X-Api-Key": self.public_key,
            "X-Sign-Date": timestamp,
            "X-Request-Sign": "dmar ed25519 " + signature,
        }
