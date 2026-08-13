"""Certificate schema: exact float encoding, canonical form, content addressing.

Design rules
------------
1. Floats are stored as C99 hex literals (``float.hex``), so a certificate
   round-trips bit-exactly. Decimal text would silently perturb the very
   quantities whose last bits the checker is reasoning about.
2. The certificate is content-addressed: ``content_hash`` is a BLAKE2b digest
   over the canonical JSON of everything except the hash field itself.
3. The operator is *referenced by hash*, not embedded. A checker handed a
   different operator than the producer used cannot be tricked into validating
   the claim against it. Encodings live in `operators.py`.
4. The witness is minimal. It carries the eigenvector estimate and the gap
   parameter and nothing else -- in particular it does NOT carry the producer's
   Rayleigh quotient or residual norm, because the checker recomputes those
   and must have no opportunity to reuse an untrusted number.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

SCHEMA_VERSION = "certkit/1"


class SchemaError(Exception):
    """Malformed certificate. Always an ABSTAIN, never a warning."""


# -- exact float <-> text -------------------------------------------------
def f2h(x: float) -> str:
    x = float(x)
    if not math.isfinite(x):
        raise SchemaError("non-finite float in certificate")
    return x.hex()


def h2f(s: str) -> float:
    if not isinstance(s, str):
        raise SchemaError(f"expected hex float string, got {type(s).__name__}")
    try:
        x = float.fromhex(s)
    except ValueError as exc:
        raise SchemaError(f"bad hex float {s!r}") from exc
    if not math.isfinite(x):
        raise SchemaError("non-finite float in certificate")
    return x


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(obj: Any) -> str:
    return hashlib.blake2b(canonical(obj).encode("utf-8"), digest_size=16).hexdigest()


# -- certificate ----------------------------------------------------------
def seal(cert: dict) -> dict:
    """Attach the content hash. Any later mutation invalidates it."""
    body = {k: v for k, v in cert.items() if k != "content_hash"}
    cert = dict(body)
    cert["content_hash"] = "blake2b16:" + digest(body)
    return cert


def verify_seal(cert: Any) -> None:
    if not isinstance(cert, dict):
        raise SchemaError("certificate is not an object")
    got = cert.get("content_hash")
    body = {k: v for k, v in cert.items() if k != "content_hash"}
    want = "blake2b16:" + digest(body)
    if got != want:
        raise SchemaError("content hash mismatch: certificate was modified")


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise SchemaError(msg)
