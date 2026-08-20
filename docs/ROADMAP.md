# Roadmap

What is **shipped**, what is **next**, and what is **explicitly deferred**. Nothing is deleted from vision — it is staged.

---

## v0.1 — Runnable kernel ✓

| Delivered | Notes |
|---|---|
| Agent registry + `AURA-000n` | Lite ID; user IDs in `ids` trailer |
| Session modes | `script`, `task`, `continuous` |
| Audit spine | JSONL + session summary |
| Constraint engine | 4 built-in rule types + plugin hook |
| Conformance summary | Declared vs observed on close |
| Python SDK + basic CLI | Library-first |
| 3 examples | Minimal, guarded, task mode |
| Repo hygiene | Contributing, CoC, security, changelog |

---

## v0.2 (current) — Membrane + Sequencer + Skillware host ✓

| Delivered | Notes |
|---|---|
| **Membrane** | Ingress event, egress `guarded_tool_call` (`tool.intent` / `tool.call` / `tool.result`) |
| **Sequencer** | Linear steps, gates (`human_confirm`, …), retries, `step_id` on spine |
| **Skillware host** | Optional extra `skillware>=0.5.1`; `MockSkill` for tests |
| **Observers** | Registry + parallel dispatch on every event |
| **Agent profile** | `skills`, `sequencer`, `observers` fields |
| **Conformance** | Sequencer declared order vs completed steps |
| **Example 04** | Research → draft → approve → notify pipeline |
| **Docs** | [using-aura.md](using-aura.md), [skillware-integration.md](skillware-integration.md) |

---

## v0.3 — Adapters depth

| Item | Why |
|---|---|
| Type adapter contract (bind lifecycle) | Plug brains, skills, memory without core changes |
| Brain adapter docs + one live provider | Gemini / Claude / Ollama examples |
| Memory adapter docs | Frameworks + Postgres / vector / custom |
| Observer presets | Monitor, break, limit as named spine subscribers |
| Headless-only example | No Python loop file — API emit only |

---

## v0.4 — Governance depth

| Item | Why |
|---|---|
| Autonomy levels | Tiered permissions enforced on hooks |
| Conformance plugins | Rules from external policy files |
| Middleware ops | PII mask, prompt compress as ordered ops (schema exists) |
| Skill manifest rule merge | Constitution at bind time |

---

## v0.5+ — Ecosystem

| Item | Why |
|---|---|
| OTel exporter | Map AuraEvent → spans; enterprise observability |
| Legacy / Rooms bridges | Optional ARPA stack export |
| Analytics & compare-runs | Consumers of exported JSONL |
| Auto-discovery | LangGraph / MCP introspection where stable |
| HTTP fleet API | Remote session management — deferred |

---

## Explicitly not planned in core

- Identity service or Live ID requirement
- Hardcoded vendor list (models, memory backends)
- Replacing user loops — AURA wraps, never owns the body
- Full batch eval (RAGAS) — export feeds external eval

---

## How to influence priority

Open an issue with: use case, minimal repro, and whether you can contribute an adapter.
