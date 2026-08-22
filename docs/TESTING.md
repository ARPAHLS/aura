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
black aura tests
flake8 aura tests
```

CI expectation: **pytest**, **black**, and **flake8** all pass on `aura/` and `tests/`.

## Continuous integration

GitHub Actions workflow **[`.github/workflows/ci.yml`](../.github/workflows/ci.yml)** (job name: **`lint-test`**) runs on:

- every **pull request** targeting `main`
- every **push** to `main` (post-merge sanity)

Steps (Python 3.12 on Ubuntu):

```bash
pip install -e ".[dev]"
black --check aura tests
flake8 aura tests
pytest
```

**Fork PRs:** the workflow uses `permissions: contents: read` only — no repository secrets, no PyPI OIDC, no deploy environment.

**Publish workflow:** [`.github/workflows/publish-pypi.yml`](../.github/workflows/publish-pypi.yml) runs the same lint/test steps before release upload; keep both in sync until a reusable workflow lands (separate CI follow-up issue).

**Maintainers:** after the first green `lint-test` run on `main`, enable **branch protection** → required status check **`lint-test`**.

## Coverage expectations

- **New behavior needs a test** — extend the closest file (`test_core.py`, `test_v02.py`, `test_v03.py`, `test_cli.py`, or `test_core_gaps.py`).
- Shared fixtures live in **`tests/conftest.py`** — do not duplicate `aura_home` in test modules.
- Optional Skillware-only tests use `@pytest.mark.skillware` and `pytest.importorskip("skillware")`.
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
| `test_examples_smoke.py` | Runnable example scripts |

## What we test

| Area | Tests |
|---|---|
| Identity | ULID ids, `agent_ref`, custom `aura_id`, resolve lookup, legacy `AURA-000n`, archive |
| Audit | Hash chain (valid + tamper), audit report, approver principal, session export |
| Core | Registry, spine, constraints, conformance, sequencer (`test_core.py`, `test_v02.py`) |
| CLI | Version, agent CRUD, run, logs, export, export-otel, compare (`test_cli.py`) |
| Config / runtime | YAML merge, `run_script`, middleware, session modes (`test_core_gaps.py`) |
| Compare / OTel | Summary diff incl. `agent_ref` + `hash_chain_valid`, OTel JSONL export (`test_v03.py`, `test_core_gaps.py`) |
| Examples | Smoke run all `examples/*/main.py` (`test_examples_smoke.py`) |

## Pre-PR checklist

1. `pytest`
2. `black aura tests` (no diff)
3. `flake8 aura tests`
4. CHANGELOG entry under `[Unreleased]` or release section
5. Docs updated if behavior or CLI changed
