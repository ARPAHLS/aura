# Roadmap

Shipped work stays in [CHANGELOG.md](../CHANGELOG.md). This file lists what is **next**.

---

## Shipped (summary)

| Version | Highlights |
|---|---|
| **v0.1** | Registry, sessions, constraints, JSONL export, SDK |
| **v0.2** | Membrane, sequencer, Skillware host, observers |
| **v0.3** | ULID + `agent_ref`, audit report, hash chain, OTel export, compare CLI |

---

## Next

| Item | Why |
|---|---|
| Brain / memory adapters | Plug models and retention without core changes |
| Named observer presets | Monitor, break, limit as packaged subscribers |
| Skill manifest rule merge | Constitution at Skillware bind time |
| Middleware ops | PII mask, compress — schema exists |
| Signed audit packs | WORM / external sink hooks |
| HTTP fleet API | Remote session management |
| Auto-discovery | LangGraph / MCP probe where stable |

---

## Explicitly not in core

- Central identity service or Live ID requirement (adapter only, when available)
- Replacing user loops — AURA wraps, never owns the body
- Full batch eval (RAGAS) — export feeds external pipelines

---

Open an issue with use case + minimal repro to influence priority.
