# Concepts

Plain-language model for AURA Harness.

## Agent

A logical entity you run under AURA.

| Field | Role |
|---|---|
| **`agent_ref`** | Stable slug for humans and CI, e.g. `acme/compliance-bot` |
| **`aura_id`** | Internal ULID (default) or your supplied id |
| **`name`** | Optional alias for lookup |
| **`ids`** | Trailer for tenant, Skillware, and your external ids |

Legacy profiles with `AURA-000n` ids still load. See [trust-paths.md](trust-paths.md).

Profile fields also include **`skills`**, **`sequencer`** spec, **`observers`**, and **`rules`**.

## Session

One run of an agent. Opens (with **ingress**), records events, closes, exports logs.

| Mode | When to use |
|---|---|
| `script` | Starts and ends in one go (default) |
| `task` | Ends when you call `complete_goal()` |
| `continuous` | Long-running until error or manual stop |

## Membrane

The runtime **coat** around your body — not the loop itself.

| Boundary | Meaning |
|---|---|
| **Ingress** | Context normalized at session open |
| **Body** | Your host loop (script, Skillware, framework) |
| **Egress** | Policy + audit before tools execute |

## Event

Anything that happens during a session: `turn.start`, `tool.call`, `sequencer.step.start`, `membrane.ingress`, etc.

Every event is appended to the **audit trail** with causal links (`event_id`, `parent_id`, `trace_id`, optional `step_id`).

## Audit trail

The live, append-only record of a session. Official name for what the code calls the **audit spine**. Written to JSONL as events occur.

## Session export

What you get when a session closes: JSONL audit file + conformance **summary** JSON (+ OTel JSONL by default). Ship to logs, observability, or storage.

With `export=False`, no files are written, but `run.summary` and `run.audit_report` are still built in memory when the context exits. Summary and OTel files commit atomically on disk export; a failed export leaves neither artifact updated.

After close, the session is sealed — further `emit` or `approve` calls raise `SessionClosedError`.

## Constitution

Rules, guardrails, and constraints the run must obey — on the agent profile, in YAML, or from adapters. Enforced during the run; checked again on close (conformance).

## Rule

A constraint checked when relevant events are emitted.

Built-in types: `max_tokens_per_step`, `confirm_before`, `allow_tools`, `deny_tools`.

## Conformance

On session close, AURA compares **declared rules at open** (and sequencer step order) vs **observed events** and writes a summary. The open-time `open_snapshot_hash` in the summary matches conformance when base rules are unchanged; runtime skill binds may update `snapshot_hash` for live constraint checks.

## Sequencer

Prescriptive multi-step pipeline **inside** a session — not emergent model tool chaining. You declare steps upfront; AURA enforces order on close.

## Observer

Parallel subscriber to the audit trail. Must not block the host. Used for metrics, alerts, or custom analytics.

## Runtime / Body

How the body executes (Python script, Skillware host, future: LangGraph). AURA wraps; it does not own the loop.

## Storage

Default: `~/.aura/` (override with `AURA_HOME`). Project-local: set `storage: project` in `aura.project.yaml` → `.aura/` in project root.

→ [onboarding.md](onboarding.md) — storage, identity, and first run · [glossary.md](glossary.md)
