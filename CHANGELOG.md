# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **docs/comparison.md** — AURA vs DeepSeek Harness, LangGraph, CrewAI, LangSmith/tracing, DeepEval/RAGAS, MCP, OTel; orchestrator vs membrane framing; executive matrix; honest v0.1 scope.
  - *Rationale:* Public positioning aligned with Skillware-style comparison doc; clarifies long-term differentiation without claiming unshipped membrane features as done.

### Changed

- **`pyproject.toml`** — description, expanded keywords, PyPI classifiers (AI, monitoring, audiences), `[project.urls]` with Homepage `arpacorp.net`.
  - *Rationale:* PyPI/GitHub metadata reflects product identity; no "record enforce export" tagline.
- **README.md**, **docs/INDEX.md**, **architecture.md**, **getting-started.md**, **spec/type-plugin.contract.md** — links to comparison doc; getting-started Next section wording aligned.

### Changed (prior)

- **AURA architecture diagram** — replaced manifesto stack (Soul, Rooms, Legacy) with harness-specific flow: Identity, Brain, Memory, Tools, Constitution → Body / Runtime → Aura → **Audit Trail** → **Session Export**.
  - *Rationale:* README and docs must reflect AURA's model, not copy manifesto; Soul removed; Identity is a peer input.
  - *Affected:* `README.md`, `docs/stack-position.md`, `docs/architecture.md`, `docs/concepts.md`, `docs/glossary.md`.
- **Official output names** — **Audit trail** (live log) and **Session export** (JSONL + summary on close). Code term `AuditSpine` unchanged.

### Changed (prior)

- **README.md** — fixed broken stack table (blank line between header and rows broke Markdown rendering); updated to reflect v0.1 shipped vs roadmap; added getting-started/examples badges; removed aspirational mechanisms presented as current; lite identity note.
  - *Rationale:* GitHub README must match runnable repo state; table must render correctly.

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

[Unreleased]: https://github.com/ARPAHLS/aura/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ARPAHLS/aura/releases/tag/v0.1.0
