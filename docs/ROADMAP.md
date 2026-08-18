# Roadmap

What is **in v0.1**, what is **next**, and what is **explicitly deferred**. Nothing is deleted from vision — it is staged.

---

## v0.1 (current) — Runnable kernel

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

## v0.2 — Adapters

| Item | Why |
|---|---|
| Type adapter contract (implemented bind lifecycle) | Plug brains, skills, memory without core changes |
| Skillware reference adapter | [github.com/arpahls/skillware](https://github.com/arpahls/skillware) tool events on spine |
| Brain adapter docs + one live provider | Gemini / Claude / Ollama examples |
| Memory adapter docs | Frameworks + Postgres / vector / custom |
| Headless-only example | No Python loop file — API emit only |

---

## v0.3 — Observers & templates

| Item | Why |
|---|---|
| Observer presets | Monitor, break, limit as spine subscribers — not twelve hardcoded modules |
| Runtime templates | Spin up minimal Python loop scaffolds |
| LangGraph / MCP probe docs | Reduce manual hook burden |

---

## v0.4 — Governance depth

| Item | Why |
|---|---|
| Autonomy levels | Tiered permissions (low → full) enforced on hooks |
| Conformance plugins | Rules from external policy files |
| Middleware ops | PII mask, prompt compress as ordered ops |

---

## v0.5+ — Ecosystem

| Item | Why |
|---|---|
| OTel exporter | Map AuraEvent → spans; enterprise observability |
| Legacy / Rooms bridges | Optional ARPA stack export |
| Sequencer module or separate product | Multi-step pipelines with retries/gates |
| Analytics & compare-runs | Consumers of exported JSONL |
| Auto-discovery | Framework introspection where stable |

---

## Explicitly not planned in core

- Identity service or Live ID requirement
- Hardcoded vendor list (models, memory backends)
- Replacing user loops — AURA wraps, never owns the body

---

## How to influence priority

Open an issue with: use case, minimal repro, and whether you can contribute an adapter.
