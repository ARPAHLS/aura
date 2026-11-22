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


def _looks_like_secret_ref(value: str) -> bool:
    """Return True for SecretBroker-style prefixed refs like ``env:NAME`` (not ``C:\\...``)."""
    colon = value.find(":")
    return colon > 1 and value[:colon].replace("_", "").replace("-", "").isalnum()


def _resolve_keyring_file_path(raw_val: str, base_dir: Path) -> Path | None:
    """Return existing key file path if ``raw_val`` points to a file, else None."""
    if (
        not raw_val
        or "\n" in raw_val
        or "\r" in raw_val
        or "\x00" in raw_val
        or "-----BEGIN " in raw_val
        or _looks_like_secret_ref(raw_val)
    ):
        return None
    candidate = Path(raw_val)
    try:
        if candidate.is_absolute():
            return candidate if candidate.is_file() else None
        rel_candidate = base_dir / candidate
        if rel_candidate.is_file():
            return rel_candidate
        if candidate.is_file():
            return candidate
    except OSError:
        return None
    return None


def load_keyring(keyring_path: str | Path) -> dict[str, str | bytes]:
    """Load a JSON keyring mapping ``key_id`` to secret/PEM string or key file path."""
    path = Path(keyring_path)
    if not path.is_file():
        raise FileNotFoundError(f"Keyring file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SignedPackError(f"Invalid JSON in keyring {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise SignedPackError(f"Keyring file must be a JSON object mapping key_id to key: {path}")

    base_dir = path.parent
    keyring: dict[str, str | bytes] = {}
    for raw_id, raw_val in data.items():
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise SignedPackError("Keyring keys must be non-empty strings")
        if not isinstance(raw_val, str):
            raise SignedPackError(f"Keyring entry for {raw_id!r} must be a string")
        if not raw_val.strip():
            raise SignedPackError(f"Keyring entry for {raw_id!r} must not be empty")

        key_file = _resolve_keyring_file_path(raw_val, base_dir)
        if key_file is not None:
            key_bytes = key_file.read_bytes()
            if not key_bytes:
                raise SignedPackError(f"Key file for {raw_id!r} is empty: {key_file}")
            keyring[raw_id] = key_bytes
        else:
            keyring[raw_id] = raw_val
    return keyring


def _resolve_verification_key(
    pack: Mapping[str, Any],
    *,
    key: str | bytes | None = None,
    keyring: Mapping[str, str | bytes] | None = None,
    secret_broker: Any = None,
) -> bytes:
    """Resolve verification key bytes from ``keyring`` by ``pack['key_id']`` or single ``key``."""
    if keyring is None:
        return resolve_signing_key(key, secret_broker=secret_broker)

    if key is not None:
        raise SignedPackError("Cannot specify both key and keyring")
    if not isinstance(keyring, Mapping):
        raise SignedPackError("Keyring must be a mapping of key_id to verification key")

    raw_key_id = pack.get("key_id")
    if not isinstance(raw_key_id, str) or not raw_key_id.strip():
        raise SignedPackError("Pack is missing key_id for keyring lookup")
    if raw_key_id not in keyring:
        raise SignedPackError(f"Unknown key_id {raw_key_id!r}: not found in keyring")

    entry = keyring[raw_key_id]
    if isinstance(entry, bytes):
        if not entry:
            raise SignedPackError(f"Empty verification key in keyring for key_id {raw_key_id!r}")
        return entry
    if not isinstance(entry, str):
        raise SignedPackError(f"Invalid verification key type in keyring for key_id {raw_key_id!r}")
    if not entry.strip():
        raise SignedPackError(f"Empty verification key in keyring for key_id {raw_key_id!r}")
    return resolve_signing_key(entry, secret_broker=secret_broker)


def verify_audit_pack(
    pack_path: str | Path,
    *,
    key: str | bytes | None = None,
    keyring: Mapping[str, str | bytes] | None = None,
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
    raw_sig = pack.get("signature")
    signature = raw_sig if isinstance(raw_sig, str) else ""
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

    if key is not None and keyring is not None:
        errors.append("Cannot specify both key and keyring")
    elif raw_sig is not None and not isinstance(raw_sig, str):
        errors.append("Pack signature must be a string")
    elif not signature:
        errors.append("Missing pack signature")
    else:
        try:
            key_bytes = _resolve_verification_key(
                pack,
                key=key,
                keyring=keyring,
                secret_broker=secret_broker,
            )
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
