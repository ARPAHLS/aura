"""Tests for signed audit pack export and offline verification (#50)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aura import MapSecretBroker, SignedPackError, agent, verify_audit_pack


def test_signed_pack_hmac_export_and_verify(aura_home):
    ag = agent("signed-pack-hmac")
    with ag.session(
        export=True,
        signed_pack=True,
        signing_key="super-secret-hmac-key",
        key_id="ci-hmac-1",
    ) as run:
        run.emit("turn.start", {"input": "hello"})
        run.emit("turn.end", {"output": "world"})

    assert "pack" in run.exports
    pack_path = Path(run.exports["pack"])
    assert pack_path.is_file()
    assert any(e.kind == "export.signed_pack" for e in run.get_events())

    res = verify_audit_pack(pack_path, key="super-secret-hmac-key")
    assert res["valid"] is True
    assert res["algorithm"] == "hmac-sha256"
    assert res["key_id"] == "ci-hmac-1"
    assert res["errors"] == []

    # Wrong key must fail
    bad_key = verify_audit_pack(pack_path, key="wrong-key")
    assert bad_key["valid"] is False
    assert "Signature verification failed" in bad_key["errors"]

    # Tampering summary must fail
    summary_path = Path(run.exports["summary"])
    summary_data = json.loads(summary_path.read_text(encoding="utf-8"))
    summary_data["agent_name"] = "tampered"
    summary_path.write_text(json.dumps(summary_data), encoding="utf-8")
    tampered_sum = verify_audit_pack(pack_path, key="super-secret-hmac-key")
    assert tampered_sum["valid"] is False
    assert "Summary SHA-256 digest mismatch" in tampered_sum["errors"]


def test_signed_pack_missing_key_raises(aura_home, monkeypatch):
    monkeypatch.delenv("AURA_SIGNING_KEY", raising=False)
    ag = agent("signed-pack-nokey")
    with pytest.raises(SignedPackError):
        with ag.session(export=True, signed_pack=True) as run:
            run.emit("turn.start", {"input": "hi"})


def test_signed_pack_secret_broker_ref(aura_home):
    broker = MapSecretBroker({"env:PACK_SIGN_KEY": "broker-resolved-key-123"})
    ag = agent("signed-pack-broker")
    with ag.session(
        export=True,
        signed_pack=True,
        signing_key="env:PACK_SIGN_KEY",
        secret_broker=broker,
    ) as run:
        run.emit("turn.end", {"output": "ok"})

    res = verify_audit_pack(run.exports["pack"], key="broker-resolved-key-123")
    assert res["valid"] is True


def test_signed_pack_ed25519_when_cryptography_installed(aura_home):
    cryptography = pytest.importorskip("cryptography")
    assert cryptography is not None
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    priv = Ed25519PrivateKey.generate()
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    ag = agent("signed-pack-ed25519")
    with ag.session(
        export=True,
        signed_pack=True,
        signing_key=priv_pem,
        signing_algorithm="ed25519",
        key_id="ed-key-1",
    ) as run:
        run.emit("turn.end", {"output": "signed"})

    res = verify_audit_pack(run.exports["pack"], key=pub_pem)
    assert res["valid"] is True
    assert res["algorithm"] == "ed25519"


def test_cli_verify_pack(run_aura, aura_home):
    ag = agent("cli-verify-pack")
    with ag.session(export=True, signed_pack=True, signing_key="cli-pack-secret") as run:
        run.emit("turn.end", {"output": "done"})

    ok = run_aura("verify", "pack", run.exports["pack"], "--key", "cli-pack-secret")
    assert ok.returncode == 0
    assert json.loads(ok.stdout)["valid"] is True

    bad = run_aura("verify", "pack", run.exports["pack"], "--key", "bad-secret")
    assert bad.returncode == 1
    assert json.loads(bad.stdout)["valid"] is False
