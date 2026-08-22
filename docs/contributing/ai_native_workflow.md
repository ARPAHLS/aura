# Agent contribution workflow

Written for **autonomous and semi-autonomous agents** working on AURA Harness. Human operators should read this before supervising agent work.

---

## Before you write code

1. Read [CONTRIBUTING.md](../../CONTRIBUTING.md) — especially [Ways to contribute](../../CONTRIBUTING.md#ways-to-contribute), [Ripple effects](../../CONTRIBUTING.md#ripple-effects-if-you-change-x-update-y), and [What to avoid](../../CONTRIBUTING.md#what-to-avoid).
2. **Open or claim a GitHub issue** — use the matching [issue template](../../.github/ISSUE_TEMPLATE/). Do not start large work without an issue reference.
3. **Plan in the issue or PR** — list files you will touch and ripple updates (tests, CHANGELOG, docs).
4. **Wait for maintainer feedback** on non-trivial or breaking changes before large diffs.

### Issue hygiene

- Link related work with full GitHub URLs: `https://github.com/ARPAHLS/aura/issues/<N>`.
- Do **not** reference internal planning file prefixes (`issues/12-…`) or target release versions (`v0.x`) in GitHub issue bodies.
- Use **Phase C / D / E** or plain *shipped* vs *planned* language. Semver bumps are maintainer-only ([CHANGELOG](../../CHANGELOG.md)).

---

## Repository map (where things live)

| Path | Purpose |
| :--- | :--- |
| `aura/agents/` | Registry, profiles, `agent_ref`, ULID ids |
| `aura/core/` | Session, spine, constraints, conformance, audit report, compare, spectrum stub |
| `aura/membrane/` | Ingress context, egress guarded tool calls |
| `aura/sequencer/` | Prescriptive step pipelines |
| `aura/hosts/` | SkillwareHost (reference adapter), mock skills |
| `aura/observers/` | Parallel audit subscribers |
| `aura/exporters/` | JSONL summary, OTel JSONL |
| `aura/cli/` | `aura` CLI (interactive menu, agent set, config/paths, export, compare) |
| `aura/api.py` | Public SDK (`agent()`, `session()`, `emit()`) |
| `aura/runtime/` | Script wrap helpers |
| `tests/` | pytest suite (see below) |
| `examples/` | Runnable demos (nested folders today; flat restructure planned) |
| `docs/` | User and contributor documentation |
| `spec/` | JSON schemas (contracts) |
| `.github/` | Issue templates, labels, workflows |

### Shipped surface (know what exists)

- **Identity:** `agent_ref`, ULID `aura_id`, `policy_version`, hash chain on spine events
- **Session export:** `.jsonl`, `.summary.json` (with `audit_report`), `.otel.jsonl`
- **CLI:** `aura agent create/set`, `config show`, `paths`, `run`, `logs`, `export`, `export-otel`, `compare`
- **SDK helpers:** `AuditSpine.from_jsonl()` for disk verify; `compare_sessions()` includes `agent_ref` and `hash_chain_valid` diffs
- **CI:** Python 3.10–3.13 matrix on every PR; gate job `lint-test` ([`ci.yml`](../../.github/workflows/ci.yml))

---

## Test modules

| File | Focus |
| :--- | :--- |
| `tests/test_core.py` | Registry, spine, constraints, session export |
| `tests/test_core_gaps.py` | Config merge, tamper, compare edge cases, session modes |
| `tests/test_v02.py` | Sequencer, membrane, Skillware host |
| `tests/test_v03.py` | Identity, audit report, hash chain, compare |
| `tests/test_cli.py` | CLI commands and exit codes |
| `tests/test_examples_smoke.py` | Example script smoke runs |

Run the full suite before opening a PR (`pytest` — currently 64 tests).

---

## Agent checklist (every PR)

- [ ] GitHub issue linked (`Fixes #N` or `Refs #N`)
- [ ] Scope matches issue — no unrelated refactors
- [ ] `pytest` passes
- [ ] `black aura tests` — no diff
- [ ] `flake8 aura tests` — clean
- [ ] CI green — [`lint-test`](../../.github/workflows/ci.yml) job on the PR
- [ ] Tests added/updated for behavior changes
- [ ] [CHANGELOG.md](../../CHANGELOG.md) updated under `[Unreleased]` when user-visible
- [ ] Docs/examples updated per [ripple table](../../CONTRIBUTING.md#ripple-effects-if-you-change-x-update-y)
- [ ] No secrets, `.env`, or local paths committed
- [ ] No version bump in `pyproject.toml` / `CITATION.cff` unless explicitly requested
- [ ] No emojis in code, commits, or PR title
- [ ] No `Co-authored-by:` trailers for AI tools

---

## Verify locally

```bash
pip install -e ".[dev]"
pytest
black aura tests
flake8 aura tests
```

Optional Skillware integration tests:

```bash
pip install -e ".[dev,skillware]"
pytest
```

---

## What agents must not do

- Bypass the membrane for tool calls in examples/tests meant to demonstrate policy (use `SkillwareHost` or `emit()`).
- Delete or gut vision/roadmap content without maintainer direction.
- Commit `AURA_PLAN.md` or `issues/` (gitignored local planning).
- Invent features not in the issue — if scope grows, comment on the issue first.
- Mark PR checklist items you did not verify.
- Put internal backlog numbers or v0.x release targets in GitHub issue text.

---

## Operator supervision

If you are a **human operator** directing an agent:

1. Approve the file list and ripple plan before implementation.
2. Run tests locally or confirm CI green before merge.
3. Own the fork, commit authorship, and PR — you are accountable for the diff.

---

## Questions

- [Issues](https://github.com/ARPAHLS/aura/issues)
- [CONTRIBUTING.md](../../CONTRIBUTING.md)
- systems@arpacorp.net
