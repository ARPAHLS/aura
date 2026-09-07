# Field Services

> **Optional reference** — not required for onboarding. See [INDEX.md](INDEX.md). **Operational preset reference:** [observers.md](observers.md).

The **twelve complementary services** that run **in parallel** with the agent loop — the coat, not bolt-ons.

Design language from [narrative.md](narrative.md). Operation ids live in [spec/capability.registry.json](../spec/capability.registry.json); packaged presets ship under `aura/observers/presets/`.

---

| Service | What it does | Status |
|---|---|---|
| **Monitor** | Loop state, tool calls, outputs, drift — continuously | **Shipped** — `preset: monitor` |
| **Audit** | Record what, when, why, under which permissions — always on | **Shipped** — audit spine + export |
| **Break** | Stop infinite retries, circular reasoning, runaway tools | **Shipped** — `preset: break` |
| **Track** | Task progress, resource use, retries, lineage across steps | Partial — `preset: goal_drift` + `preset: schedule_slo` ([#46](https://github.com/ARPAHLS/aura/issues/46)); wire via `spectrum.services` ([#77](https://github.com/ARPAHLS/aura/issues/77)) |
| **Limit** | Budgets, rate caps, scope, spectrum permissions | **Shipped** — `preset: limit` + `spectrum.services: [limit]` ([#77](https://github.com/ARPAHLS/aura/issues/77)); `spectrum.level` enforces egress bind |
| **Safeguard** | Enforce guardrails from manifest and constitution | Partial — constraint engine + manifest merge |
| **Wake** | Restart stalled loops, re-queue work, resume | Planned |
| **Conserve** | Reduce token waste — redundant calls, repeated failures | Planned |
| **Recover** | Catch errors, retry logic, fallback paths | Partial — sequencer retries |
| **Remember** | Memory discipline — keep, compress, discard, persist | Planned (memory adapter) |
| **Learn** | Capture mistakes and outcomes for next iteration | Planned |
| **Attach** | Modular extensions — skills, schedulers, observers | **Shipped** — observers + Skillware host |

---

## vs Hook Pipeline vs Sequencer

| Layer | When |
|---|---|
| **Field services** | Parallel — consume AuraEvent stream |
| **Hook pipeline** | Per tick — intercept loop (`pre_tool`, `on_drift`, …) |
| **Sequencer** | Declared multi-step pipelines — skills, gates, middleware |

All three emit to the same **audit spine**.

---

## Spectrum toggle

Manifest `spectrum.services` lists field services to wire at session open when the profile has an explicit `spectrum` block ([#77](https://github.com/ARPAHLS/aura/issues/77)). `audit` is always on via the spine — listing it is metadata only. When `services` is omitted, level defaults apply: `high` wires `monitor`, `full` wires `monitor` + `break`; `low` / `mid` wire nothing extra. Explicit `profile.observers[]` wins over duplicate service presets. Unknown service names emit `observer.note` (or `observer.alert` when `strict_services: true`); session open never fails by default. Per-service tuning: `spectrum.service_config.{service}`. Enforcement posture: `spectrum.level` — see [aura-levels.md](aura-levels.md).

---

## Attachments (extensions)

Beyond core twelve — observability modules, resource governors, temporal schedulers, event bridges, recovery playbooks. Registered as **op plugins** or **type plugins** — same extensibility model.

See [architecture.md](architecture.md) · [outputs.md](outputs.md) · [ROADMAP.md](ROADMAP.md)
