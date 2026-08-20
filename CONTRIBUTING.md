# Contributing to AURA Harness

Welcome. AURA Harness is a **runtime coat** around agent loops — audit, policy, session export — without replacing your host. We welcome contributions from **human developers**, **semi-autonomous assistants**, and **autonomous agents** that follow this guide.

**Agents:** read [Agent Contribution Workflow](docs/contributing/ai_native_workflow.md) first. Human operators supervising agent work should use the same workflow for review.

---

## Navigation

| Section | Description |
| :--- | :--- |
| [Ways to contribute](#ways-to-contribute) | Pick your contribution type |
| [Getting started](#getting-started) | Fork, branch, install |
| [Universal expectations](#universal-expectations) | Standards for every PR |
| [Ripple effects](#ripple-effects-if-you-change-x-update-y) | What else to update when you change X |
| [Pull request process](#pull-request-process) | Issue → verify → PR |
| [What to avoid](#what-to-avoid) | Anti-patterns |
| [AI agents and operators](#ai-agents-and-operators) | Autonomous work rules |
| [Related documents](#related-documents) | Testing, CoC, templates |

---

## Ways to contribute

| Type | What you change | Typical label | Before coding | Verify locally |
| :--- | :--- | :--- | :--- | :--- |
| **Bug fix** | Paths named in issue | `bug` | [Bug report](.github/ISSUE_TEMPLATE/01_bug_report.yml) | Repro + `pytest`; add regression test when possible |
| **Core framework** | `aura/core/`, `aura/agents/`, `aura/api.py` | `core framework` | [Core issue](.github/ISSUE_TEMPLATE/03_core_framework.yml) | `pytest tests/test_core.py` + related; update docs if API changes |
| **CLI** | `aura/cli/` | `cli` | [CLI issue](.github/ISSUE_TEMPLATE/04_cli.yml) | Manual CLI check + `pytest` |
| **Integration** | `aura/sequencer/`, `aura/hosts/`, `aura/membrane/`, `aura/observers/`, exporters | `sequencer`, `hosts`, `membrane`, `observers`, `audit & export` | [Integration issue](.github/ISSUE_TEMPLATE/06_integration.yml) | `pytest tests/test_v02.py` / `test_v03.py`; update integration docs |
| **Documentation** | `docs/`, `README.md` | `documentation` | [Documentation issue](.github/ISSUE_TEMPLATE/02_documentation.yml) | Links valid; tone matches repo |
| **Enhancement** | New behavior in scope of issue | `enhancement` | [Enhancement issue](.github/ISSUE_TEMPLATE/05_enhancement.yml) | Tests + CHANGELOG + ripple docs |
| **Examples** | `examples/` | `examples` | Issue or enhancement | Script runs; update `examples/README.md` |
| **Packaging / CI** | `pyproject.toml`, `.github/workflows/` | `packaging`, `ci` | Issue | Build wheel locally; CI green |
| **Good first issue** | Small docs/tests/fixes | `good first issue` | Read acceptance criteria | Checklist for underlying type above |

Labels: [`.github/labels.json`](.github/labels.json) — synced on merge to `main` via [sync-labels workflow](.github/workflows/sync-labels.yml).

---

## Getting started

### 1. Find or open an issue

Check [existing issues](https://github.com/ARPAHLS/aura/issues) first.

| Intent | Template |
| :--- | :--- |
| Incorrect behavior | [Bug report](https://github.com/ARPAHLS/aura/issues/new/choose) |
| Session, spine, identity, audit | [Core framework](https://github.com/ARPAHLS/aura/issues/new/choose) |
| `aura` CLI | [CLI](https://github.com/ARPAHLS/aura/issues/new/choose) |
| Sequencer, Skillware host, membrane, observers | [Integration](https://github.com/ARPAHLS/aura/issues/new/choose) |
| Docs only | [Documentation](https://github.com/ARPAHLS/aura/issues/new/choose) |
| New feature | [Enhancement](https://github.com/ARPAHLS/aura/issues/new/choose) |

Wait for maintainer feedback on large or breaking work before investing in a big PR.

### 2. Fork and clone

```bash
git clone https://github.com/<your-username>/aura.git
cd aura
git remote add upstream https://github.com/ARPAHLS/aura.git
```

### 3. Sync and branch

```bash
git fetch upstream
git checkout main
git pull upstream main
git checkout -b fix/issue-<number>-short-description
```

### 4. Install

Requires **Python 3.10+**.

```bash
py -3.13 -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"
```

Skillware host work:

```bash
pip install -e ".[dev,skillware]"
```

See [docs/TESTING.md](docs/TESTING.md) for lint and CI parity.

### 5. Implement and verify

Follow [Ripple effects](#ripple-effects-if-you-change-x-update-y), then [Pull request process](#pull-request-process).

---

## Universal expectations

### Code of conduct

Follow the [Code of Conduct](CODE_OF_CONDUCT.md). We welcome autonomous logical systems that adhere to repo standards; operators remain accountable for merged work.

### Style

- **No emojis** in source, docs, commits, or PR titles.
- **Black** (`black aura tests`) and **Flake8** (`flake8 aura tests`) — see [TESTING.md](docs/TESTING.md).
- Typed Python where the surrounding code uses types; match existing naming and structure.

### Scope

- Change only what the issue requires.
- **Do not bump** `pyproject.toml` version or `CITATION.cff` unless a maintainer or release issue explicitly asks.
- **Do not commit** `AURA_PLAN.md` (local, gitignored) or secrets (`.env`, keys, tokens).

### Tests and CI

- Behavior changes **require tests** in `tests/`.
- Run before opening a PR:

  ```bash
  pytest
  black aura tests
  flake8 aura tests
  ```

- CI runs on PRs: tests, black, flake8 (see [publish-pypi.yml](.github/workflows/publish-pypi.yml) test job pattern).
- Wait for green checks before requesting review.

### CHANGELOG

When a PR changes **user-visible behavior** (SDK, CLI, export shape, default session behavior, new commands):

- Add entries under **`[Unreleased]`** in [CHANGELOG.md](CHANGELOG.md) ([Keep a Changelog](https://keepachangelog.com/) sections: Added / Changed / Fixed / Removed).
- Do **not** add version headers or cut releases — maintainers tag releases.

Pure internal refactors with no user-visible effect may omit CHANGELOG; ask on the issue if unsure.

---

## Ripple effects (if you change X, update Y)

| If you change… | Also update… |
| :--- | :--- |
| Public SDK (`aura/api.py`, `SessionRun` methods) | `docs/getting-started.md`, `docs/using-aura.md`, `docs/concepts.md`, tests, CHANGELOG |
| Session / spine event shape | `spec/aura-event.schema.json` (if applicable), `docs/outputs.md`, tests, CHANGELOG |
| Agent profile / registry fields | `docs/trust-paths.md`, `aura/agents/profile.py` persistence, tests, CHANGELOG |
| Constraint rule types | `docs/concepts.md`, `aura/core/constraints.py` tests, CHANGELOG |
| Sequencer step model | `spec/sequencer.schema.json`, `docs/sequencer.md`, `tests/test_v02.py`, CHANGELOG |
| Skillware host / egress | `docs/skillware-integration.md`, examples, CHANGELOG |
| CLI commands or flags | `docs/getting-started.md`, `README.md` quick start line, CHANGELOG |
| New example | `examples/README.md`, optional link from `docs/getting-started.md` |
| Architecture terminology | `docs/architecture.md`, `README.md` diagrams (keep in sync) |
| Release / PyPI behavior | `docs/PUBLISHING.md`, `.github/workflows/publish-pypi.yml`, CHANGELOG |
| Issue template fields | `.github/labels.json` if new label needed; run label sync |
| Version (maintainer only) | `pyproject.toml`, `aura/__init__.py`, `CITATION.cff`, CHANGELOG release section |

When in doubt, search the repo for the symbol or term you changed and update docs that reference it.

---

## Pull request process

1. **Link an issue** — `Fixes #123` or `Refs #123` in the PR description.
2. **Branch** — feature branch on your fork, not direct commits to upstream `main`.
3. **Implement** — follow [Ways to contribute](#ways-to-contribute) and [Ripple effects](#ripple-effects-if-you-change-x-update-y).
4. **Verify locally** — `pytest`, `black aura tests`, `flake8 aura tests`.
5. **CHANGELOG** — `[Unreleased]` entry when user-visible.
6. **PR template** — complete [pull request template](.github/PULL_REQUEST_TEMPLATE.md) honestly.
7. **Push** — open PR to `ARPAHLS/aura` `main`.
8. **CI** — fix failures; address review on the same branch.

### Commit messages

- Imperative mood: `Add audit report findings for denied tools`
- No emojis; no AI `Co-authored-by:` trailers
- Reference issue when helpful: `Fix session export agent_ref (#42)`

---

## What to avoid

- **Bypassing the membrane** — do not document or test “call Skillware directly” as the blessed path unless the issue is explicitly about fallback/offline mode.
- **God modules** — keep changes focused; no unrelated refactors.
- **Orchestrator creep** — AURA wraps loops; do not add model routing or tool frameworks into core.
- **Deleting vision** — do not remove ROADMAP/narrative content without maintainer agreement.
- **Placeholder docs** — no “TODO: document” in user-facing paths you touch.
- **Unrequested version bumps** — see [Maintainer: cutting a release](#maintainer-cutting-a-release).
- **Hardcoded vendors** — use adapters and host patterns; no “only OpenAI” assumptions in core.

---

## AI agents and operators

Autonomous and semi-autonomous agents are **welcome** when they:

- Follow [Agent Contribution Workflow](docs/contributing/ai_native_workflow.md)
- Link issues and stay in scope
- Run tests and linters before requesting review
- Update ripple docs and CHANGELOG when required
- Do not commit secrets or gitignored local plans

**Operators** must review agent output, run verification, and own the PR. Agents should not merge their own PRs unless explicitly delegated by maintainers.

---

## Architecture principles (do not violate in core)

- **Events before features** — meaningful actions emit to the audit spine.
- **Wrap, don't replace** — the user's loop stays in their host.
- **Layered identity** — `agent_ref` for humans/CI, ULID internal id, external ids in trailer.
- **Observers don't enforce** — policy lives in constraints + egress; observers subscribe only.

---

## Related documents

| Document | Purpose |
| :--- | :--- |
| [Agent Contribution Workflow](docs/contributing/ai_native_workflow.md) | Agents and supervising operators |
| [TESTING.md](docs/TESTING.md) | pytest, black, flake8, pre-PR checklist |
| [Code of Conduct](CODE_OF_CONDUCT.md) | Humans and autonomous logical systems |
| [SECURITY.md](SECURITY.md) | Vulnerability reporting |
| [PUBLISHING.md](docs/PUBLISHING.md) | PyPI and release tags |
| [ROADMAP.md](docs/ROADMAP.md) | Shipped vs deferred (do not re-delete vision) |
| [Issue templates](.github/ISSUE_TEMPLATE/) | Bug, docs, core, CLI, enhancement, integration |
| [`.github/labels.json`](.github/labels.json) | Label definitions |
| [CHANGELOG.md](CHANGELOG.md) | User-facing history |
| [CITATION.cff](CITATION.cff) | Software citation metadata |

---

## Maintainer: cutting a release

Contributor PRs must **not** bump version unless asked. Maintainers cut releases:

| Touch | Every release? |
| :--- | :--- |
| `pyproject.toml` → `version` | **Yes** |
| `aura/__init__.py` → `__version__` | **Yes** |
| `CHANGELOG.md` | **Yes** — move `[Unreleased]` to `## [X.Y.Z] - date` |
| `CITATION.cff` → `version`, `date-released` | **Yes** |
| Git tag `vX.Y.Z` + GitHub Release | **Yes** — triggers [PyPI publish](.github/workflows/publish-pypi.yml) |
| `README.md` install pin examples | Optional |

Thank you for helping make agent runs auditable, policy-bound, and portable.
