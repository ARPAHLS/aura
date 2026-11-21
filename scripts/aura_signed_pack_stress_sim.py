#!/usr/bin/env python3
"""
Signed audit pack stress simulation (#50).

Exercises:
  1. Valid HMAC-SHA256 pack export + offline verify
  2. Tampered JSONL detection
  3. Tampered summary JSON detection
  4. Forged chain_root detection
  5. Wrong key rejection
  6. 50-event session pack integrity
  7. Ed25519 asymmetric sign + public-key verify (when cryptography installed)

Usage (repo root):
  python scripts/aura_signed_pack_stress_sim.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from aura import agent, configure, verify_audit_pack  # noqa: E402


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    with tempfile.TemporaryDirectory() as home:
        os.environ["AURA_HOME"] = home
        configure()

        # 1 + 6: 50-event session HMAC pack
        ag = agent("pack-stress-50")
        with ag.session(
            export=True,
            signed_pack=True,
            signing_key="stress-hmac-key",
            key_id="stress-1",
        ) as run:
            for i in range(50):
                run.emit("turn.start", {"step": i})

        pack_path = Path(run.exports["pack"])
        res = verify_audit_pack(pack_path, key="stress-hmac-key")
        _assert(res["valid"] is True, f"expected valid pack: {res}")
        print("[PASS] valid_50_event_hmac_pack")

        # 5: Wrong key
        bad = verify_audit_pack(pack_path, key="wrong-key")
        _assert(bad["valid"] is False, "expected wrong key failure")
        print("[PASS] wrong_key_rejected")

        # 2, 3, 4: Tamper copies in isolated temp dir
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            for p in pack_path.parent.glob(f"{run.session_id}*"):
                shutil.copy2(p, tdir / p.name)
            t_pack = tdir / pack_path.name
            t_jsonl = tdir / Path(run.exports["jsonl"]).name
            t_summary = tdir / Path(run.exports["summary"]).name

            # 2: Tampered JSONL
            orig_jsonl = t_jsonl.read_text(encoding="utf-8")
            t_jsonl.write_text(orig_jsonl + '{"tampered":true}\n', encoding="utf-8")
            r_jsonl = verify_audit_pack(t_pack, key="stress-hmac-key")
            _assert(r_jsonl["valid"] is False, "expected tampered JSONL failure")
            t_jsonl.write_text(orig_jsonl, encoding="utf-8")
            print("[PASS] tampered_jsonl_detected")

            # 3: Tampered summary
            orig_sum = t_summary.read_text(encoding="utf-8")
            t_summary.write_text(orig_sum + " ", encoding="utf-8")
            r_sum = verify_audit_pack(t_pack, key="stress-hmac-key")
            _assert(r_sum["valid"] is False, "expected tampered summary failure")
            t_summary.write_text(orig_sum, encoding="utf-8")
            print("[PASS] tampered_summary_detected")

            # 4: Forged chain_root
            pack_data = json.loads(t_pack.read_text(encoding="utf-8"))
            pack_data["chain_root"] = "f" * 64
            t_pack.write_text(json.dumps(pack_data), encoding="utf-8")
            r_root = verify_audit_pack(t_pack, key="stress-hmac-key")
            _assert(r_root["valid"] is False, "expected forged chain_root failure")
            print("[PASS] forged_chain_root_detected")

        # 7: Ed25519 if available
        try:
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
            ag_ed = agent("pack-stress-ed")
            with ag_ed.session(
                export=True,
                signed_pack=True,
                signing_key=priv_pem,
                signing_algorithm="ed25519",
            ) as run_ed:
                run_ed.emit("turn.end", {"ok": True})
            res_ed = verify_audit_pack(run_ed.exports["pack"], key=pub_pem)
            _assert(res_ed["valid"] is True, f"ed25519 verify failed: {res_ed}")
            print("[PASS] ed25519_asymmetric_pack")
        except ImportError:
            print("[SKIP] ed25519_asymmetric_pack (cryptography not installed)")

    print("ALL SIGNED PACK SCENARIOS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
