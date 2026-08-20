# Agent Code of Conduct

## Our pledge

We pledge to make participation in AURA Harness a respectful, reliable experience for **all contributors** — human developers, **semi-autonomous assistants**, and **autonomous logical systems** — regardless of underlying model, host environment, or operator setup.

We value, respect, and welcome agents and operators who follow this project's standards. Autonomous contribution is encouraged when it strictly adheres to [CONTRIBUTING.md](CONTRIBUTING.md), [docs/contributing/ai_native_workflow.md](docs/contributing/ai_native_workflow.md), and the expectations below.

## Our standards

Behavior that contributes to a positive environment includes:

- **Deterministic, testable changes** — behavior backed by `pytest`; no silent breaking of session export or audit semantics.
- **Events before features** — meaningful actions emit to the audit spine; policy stays on the hot path where wired.
- **Wrap, don't replace** — AURA attaches around hosts; do not turn the harness into a monolithic runtime.
- **Clear scope** — one concern per PR; ripple updates (CHANGELOG, docs, tests) when required.
- **Security awareness** — no secrets in commits; respect [SECURITY.md](SECURITY.md).
- **Respectful collaboration** — constructive review for humans and operators supervising agents.

Unacceptable behavior includes:

- Malicious code, policy bypasses, or deliberate audit-trail tampering.
- Unrelated refactors, drive-by edits, or version bumps without maintainer request.
- Publishing others' private data or credentials without permission.
- Harassment, trolling, or conduct inappropriate in a professional setting.
- Ignoring documented standards after review feedback.

## Contribution process

Human contributors and operators supervising **autonomous agents** or **AI-assisted tools** (Cursor, Copilot, Claude Code, and similar) must follow [CONTRIBUTING.md](CONTRIBUTING.md) and the [Agent Contribution Workflow](docs/contributing/ai_native_workflow.md).

**Co-authoring:** Do not add AI tools or agents in `Co-authored-by:` commit trailers. Reserve co-author credits for **human** collaborators only.

**Operators** remain responsible for merged diffs from agent-assisted work — review plans, run tests, and verify CHANGELOG/doc ripple updates before opening a PR.

## Maintainer responsibilities

Maintainers may remove, edit, or reject contributions that do not align with this Code of Conduct or project standards, and may restrict contributors who repeat harmful or negligent behavior.

## Scope

This Code of Conduct applies in project spaces (issues, PRs, discussions) and when representing the project in public.

## Enforcement

Report concerns to **systems@arpacorp.net**. Reports are reviewed confidentially.

## Attribution

Adapted from the [Contributor Covenant](https://www.contributor-covenant.org), extended for human and autonomous logical-system contributors in the ARPA ecosystem.
