# Reference tool-host capstone

End-to-end **AURA membrane** coverage for hosts that execute capabilities through egress — with one live reference adapter (Skillware) to prove the pattern, not to define the product.

**AURA is the coat.** The body (LLM, cron, framework) and tools (Skillware, MCP, plain callables) stay outside. This checklist is what “360° reference host” means for epic [#12](https://github.com/ARPAHLS/aura/issues/12).

---

## Problem without AURA

| Without | Risk |
|---|---|
| Direct `skill.execute()` / raw API calls | No causal audit, no policy at boundary |
| Ad-hoc logging | Not tamper-evident, hard to compare runs |
| Observers that block silently | Policy bypass — enforcement must be at egress |

## What AURA adds

| Plane | Mechanism |
|---|---|
| **Before call** | `membrane.ingress`, `host.bind`, `skill.registered`, merged constitution |
| **At call** | `tool.intent` → `tool.call` → constraints → `tool.result` |
| **After call** | Observer presets (`monitor`, `break`), session export, OTel |

---

## Spine checklist (every reference run)

Open `.aura/sessions/<id>.jsonl` and confirm:

| # | Event kind | Meaning |
|---|---|---|
| 1 | `membrane.ingress` | Session context bound |
| 2 | `session.open` | `agent_ref`, `policy_version`, mode |
| 3 | `host.bind` | First capability registered on host |
| 4 | `skill.registered` | Per-skill manifest snapshot + `bound_skill_ids` |
| 5 | `sequencer.step.*` | Declared pipeline order (if using sequencer) |
| 6 | `tool.intent` / `tool.call` / `tool.result` | Egress audit per capability |
| 7 | `pipeline.verdict` or host logic | Host decision before body LLM (recommended) |
| 8 | `observer.note` / `observer.alert` | Optional after-call analytics |
| 9 | `sequencer.step.skipped` | Conditional steps when prior result fails `when` |
| 10 | `session.close` | Normal close |
| — | Summary `audit_report.hash_chain_valid` | Tamper-evident export |

---

## Runnable paths (mock → live → body LLM)

| Path | Command | Coat |
|---|---|---|
| **Mock host** | `python examples/06-skillware-sequencer-chain/main.py` | Tight — sequencer + conditional steps |
| **Live registry** | `$env:SKILLWARE_LIVE=1` + same | Same API, real bundled skills |
| **Observers** | `python examples/07-observer-presets/main.py` | Analytics only |
| **Emit-only** | `python examples/08-emit-only-loop/main.py` | Loose — no tool host |
| **Body + tools** | `python integrations/skillware/ollama_skill_loop.py` | LLM body + Skillware egress |

Swap Skillware for your runtime — keep `ToolHost.execute()` through egress.

---

## ToolHost contract

```python
from aura.hosts import ToolHost, SkillwareHost  # SkillwareHost is one implementation

with agent("demo", skills=[...]).session() as run:
    host: ToolHost = SkillwareHost(run._session)  # or your adapter
    host.register(capability)
    host.execute(skill_id, tool_label, args, step_id=optional)
```

See `aura/hosts/protocol.py`.

---

## Sequencer conditional steps

Skip a step when a prior step’s result does not match:

```yaml
- id: compress
  type: skill
  ref: rewriter
  depends_on: [scan]
  when:
    prior_step: scan
    field: is_safe
    equals: true
```

Emits `sequencer.step.skipped` — order remains auditable; downstream host logic sets `pipeline.verdict`.

---

## CI tiers

| Tier | Command |
|---|---|
| Gate | `pytest --ignore=tests/integration` |
| Live registry | `pytest tests/test_skillware_integration.py` |
| Full stack (local) | `pytest tests/integration/ -v` |

---

## Related

- [using-aura.md](../using-aura.md)
- [sequencer.md](../sequencer.md)
- [aura-on-skillware.md](aura-on-skillware.md) — reference adapter deep dive (optional stack)
- [integrations/skillware/](../../integrations/skillware/) — scripts only
