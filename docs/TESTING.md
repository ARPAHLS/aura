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
