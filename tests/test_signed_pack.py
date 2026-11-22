"""Tests for signed audit pack export and offline verification (#50)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aura import MapSecretBroker, SignedPackError, agent, verify_audit_pack
from aura.exporters.signed_pack import load_keyring


def _generate_ed25519_keypair():
    pytest.importorskip("cryptography")
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
    return priv_pem, pub_pem


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
    priv_pem, pub_pem = _generate_ed25519_keypair()

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


def test_signed_pack_keyring_hmac_rotation(aura_home, monkeypatch):
    monkeypatch.setenv("AURA_SIGNING_KEY", "env-fallback-should-not-be-used")
    ag = agent("signed-pack-keyring-hmac")

    with ag.session(
        export=True,
        signed_pack=True,
        signing_key="rotated-secret-v1",
        key_id="hmac-v1",
    ) as run_v1:
        run_v1.emit("turn.end", {"version": 1})

    with ag.session(
        export=True,
        signed_pack=True,
        signing_key="rotated-secret-v2",
        key_id="hmac-v2",
    ) as run_v2:
        run_v2.emit("turn.end", {"version": 2})

    keyring = {
        "hmac-v1": "rotated-secret-v1",
        "hmac-v2": b"rotated-secret-v2",
    }

    res_v1 = verify_audit_pack(run_v1.exports["pack"], keyring=keyring)
    assert res_v1["valid"] is True
    assert res_v1["key_id"] == "hmac-v1"
    assert res_v1["errors"] == []

    res_v2 = verify_audit_pack(run_v2.exports["pack"], keyring=keyring)
    assert res_v2["valid"] is True
    assert res_v2["key_id"] == "hmac-v2"
    assert res_v2["errors"] == []


def test_signed_pack_keyring_ed25519_rotation(aura_home):
    priv_v1, pub_v1 = _generate_ed25519_keypair()
    priv_v2, pub_v2 = _generate_ed25519_keypair()

    ag = agent("signed-pack-keyring-ed25519")
    with ag.session(
        export=True,
        signed_pack=True,
        signing_key=priv_v1,
        signing_algorithm="ed25519",
        key_id="ed-2025",
    ) as run_v1:
        run_v1.emit("turn.end", {"key": "2025"})

    with ag.session(
        export=True,
        signed_pack=True,
        signing_key=priv_v2,
        signing_algorithm="ed25519",
        key_id="ed-2026",
    ) as run_v2:
        run_v2.emit("turn.end", {"key": "2026"})

    keyring = {
        "ed-2025": pub_v1.decode("utf-8"),
        "ed-2026": pub_v2,
    }

    res_v1 = verify_audit_pack(run_v1.exports["pack"], keyring=keyring)
    assert res_v1["valid"] is True
    assert res_v1["key_id"] == "ed-2025"

    res_v2 = verify_audit_pack(run_v2.exports["pack"], keyring=keyring)
    assert res_v2["valid"] is True
    assert res_v2["key_id"] == "ed-2026"


def test_signed_pack_keyring_secret_broker_and_env_fallback_preserved(aura_home, monkeypatch):
    ag = agent("signed-pack-env-and-broker")
    with ag.session(
        export=True,
        signed_pack=True,
        signing_key="env-secret-value",
        key_id="env-kid",
    ) as run:
        run.emit("turn.end", {"ok": True})

    # Existing single-key and AURA_SIGNING_KEY fallback remain unchanged when keyring is omitted
    monkeypatch.setenv("AURA_SIGNING_KEY", "env-secret-value")
    assert verify_audit_pack(run.exports["pack"])["valid"] is True
    assert verify_audit_pack(run.exports["pack"], key="env-secret-value")["valid"] is True

    # SecretBroker refs inside a keyring also resolve cleanly
    broker = MapSecretBroker({"env:ROTATED_KEY": "env-secret-value"})
    res_broker = verify_audit_pack(
        run.exports["pack"],
        keyring={"env-kid": "env:ROTATED_KEY"},
        secret_broker=broker,
    )
    assert res_broker["valid"] is True


def test_signed_pack_keyring_fail_closed_missing_or_unknown_key_id(aura_home, monkeypatch):
    monkeypatch.setenv("AURA_SIGNING_KEY", "secret-1")
    ag = agent("signed-pack-keyring-fail")
    with ag.session(
        export=True,
        signed_pack=True,
        signing_key="secret-1",
        key_id="known-kid",
    ) as run:
        run.emit("turn.end", {"ok": True})

    pack_path = Path(run.exports["pack"])

    # Unknown key_id must fail closed even if AURA_SIGNING_KEY matches
    unknown = verify_audit_pack(pack_path, keyring={"other-kid": "secret-1"})
    assert unknown["valid"] is False
    assert any("known-kid" in err and "not found in keyring" in err for err in unknown["errors"])

    # Empty keyring must fail closed
    empty_ring = verify_audit_pack(pack_path, keyring={})
    assert empty_ring["valid"] is False
    assert any("not found in keyring" in err for err in empty_ring["errors"])

    # Empty key entry in keyring must not fall back to AURA_SIGNING_KEY
    blank_entry = verify_audit_pack(pack_path, keyring={"known-kid": ""})
    assert blank_entry["valid"] is False
    assert any("Empty verification key" in err for err in blank_entry["errors"])

    # Providing both key and keyring must fail closed
    both = verify_audit_pack(pack_path, key="secret-1", keyring={"known-kid": "secret-1"})
    assert both["valid"] is False
    assert any("both key and keyring" in err for err in both["errors"])

    # Missing key_id in pack manifest must fail closed
    pack_data = json.loads(pack_path.read_text(encoding="utf-8"))
    del pack_data["key_id"]
    pack_path.write_text(json.dumps(pack_data), encoding="utf-8")
    missing_id = verify_audit_pack(pack_path, keyring={"known-kid": "secret-1"})
    assert missing_id["valid"] is False
    assert any("missing key_id" in err for err in missing_id["errors"])

    # Whitespace-only key_id in pack manifest must fail closed
    pack_data["key_id"] = "   "
    pack_path.write_text(json.dumps(pack_data), encoding="utf-8")
    blank_id = verify_audit_pack(pack_path, keyring={"known-kid": "secret-1"})
    assert blank_id["valid"] is False
    assert any("missing key_id" in err for err in blank_id["errors"])


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


def test_cli_verify_pack_with_keyring_hmac_and_file_paths(run_aura, aura_home, tmp_path: Path):
    ag = agent("cli-verify-keyring")
    with ag.session(
        export=True,
        signed_pack=True,
        signing_key="cli-rotated-hmac-1",
        key_id="hmac-1",
    ) as run_hmac:
        run_hmac.emit("turn.end", {"ok": True})

    key_dir = tmp_path / "keys"
    key_dir.mkdir()
    hmac_key_file = key_dir / "hmac-1.key"
    hmac_key_file.write_text("cli-rotated-hmac-1", encoding="utf-8")

    keyring_path = key_dir / "keyring.json"
    keyring_path.write_text(
        json.dumps(
            {
                "hmac-1": "hmac-1.key",
                "hmac-2": "cli-rotated-hmac-2",
            }
        ),
        encoding="utf-8",
    )

    ok = run_aura("verify", "pack", run_hmac.exports["pack"], "--keyring", str(keyring_path))
    assert ok.returncode == 0
    payload = json.loads(ok.stdout)
    assert payload["valid"] is True
    assert payload["key_id"] == "hmac-1"

    # Unknown key_id in pack exits non-zero
    with ag.session(
        export=True,
        signed_pack=True,
        signing_key="unknown-secret",
        key_id="hmac-unknown",
    ) as run_unknown:
        run_unknown.emit("turn.end", {"ok": False})

    bad = run_aura("verify", "pack", run_unknown.exports["pack"], "--keyring", str(keyring_path))
    assert bad.returncode == 1
    bad_payload = json.loads(bad.stdout)
    assert bad_payload["valid"] is False
    assert any("not found in keyring" in err for err in bad_payload["errors"])

    # Missing keyring file exits non-zero
    missing_kr = run_aura(
        "verify",
        "pack",
        run_hmac.exports["pack"],
        "--keyring",
        str(tmp_path / "missing.json"),
    )
    assert missing_kr.returncode == 1
    assert "not found" in missing_kr.stderr

    # Invalid keyring JSON exits non-zero
    bad_kr = tmp_path / "bad_keyring.json"
    bad_kr.write_text("[1, 2, 3]", encoding="utf-8")
    invalid_kr = run_aura("verify", "pack", run_hmac.exports["pack"], "--keyring", str(bad_kr))
    assert invalid_kr.returncode == 1
    assert "JSON object" in invalid_kr.stderr

    # Combining --key and --keyring is rejected by CLI parser
    conflict = run_aura(
        "verify",
        "pack",
        run_hmac.exports["pack"],
        "--key",
        "cli-rotated-hmac-1",
        "--keyring",
        str(keyring_path),
    )
    assert conflict.returncode != 0


def test_cli_verify_pack_with_keyring_ed25519(run_aura, aura_home, tmp_path: Path):
    priv_v1, pub_v1 = _generate_ed25519_keypair()
    priv_v2, pub_v2 = _generate_ed25519_keypair()

    ag = agent("cli-verify-keyring-ed")
    with ag.session(
        export=True,
        signed_pack=True,
        signing_key=priv_v1,
        signing_algorithm="ed25519",
        key_id="ed-inline",
    ) as run_inline:
        run_inline.emit("turn.end", {"mode": "inline"})

    with ag.session(
        export=True,
        signed_pack=True,
        signing_key=priv_v2,
        signing_algorithm="ed25519",
        key_id="ed-file",
    ) as run_file:
        run_file.emit("turn.end", {"mode": "file"})

    pub_file = tmp_path / "ed-file.pub.pem"
    pub_file.write_bytes(pub_v2)

    keyring_path = tmp_path / "ed-keyring.json"
    keyring_path.write_text(
        json.dumps(
            {
                "ed-inline": pub_v1.decode("utf-8"),
                "ed-file": str(pub_file),
            }
        ),
        encoding="utf-8",
    )

    loaded = load_keyring(keyring_path)
    assert isinstance(loaded["ed-inline"], str)
    assert isinstance(loaded["ed-file"], bytes)

    res_inline = run_aura(
        "verify", "pack", run_inline.exports["pack"], "--keyring", str(keyring_path)
    )
    assert res_inline.returncode == 0
    assert json.loads(res_inline.stdout)["valid"] is True

    res_file = run_aura("verify", "pack", run_file.exports["pack"], "--keyring", str(keyring_path))
    assert res_file.returncode == 0
    assert json.loads(res_file.stdout)["valid"] is True
