# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-08-20

### Added

- **Membrane** (`aura/membrane/`) — ingress context at session open; egress `guarded_tool_call` (`tool.intent` → `tool.call` → `tool.result`).
  - *Rationale:* Official membrane terminology with a concrete Skillware egress path.
- **Sequencer** (`aura/sequencer/runner.py`, `engine.py`) — linear steps (`skill`, `op`, `prompt`, `gate`, `subflow`), retries, gates (`human_confirm`, `constitution`, `budget`), per-step `step_id` on spine.
  - *Rationale:* Prescriptive pipelines distinct from emergent agent loops; conformance on declared order.
- **Skillware host** (`aura/hosts/skillware.py`) — wrap skill `execute()` through egress; `MockSkill` for tests/examples.
  - *Rationale:* Reference host for enterprise compliance flows; optional `pip install "aura-harness[skillware]"` (≥ 0.5.1).
- **Observers** (`aura/observers/`) — registry + parallel dispatch on every spine event.
- **Agent profile fields** — `skills`, `sequencer`, `observers` persisted in registry JSON.
- **SDK** — `SessionRun.run_sequencer(host=...)`, `session(sequencer=...)`, `emit(..., step_id=...)`, `session.require_approval()`.
- **Conformance** — sequencer declared vs completed step order in summary.
- **Example 04** — `examples/04-sequencer-pipeline/` (research → draft → approve → notify).
- **Tests** — `tests/test_v02.py` (7 tests).
- **Docs** — [using-aura.md](docs/using-aura.md), [skillware-integration.md](docs/skillware-integration.md); updated architecture, concepts, glossary, sequencer, ROADMAP, comparison.

### Changed

- **Version** — `0.2.0` in `pyproject.toml` and `aura.__version__`.
- **Session open** — emits `membrane.ingress` before `session.open`.
- **README** — v0.2 component table, membrane diagram with observers.

## [0.1.0] - 2026-08-18

### Added

- **Agent registry** (`aura/agents/`) — local store with monotonic `AURA-000n` IDs, optional user `name`, ID trailer (`ids.external`), alias uniqueness, soft archive; counter never decreases.
  - *Rationale:* Lite audit anchor without an identity service; user-supplied IDs nest under `ids`.
- **Config merge** (`aura/config.py`) — global `~/.aura/` + project `.aura/` paths; merge order defaults → global → project → agent → session.
  - *Rationale:* Enterprise-friendly layering without forcing a stack.
- **Session lifecycle** (`aura/core/session.py`) — modes `script`, `task`, `continuous`; open/run/close; snapshot hash of declared rules at session open.
  - *Rationale:* One API covers one-shot scripts, goal-bound tasks, and long-running loops.
- **Audit spine** (`aura/core/spine.py`) — append-only JSONL per session, causal fields (`event_id`, `parent_id`, `trace_id`), `aura_id` on every event.
  - *Rationale:* Lightweight, grep-friendly, ingestible by third-party tools later (OTel mapping documented in roadmap).
- **Constraint engine** (`aura/core/constraints.py`) — built-in rules: `max_tokens_per_step`, `confirm_before`, `allow_tools`, `deny_tools`; plugin hook for custom rules.
  - *Rationale:* Modular guardrails without hardcoding twelve field services.
- **Conformance summary** (`aura/core/conformance.py`) — compares declared rules vs observed events on session close; emits summary JSON.
  - *Rationale:* Job A (conformance) as flexible comparator, not fixed checklist.
- **Public SDK** (`aura/api.py`) — `configure()`, `agent()`, `Agent.session()` context manager, `emit()`, `approve()`, auto-export on close.
  - *Rationale:* Library-first; CLI mirrors SDK.
- **Python runtime helper** (`aura/runtime/python.py`) — `run_script()` wrapper and `@aura_wrapped` decorator pattern.
  - *Rationale:* First attach target; headless `emit()` works without runtime adapter.
- **JSONL exporter** (`aura/exporters/jsonl.py`) — session `.jsonl` + `.summary.json`.
- **CLI** — `aura version`, `agent create|list|show`, `run`, `logs`, `export`.
- **Examples** — `examples/01-minimal-loop`, `02-guarded-tools`, `03-task-mode` with READMEs.
- **Tests** — registry, spine, constraints, session, conformance, API integration.
- **Repo hygiene** — `LICENSE` (MIT), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, this changelog.
- **Docs** — `docs/concepts.md`, `docs/getting-started.md`, `docs/ROADMAP.md`; refreshed README overview.

### Changed

- **Identity model** — removed requirement for Live ID / SoulSig in runtime path; optional IDs live in agent `ids` trailer only.
  - *Affected:* `docs/trust-paths.md` reframed as optional adapter enrichment (see docs note).
- **Architecture narrative** — docs emphasize attach → record → enforce → export; stack diagram kept as optional ARPA ecosystem context.
- **`pyproject.toml`** — MIT license, description updated, `pyyaml` dependency for agent YAML profiles.
- **`.gitignore`** — ignore `.aura/` local state (except committed examples config).

### Deferred (see docs/ROADMAP.md)

- Sequencer DSL (possible separate product).
- Twelve field services as named observer presets, not core modules.
- Live ID, Legacy, Rooms bridges.
- OTel exporter (JSONL + mapping notes only).
- Auto-discovery for LangGraph, MCP, etc.
- Skillware wired adapter (documented; stub in roadmap).

### Notes

- v0.1 is a **runnable kernel**, not the full manifesto stack.
- Type plugin registry (`aura/core/registry.py`) retained for future adapters; not required to run basic sessions.

[Unreleased]: https://github.com/ARPAHLS/aura/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/ARPAHLS/aura/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/ARPAHLS/aura/releases/tag/v0.1.0
