# Agent contribution workflow

Written for **autonomous and semi-autonomous agents** working on AURA Harness. Human operators should read this before supervising agent work.

---

## Before you write code

1. Read [CONTRIBUTING.md](../../CONTRIBUTING.md) — especially [Ways to contribute](../../CONTRIBUTING.md#ways-to-contribute), [Ripple effects](../../CONTRIBUTING.md#ripple-effects-if-you-change-x-update-y), and [What to avoid](../../CONTRIBUTING.md#what-to-avoid).
2. **Open or claim an issue** — use the matching [issue template](../../.github/ISSUE_TEMPLATE/). Do not start large work without an issue reference.
3. **Plan in the issue or PR** — list files you will touch and ripple updates (tests, CHANGELOG, docs).
4. **Wait for maintainer feedback** on non-trivial or breaking changes before large diffs.

---

## Repository map (where things live)

| Path | Purpose |
| :--- | :--- |
| `aura/agents/` | Registry, profiles, `agent_ref`, ULID ids |
| `aura/core/` | Session, spine, constraints, conformance, audit report |
| `aura/membrane/` | Ingress context, egress guarded tool calls |
| `aura/sequencer/` | Prescriptive step pipelines |
| `aura/hosts/` | Skillware host, mock skills |
| `aura/observers/` | Parallel audit subscribers |
| `aura/exporters/` | JSONL summary, OTel JSONL |
| `aura/cli/` | `aura` CLI |
| `aura/api.py` | Public SDK |
| `tests/` | pytest suite |
| `examples/` | Runnable demos + README |
| `docs/` | User and contributor documentation |
| `spec/` | JSON schemas (contracts) |
| `.github/` | Issue templates, labels, workflows |

---

## Agent checklist (every PR)

- [ ] Issue linked (`Fixes #N` or `Refs #N`)
- [ ] Scope matches issue — no unrelated refactors
- [ ] `pytest` passes
- [ ] `black aura tests` — no diff
- [ ] `flake8 aura tests` — clean
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
- Commit `AURA_PLAN.md` (gitignored local plan).
- Invent features not in the issue — if scope grows, comment on the issue first.
- Mark PR checklist items you did not verify.

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
