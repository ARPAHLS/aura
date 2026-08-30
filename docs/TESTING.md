# Testing

## Setup

```bash
py -3.13 -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"
```

## Run tests

```bash
pytest
pytest --cov=aura --cov-report=term-missing
```

## Lint (required before PR)

```bash
black aura tests integrations examples
flake8 aura tests integrations examples
```

CI expectation: **pytest**, **black**, and **flake8** all pass on `aura/` and `tests/` for every supported Python version. The dependency audit is advisory: `pip-audit` reports findings without blocking the CI gate.

## Continuous integration

GitHub Actions:

| Workflow | Role |
|---|---|
| **[`ci.yml`](../.github/workflows/ci.yml)** | PR + push to `main` — Python matrix, Skillware job, gate `lint-test` |
| **[`reusable-test.yml`](../.github/workflows/reusable-test.yml)** | **Single source** for install / black / flake8 / pytest (issue [#17](https://github.com/ARPAHLS/aura/issues/17)) |
| **[`publish-pypi.yml`](../.github/workflows/publish-pypi.yml)** | Release gate — calls `reusable-test.yml` on Python 3.12 before upload |

**[`ci.yml`](../.github/workflows/ci.yml)** runs on:

- every **pull request** targeting `main`
- every **push** to `main` (post-merge sanity)

Python matrix on **ubuntu-latest** (`fail-fast: true` — one version failure cancels the rest):

```yaml
python-version: ["3.10", "3.11", "3.12", "3.13"]
```

Each matrix cell invokes **`reusable-test.yml`** with the same steps:

```bash
pip install -e ".[dev]"
pip install pip-audit
pip-audit                 # warn-only; does not block the CI gate
black --check aura tests integrations examples
flake8 aura tests integrations examples
pytest --cov=aura --cov-report=term-missing --ignore=tests/integration
```

The **Dependency audit (warn-only)** step runs `pip-audit` with
`continue-on-error: true`. A vulnerability finding or audit error is therefore
reported in the workflow logs but does not fail the matrix or block a PR from
merging. Treat the output as a prompt to investigate and update dependencies;
use the private reporting path in [SECURITY.md](../SECURITY.md) for a suspected
vulnerability in AURA itself.

The workflow also emits a gate job named **`lint-test`** that succeeds only when every matrix cell passed. That is the check to require in branch protection.

**Fork PRs:** the workflow uses `permissions: contents: read` only — no repository secrets, no PyPI OIDC, no deploy environment.

**Publish workflow:** [`.github/workflows/publish-pypi.yml`](../.github/workflows/publish-pypi.yml) calls **`reusable-test.yml`** on Python 3.12 before release upload (no `pip-audit`; same black/flake8/pytest scope as PR CI). Full 3.10–3.13 coverage is the PR CI matrix.

**Skillware job:** **`skillware-live`** in `ci.yml` calls **`reusable-test.yml`** with `skillware: true` — `pip install -e ".[dev,skillware]"` and `pytest tests/test_skillware_integration.py`.

**Maintainers:** after the first green `lint-test` run on `main`, enable **branch protection** → required status check **`lint-test`**.

## Coverage expectations

- **New behavior needs a test** — extend the closest file (`test_core.py`, `test_v02.py`, `test_v03.py`, `test_cli.py`, or `test_core_gaps.py`).
- Shared fixtures live in **`tests/conftest.py`** — do not duplicate `aura_home` in test modules.
- Optional Skillware registry tests: `tests/test_skillware_integration.py` (`@pytest.mark.skillware`) — run in CI via the **skillware-live** job when `[skillware]` is installed ([#36](https://github.com/ARPAHLS/aura/issues/36)).
- **Real integration tests** live in **`tests/integration/`** (Skillware + Ollama, example 06 live). Default CI **excludes** them (`--ignore=tests/integration`). Run locally:

```bash
pip install -e ".[integrations]"
pytest tests/integration/ -v
```

Integration tests **fail** (not skip) if Ollama or Skillware is missing — that is intentional for the local integration suite.
- Default CI matrix runs `pytest --ignore=tests/integration` — no deselected or skipped optional tests in the gate.
- CI prints **`pytest --cov=aura --cov-report=term-missing`** for visibility; there is **no coverage gate** yet.

## Test layout

| File | Focus |
|---|---|
| `conftest.py` | `aura_home`, `run_aura`, example runner |
| `test_core.py` | Registry, spine, constraints, session export (v0.1) |
| `test_v02.py` | Sequencer, observers, membrane, Skillware host |
| `test_v03.py` | Identity, audit report, hash chain, compare |
| `test_cli.py` | `aura` CLI commands and exit codes |
| `test_core_gaps.py` | Config, exporters, runtime, middleware, archive, tamper, compare edge cases (GH #4) |
| `test_identity.py` | Operator identity adapters, redaction, OTel operator attrs, `identity.bound` (GH #55) |
| `test_session_invariants.py` | Session lifecycle, atomic export, closed-session errors (GH #15) |
| `test_examples_smoke.py` | Runnable example scripts |

## What we test

| Area | Tests |
|---|---|
| Identity | ULID ids, `agent_ref`, custom `aura_id`, resolve lookup, legacy `AURA-000n`, archive; optional operator adapters + export redaction (`test_identity.py`) |
| Audit | Hash chain (valid + tamper), audit report, approver principal, session export |
| Core | Registry, spine, constraints, conformance, sequencer (`test_core.py`, `test_v02.py`) |
| CLI | Version, agent CRUD, run, logs, export, export-otel, compare, identity show (`test_cli.py`) |
| Config / runtime | YAML merge, `run_script`, middleware, session modes (`test_core_gaps.py`) |
| Compare / OTel | Summary diff incl. `agent_ref` + `hash_chain_valid`, OTel JSONL export (`test_v03.py`, `test_core_gaps.py`) |
| Examples | Smoke run all `examples/*.py` (`test_examples_smoke.py`) |
| Skillware | Live registry skills via `test_skillware_integration.py` (CI **skillware-live** job) |
| Integration | `tests/integration/` — Ollama + Skillware + example 06 (local only) |

## Pre-PR checklist

1. `pytest --ignore=tests/integration`
2. `black aura tests integrations examples` (no diff)
3. `flake8 aura tests integrations examples`
4. CHANGELOG entry under `[Unreleased]` or release section
5. Docs updated if behavior or CLI changed
