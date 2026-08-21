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
pytest -v tests/test_v03.py
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

## What we test

| Area | Tests |
|---|---|
| Identity | ULID ids, `agent_ref`, custom `aura_id`, resolve lookup |
| Audit | Hash chain, audit report, approver principal, session export |
| Core | Registry, spine, constraints, conformance, sequencer (see `test_core.py`, `test_v02.py`) |
| Compare / OTel | `test_v03.py` |

## Pre-PR checklist

1. `pytest`
2. `black aura tests` (no diff)
3. `flake8 aura tests`
4. CHANGELOG entry under `[Unreleased]` or release section
5. Docs updated if behavior or CLI changed
