# Contributing to AURA Harness

Thank you for considering a contribution. AURA is a lightweight runtime coat for agent loops — we keep the core small and grow through adapters, rules, and exporters.

## Getting started

```bash
git clone https://github.com/ARPAHLS/aura.git
cd aura
py -3.13 -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"
pytest
```

Requires **Python 3.10+**. See [docs/TESTING.md](docs/TESTING.md) for lint and PR checklist.

## Quality bar

Before opening a PR:

```bash
pytest
black aura tests
flake8 aura tests
```

## What to contribute

| Area | Examples |
|---|---|
| **Core** | Session lifecycle, spine, constraints, conformance, audit report |
| **Runtime adapters** | Python first; LangGraph, MCP, others welcome |
| **Rules & observers** | New built-in constraint types, observer presets |
| **Exporters** | OTel, webhooks, enterprise sinks |
| **Examples** | Small, runnable demos with README |
| **Docs** | Clarity over jargon; fix typos and gaps |

See [docs/ROADMAP.md](docs/ROADMAP.md) for deferred work.

## Pull request guidelines

1. **One concern per PR** when possible (feature, fix, or docs — not all three).
2. **Tests** for behavior changes in `tests/`.
3. **CHANGELOG** — add an entry ([Keep a Changelog](https://keepachangelog.com/)).
4. **No secrets** in commits (.env, API keys, tokens).
5. Match existing style: typed Python, `black` formatting, `flake8` clean.

Use the [pull request template](.github/PULL_REQUEST_TEMPLATE.md).

## Architecture principles

- **Events before features** — everything meaningful emits to the audit spine.
- **Wrap, don't replace** — the user's loop stays in their runtime.
- **Layered identity** — `agent_ref` for humans/CI, ULID internal id, external ids in trailer.
- **No hardcoded world** — models, tools, memory attach via adapters.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

## Security

Report vulnerabilities privately — see [SECURITY.md](SECURITY.md).

## Questions

- Issues: [github.com/ARPAHLS/aura/issues](https://github.com/ARPAHLS/aura/issues)
- Support: systems@arpacorp.net
