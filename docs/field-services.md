# Field Services

The **twelve complementary services** that run **in parallel** with the agent loop — the coat, not bolt-ons.

From [narrative.md](narrative.md). Implemented as **operation plugins** in `aura/ops/`, registered in [spec/capability.registry.json](../spec/capability.registry.json).

---

| Service | What it does |
|---|---|
| **Monitor** | Loop state, tool calls, outputs, drift — continuously |
| **Audit** | Record what, when, why, under which permissions — **always on (Job B)** |
| **Track** | Task progress, resource use, retries, lineage across steps |
| **Limit** | Budgets, rate caps, scope, AURA Level permissions |
| **Safeguard** | Enforce guardrails from manifest, soul contract, memory layer, skill constitution, or elsewhere |
| **Wake** | Restart stalled loops, re-queue work, resume |
| **Break** | Stop infinite retries, circular reasoning, runaway tools |
| **Conserve** | Reduce token waste — redundant calls, repeated failures |
| **Recover** | Catch errors, retry logic, fallback paths |
| **Remember** | Memory discipline — keep, compress, discard, persist |
| **Learn** | Capture mistakes and outcomes for next iteration |
| **Attach** | Modular extensions — skills, schedulers, observers |

---

## vs Hook Pipeline vs Sequencer

| Layer | When |
|---|---|
| **Field services** | Parallel — consume AuraEvent stream |
| **Hook pipeline** | Per tick — intercept loop (`pre_tool`, `on_drift`, …) |
| **Sequencer** | Declared multi-step pipelines — skills, gates, middleware |

All three emit to the same **audit spine**.

---

## Spectrum Toggle

Manifest `spectrum.services` selects which field services activate for a session. `audit` is non-optional in production profiles.

---

## Attachments (Extensions)

Beyond core twelve — observability modules, resource governors, temporal schedulers, event bridges, recovery playbooks. Registered as **op plugins** or **type plugins** — same extensibility model.

See [design/direction-draft.md](design/direction-draft.md) · [outputs.md](outputs.md)
