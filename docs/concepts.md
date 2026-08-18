# Concepts

Plain-language model for AURA Harness v0.1.

## Agent

A logical entity you run under AURA. Gets a permanent **`AURA-000n`** ID for audit. You can also give it a **name** (`agent1test`).

Your own IDs (OpenAI assistant id, company id, etc.) live in the agent **`ids`** trailer — AURA does not replace them.

## Session

One run of an agent. Opens, records events, closes, exports logs.

| Mode | When to use |
|---|---|
| `script` | Starts and ends in one go (default) |
| `task` | Ends when you call `complete_goal()` |
| `continuous` | Long-running until error or manual stop |

## Event

Anything that happens during a session: `turn.start`, `tool.call`, `constraint.violated`, etc.

Every event is appended to the **audit trail** with causal links (`event_id`, `parent_id`, `trace_id`).

## Audit trail

The live, append-only record of a session. Official name for what the code calls the **audit spine**. Written to JSONL as events occur.

## Session export

What you get when a session closes: JSONL audit file + conformance **summary** JSON. Ship to logs, observability, or storage.

## Constitution

Rules, guardrails, and constraints the run must obey — on the agent profile, in YAML, or from adapters. Enforced during the run; checked again on close (conformance).

## Rule

A constraint checked when relevant events are emitted.

Built-in types: `max_tokens_per_step`, `confirm_before`, `allow_tools`, `deny_tools`.

## Conformance

On session close, AURA compares **declared rules** vs **observed events** and writes a summary.

## Runtime

How the body executes (Python script, future: LangGraph, etc.). Optional — you can emit events directly without a runtime adapter.

## Storage

Default: `~/.aura/` (override with `AURA_HOME`). Project-local: set `storage: project` in `aura.project.yaml` → `.aura/` in project root.
