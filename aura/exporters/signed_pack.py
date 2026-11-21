"""Signed audit pack export and offline verification (#50)."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Mapping
import uuid

from aura.core.spine import AuditSpine, verify_hash_chain


class SignedPackError(RuntimeError):
    """Raised when signed audit pack creation or key resolution fails."""


def sha256_file(path: Path) -> str:
    """Return hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_pack_body(payload: Mapping[str, Any]) -> bytes:
    """Canonical JSON bytes over pack metadata (excluding signature)."""
    body = {k: v for k, v in payload.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def resolve_signing_key(
    key: str | bytes | None = None,
    *,
    secret_broker: Any = None,
) -> bytes:
    """Resolve signing key from explicit value, SecretBroker ref, or AURA_SIGNING_KEY."""
    if isinstance(key, bytes):
        if not key:
            raise SignedPackError("Signing key bytes must not be empty")
        return key
    raw = str(key).strip() if key is not None else ""
    if not raw:
        raw = os.environ.get("AURA_SIGNING_KEY", "").strip()
    if not raw:
        raise SignedPackError(
            "Signed audit pack requested but no signing key provided "
            "(pass signing_key=... or set AURA_SIGNING_KEY)"
        )
    if ":" in raw:
        broker = secret_broker
        if broker is None:
            from aura.core.secrets import default_secret_broker

            broker = default_secret_broker()
        try:
            resolved = broker.resolve(raw)
            if resolved:
                return str(resolved).encode("utf-8")
        except Exception:
            pass
    return raw.encode("utf-8")


def _sign_bytes(data: bytes, key_bytes: bytes, algorithm: str) -> str:
    alg = algorithm.strip().lower()
    if alg == "hmac-sha256":
        return hmac.new(key_bytes, data, hashlib.sha256).hexdigest()
    if alg == "ed25519":
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from cryptography.hazmat.primitives.serialization import load_pem_private_key
        except ImportError as exc:
            raise SignedPackError("ed25519 signing requires cryptography package") from exc
        if b"BEGIN " in key_bytes:
            priv = load_pem_private_key(key_bytes, password=None)
            if not isinstance(priv, Ed25519PrivateKey):
                raise SignedPackError("PEM key is not an Ed25519 private key")
        else:
            if len(key_bytes) != 32:
                raise SignedPackError("Raw Ed25519 private key must be 32 bytes")
            priv = Ed25519PrivateKey.from_private_bytes(key_bytes)
        return priv.sign(data).hex()
    raise SignedPackError(f"Unsupported signing algorithm: {algorithm!r}")


def _verify_signature(data: bytes, signature: str, key_bytes: bytes, algorithm: str) -> bool:
    alg = algorithm.strip().lower()
    if alg == "hmac-sha256":
        expected = hmac.new(key_bytes, data, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
    if alg == "ed25519":
        try:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PrivateKey,
                Ed25519PublicKey,
            )
            from cryptography.hazmat.primitives.serialization import (
                load_pem_private_key,
                load_pem_public_key,
            )
        except ImportError:
            return False
        try:
            sig_bytes = bytes.fromhex(signature)
            if b"BEGIN PUBLIC KEY" in key_bytes:
                pub = load_pem_public_key(key_bytes)
                if not isinstance(pub, Ed25519PublicKey):
                    return False
            elif b"BEGIN " in key_bytes:
                priv = load_pem_private_key(key_bytes, password=None)
                if not isinstance(priv, Ed25519PrivateKey):
                    return False
                pub = priv.public_key()
            elif len(key_bytes) == 32:
                pub = Ed25519PublicKey.from_public_bytes(key_bytes)
            else:
                return False
            pub.verify(sig_bytes, data)
            return True
        except (ValueError, InvalidSignature):
            return False
    return False


def build_signed_pack(
    *,
    session_id: str,
    jsonl_path: Path,
    summary_path: Path,
    otel_path: Path | None = None,
    signing_key: str | bytes | None = None,
    algorithm: str = "hmac-sha256",
    key_id: str | None = None,
    secret_broker: Any = None,
) -> dict[str, Any]:
    """Build a signed audit pack manifest dict covering exported session artifacts."""
    key_bytes = resolve_signing_key(signing_key, secret_broker=secret_broker)
    spine = AuditSpine.from_jsonl(jsonl_path)
    events = spine.stream()
    chain_root = events[-1].content_hash if events else None

    artifacts: dict[str, str] = {
        "jsonl": jsonl_path.name,
        "summary": summary_path.name,
    }
    digests: dict[str, str] = {
        "jsonl_sha256": sha256_file(jsonl_path),
        "summary_sha256": sha256_file(summary_path),
    }
    if otel_path is not None and otel_path.is_file():
        artifacts["otel"] = otel_path.name
        digests["otel_sha256"] = sha256_file(otel_path)

    pack: dict[str, Any] = {
        "pack_version": "1",
        "session_id": session_id,
        "signed_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": algorithm.strip().lower(),
        "key_id": key_id or "default",
        "chain_root": chain_root,
        "event_count": len(events),
        "artifacts": artifacts,
        "digests": digests,
    }
    pack["signature"] = _sign_bytes(canonical_pack_body(pack), key_bytes, pack["algorithm"])
    return pack


def write_signed_pack_atomic(pack: Mapping[str, Any], out_path: Path) -> Path:
    """Write ``.pack.json`` atomically via a staging file."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    staging = out_path.parent / f"{out_path.name}.{uuid.uuid4().hex}.staging"
    try:
        staging.write_text(json.dumps(dict(pack), indent=2), encoding="utf-8")
        staging.replace(out_path)
    except Exception:
        staging.unlink(missing_ok=True)
        raise
    return out_path


def verify_audit_pack(
    pack_path: str | Path,
    *,
    key: str | bytes | None = None,
    secret_broker: Any = None,
) -> dict[str, Any]:
    """Verify a ``.pack.json`` manifest, artifact SHA-256 digests, hash chain, and signature."""
    path = Path(pack_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audit pack not found: {path}")

    errors: list[str] = []
    try:
        pack = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"valid": False, "errors": [f"Invalid JSON in pack: {exc}"]}

    if not isinstance(pack, dict):
        return {"valid": False, "errors": ["Pack manifest must be a JSON object"]}

    session_id = str(pack.get("session_id") or "")
    algorithm = str(pack.get("algorithm") or "hmac-sha256")
    signature = str(pack.get("signature") or "")
    artifacts = pack.get("artifacts") if isinstance(pack.get("artifacts"), dict) else {}
    digests = pack.get("digests") if isinstance(pack.get("digests"), dict) else {}
    base_dir = path.parent

    jsonl_name = artifacts.get("jsonl")
    summary_name = artifacts.get("summary")
    jsonl_path = base_dir / str(jsonl_name) if jsonl_name else None
    summary_path = base_dir / str(summary_name) if summary_name else None

    if not jsonl_path or not jsonl_path.is_file():
        errors.append(f"Missing JSONL artifact: {jsonl_name}")
    elif sha256_file(jsonl_path) != digests.get("jsonl_sha256"):
        errors.append("JSONL SHA-256 digest mismatch")

    if not summary_path or not summary_path.is_file():
        errors.append(f"Missing summary artifact: {summary_name}")
    elif sha256_file(summary_path) != digests.get("summary_sha256"):
        errors.append("Summary SHA-256 digest mismatch")

    otel_name = artifacts.get("otel")
    if otel_name:
        otel_path = base_dir / str(otel_name)
        if not otel_path.is_file():
            errors.append(f"Missing OTel artifact: {otel_name}")
        elif sha256_file(otel_path) != digests.get("otel_sha256"):
            errors.append("OTel SHA-256 digest mismatch")

    if jsonl_path and jsonl_path.is_file():
        try:
            spine = AuditSpine.from_jsonl(jsonl_path)
            if verify_hash_chain(spine) is False:
                errors.append("JSONL hash chain verification failed")
            events = spine.stream()
            actual_root = events[-1].content_hash if events else None
            if actual_root != pack.get("chain_root"):
                errors.append("chain_root does not match tail content_hash")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"Malformed JSONL event: {exc}")

    if not signature:
        errors.append("Missing pack signature")
    else:
        try:
            key_bytes = resolve_signing_key(key, secret_broker=secret_broker)
            if not _verify_signature(canonical_pack_body(pack), signature, key_bytes, algorithm):
                errors.append("Signature verification failed")
        except SignedPackError as exc:
            errors.append(str(exc))

    return {
        "valid": len(errors) == 0,
        "session_id": session_id,
        "algorithm": algorithm,
        "key_id": pack.get("key_id"),
        "chain_root": pack.get("chain_root"),
        "errors": errors,
    }

