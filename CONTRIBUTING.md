# Contributing to AURA Harness

Thank you for considering a contribution. AURA is a lightweight runtime coat for agent loops — we keep the core small and grow through adapters, rules, and exporters.

## Getting started

```bash
git clone https://github.com/ARPAHLS/aura.git
cd aura
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

Requires **Python 3.10+**.

## What to contribute

| Area | Examples |
|---|---|
| **Core** | Session lifecycle, spine, constraints, conformance |
| **Runtime adapters** | Python first; LangGraph, MCP, others welcome |
| **Rules & observers** | New built-in constraint types, observer presets |
| **Exporters** | OTel, CSV, webhooks |
| **Examples** | Small, runnable demos with README |
| **Docs** | Clarity over jargon; fix typos and gaps |

See [docs/ROADMAP.md](docs/ROADMAP.md) for deferred work — check before building something we plan separately (e.g. full sequencer).

## Pull request guidelines

1. **One concern per PR** when possible (feature, fix, or docs — not all three).
2. **Tests** for behavior changes in `tests/`.
3. **CHANGELOG** — add an entry under `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md) (Keep a Changelog format).
4. **No secrets** in commits (.env, API keys, tokens).
5. Match existing code style: typed Python, minimal dependencies, clear names.

## Architecture principles

- **Events before features** — everything meaningful emits to the audit spine.
- **Wrap, don't replace** — the user's loop stays in their runtime.
- **No hardcoded world** — models, tools, memory attach via adapters later.
- **Lite identity** — AURA assigns `AURA-000n` for audit; user IDs live in the ID trailer.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Be respectful and constructive.

## Security

Report vulnerabilities privately — see [SECURITY.md](SECURITY.md).

## Questions

- Issues: [github.com/ARPAHLS/aura/issues](https://github.com/ARPAHLS/aura/issues)
- Support: systems@arpacorp.net
