# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | Yes |

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email **systems@arpacorp.net** with:

- Description of the issue
- Steps to reproduce
- Impact assessment (if known)
- Affected version

We aim to acknowledge within 72 hours and provide a timeline for a fix when applicable.

## Scope

In scope:

- AURA core (session, spine, registry, constraints, CLI)
- Example code shipped in this repository

Out of scope:

- Third-party models, tools, or adapters you attach to AURA
- User agent code running under the harness

## Dependency auditing

The pull request and main-branch CI workflow runs `pip-audit` against the installed Python dependencies. It is configured as a warn-only check with `continue-on-error: true` for one release cycle while the project establishes a clean baseline. A dependency finding therefore does not block CI yet; maintainers may make the check required once the baseline is clean.

A green audit does not guarantee that every dependency is free of vulnerabilities. Keep dependencies updated and report vulnerabilities in AURA itself using the private reporting process above.

## Audit logs

Session exports may contain sensitive data from your agent runs. Store `.aura/sessions/` and export files with appropriate access controls. AURA does not encrypt logs by default in v0.1.

**Credentials:** do not put live API keys, tokens, or card numbers on agent profiles. Use `capabilities[].secret.ref` (for example `env:AURA_CAP_…`) and a SecretBroker; egress injects the value after policy and redacts it from the spine. See [docs/capabilities.md](docs/capabilities.md).

## Signed audit pack key management

Sessions exported with `signed_pack=True` produce `{session_id}.pack.json`, a detached HMAC-SHA256 or Ed25519 signature over the canonical pack manifest (`chain_root` plus artifact SHA-256 digests). The manifest fields and verification output are described in [docs/outputs.md](docs/outputs.md); this section covers operational handling of the signing key ([#50](https://github.com/ARPAHLS/aura/issues/50)).

### Key generation and storage

- For `hmac-sha256`, generate a high-entropy secret, for example `python -c "import secrets; print(secrets.token_hex(32))"`, and set it as `AURA_SIGNING_KEY` or pass `signing_key=...`.
- For `ed25519`, install the optional `cryptography` package and generate a keypair. Sign with the private PEM (or a 32-byte raw key) and retain the public PEM for offline verification.
- Keep `AURA_SIGNING_KEY`, private PEMs, and raw private keys out of source control, committed `.env` files, session directories, and spine logs. Prefer a secret manager and a SecretBroker ref over a plaintext environment variable. AURA redacts secret-like payload keys on emit, but payload redaction does not replace key custody.

### Key rotation and `key_id` lifecycle

- Each `.pack.json` v1 manifest records the `algorithm` and a `key_id` (default `"default"`); both are covered by the signature. Set `key_id` via `agent.session(key_id=...)` to label which key produced a batch of packs.
- On rotation, assign a new `key_id` and keep the retired key (or its Ed25519 public PEM) in a key registry keyed by `key_id`. Verification reports the pack's `key_id`, so an older id identifies an archived key; on its own it is not evidence of tampering.

### Offline verification and incident response

- Verify in an air-gapped environment or CI pipeline with `aura verify pack <path> --key <key>`. `--key` takes a literal key or SecretBroker ref and otherwise falls back to `AURA_SIGNING_KEY`; Ed25519 verification also accepts a public PEM. Artifacts are resolved next to the pack file, so copy the `.pack.json` together with its JSONL, summary, and OTel files. The command prints JSON with `valid`, `key_id`, and `errors`, and exits non-zero on failure.
- Interpret failures precisely: `Signature verification failed` points to a wrong or rotated key or a tampered signature (when no key is supplied, verification reports that no signing key was provided), while `SHA-256 digest mismatch`, `chain_root does not match tail content_hash`, or `hash chain verification failed` points to altered exported artifacts. Preserve the pack and its artifacts before investigating, and report suspected flaws in AURA itself through the private channel above.
