# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Python 3.13** package classifier — matches the CI matrix and `requires-python = ">=3.10"` ([GH #10](https://github.com/ARPAHLS/aura/issues/10)).
- **Core test coverage (GH #4)** — config layers, legacy + ULID coexistence, tampered JSONL → audit report `HASH_CHAIN_BROKEN`, constraint allow/deny/token matrix, session mode + project storage paths, compare `agent_ref` / `hash_chain_valid` diffs.
- **`AuditSpine.from_jsonl()`** — reload spine from disk for verify/tamper checks.
- **Compare sessions** — `agent_ref.same` and `hash_chain_valid` fields in diff output.

- **`aura agent set`** — update `agent_ref`, purpose, skills, variables, ids, and rules on existing profiles.
- **`aura config show`** — merged global/project config and resolved registry/sessions paths.
- **`aura paths`** — view paths; **`set-project`** and **`set-storage`** persist settings to YAML.
- **Interactive paths submenu** — replaces read-only home; agents menu adds **edit** wizard.
- **Splash polish** — blank line above ASCII logo; smoother Rich truecolor gradient on Windows Terminal.

### Changed

- **PR CI** — `lint-test` now covers Python 3.10–3.13 on Ubuntu (`fail-fast`); publish remains a 3.12 release gate ([GH #10](https://github.com/ARPAHLS/aura/issues/10)).
- **`AgentRegistry.update_profile`** — registry ref/alias maps stay consistent when `agent_ref` changes.
- **Global config** — optional persisted `project_dir` in `~/.aura/config.yaml`.

## [0.3.3] - 2026-08-21

### Added

- **PR CI workflow** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) — `lint-test` job on pull requests and pushes to `main` (black, flake8, pytest).
- **Test suite** — shared `tests/conftest.py`; new `test_cli.py`, `test_core_gaps.py`, and `test_examples_smoke.py` (49 tests; example script smoke runs).
- **CI coverage report** — `pytest --cov=aura --cov-report=term-missing` in PR and publish workflows (report only, no gate).

### Changed

- **`docs/comparison.md`** — membrane vs prompt-harness positioning, session receipt language, shipped scope through v0.3.3.
- **`docs/TESTING.md`**, **`CONTRIBUTING.md`**, **`docs/PUBLISHING.md`** — CI parity, coverage expectations, publish trigger docs.

### Fixed

- **Publish workflow** — removed duplicate `v*` tag trigger (tag + GitHub Release no longer double-publishes); `skip-existing: true` for safe manual re-runs.

## [0.3.2] - 2026-08-20

### Changed

- **Publish workflow** — GitHub `pypi` environment with PyPI project URL so Deployments appear in the repo sidebar.

### Fixed

- **README badges** — single row: Version, DOI, License, Powered by (PyPI project page refresh).

## [0.3.1] - 2026-08-20

### Fixed

- **README on PyPI** — splash image uses raw GitHub URL (`main`; relative paths do not render on PyPI).
- **README badges** — Version badge pastel color; two-row layout with DOI badge.

## [0.3.0] - 2026-08-20

### Added

- **Layered identity** — `agent_ref` (tenant/slug), ULID internal `aura_id`, optional user-supplied `aura_id`, `ids.tenant`, `policy_version` on profile and spine trailer.
- **Audit report** (`aura/core/audit_report.py`) — verdict, scorecard, findings, recommendations on session export.
- **Hash chain** — `prev_hash` / `content_hash` on every spine event; verification on report build.
- **Approver principal** — `approve(request_id, principal=...)` recorded on spine.
- **OTel export** — `aura export-otel`, `.otel.jsonl` on session close.
- **Compare runs** — `aura compare <session_a> <session_b>`.
- **Lint tooling** — `black` + `flake8` in `[dev]`; [docs/TESTING.md](docs/TESTING.md), PR template.
- **Zenodo concept DOI** — [10.5281/zenodo.22031863](https://doi.org/10.5281/zenodo.22031863) in [CITATION.cff](CITATION.cff) and package metadata.

### Changed

- **Registry** — ULID default ids; `resolve()` by ref, name, or id; legacy `AURA-000n` profiles still load.
- **README** — minimal narrative layout; architecture clarifies Body ↔ Aura egress gate (not “Aura = egress”).
- **Version** — `0.3.0` across package and docs.

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

[Unreleased]: https://github.com/ARPAHLS/aura/compare/v0.3.3...HEAD
[0.3.3]: https://github.com/ARPAHLS/aura/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/ARPAHLS/aura/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/ARPAHLS/aura/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/ARPAHLS/aura/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/ARPAHLS/aura/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/ARPAHLS/aura/releases/tag/v0.1.0
