# AURA Harness — Documentation

Single entry point for public docs. **Shipped behavior** lives in Tier 1–2; Tier 3 is positioning; **Optional** is vision and internal vocabulary — not required for onboarding.

---

## Tier 1 — Start

| Doc | Content |
|---|---|
| [onboarding.md](onboarding.md) | **Start here** — install → posture → agent → body → receipt |
| [getting-started.md](getting-started.md) | Install, minimal example, CLI |
| [using-aura.md](using-aura.md) | Membrane, postures, session export, SDK |
| [concepts.md](concepts.md) | Agent, session, identity, audit |
| [examples/README.md](../examples/README.md) | Runnable core scripts + integration demos |
| [integrations/README.md](integrations/README.md) | Docs hub — models, tools, frameworks |
| [../integrations/README.md](../integrations/README.md) | **Stack index** — path and run command per provider |
| [guides/reference-tool-host-capstone.md](guides/reference-tool-host-capstone.md) | ToolHost checklist (mock → live → Ollama) |

---

## Tier 2 — Build

| Doc | Content |
|---|---|
| [architecture.md](architecture.md) | Modules, data flow, extension surface |
| [stack-position.md](stack-position.md) | Optional — harness-centric input layers vs full ARPA stack |
| [sequencer.md](sequencer.md) | Prescriptive pipelines, gates, `when`, conformance |
| [skillware-integration.md](skillware-integration.md) | Skillware reference adapter (optional host) |
| [guides/aura-on-skillware.md](guides/aura-on-skillware.md) | Deep dive — Skillware as one ToolHost impl |
| [trust-paths.md](trust-paths.md) | `agent_ref`, ULID, ids trailer — no central ID service |
| [../integrations/identity/README.md](../integrations/identity/README.md) | Optional verified operator adapters (OIDC, Auth0, BYO) |
| [outputs.md](outputs.md) | JSONL, summary, audit report, hash chain, OTel |
| [TESTING.md](TESTING.md) | pytest, black, flake8, PR checklist |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Contributor guide (humans and agents) |
| [contributing/ai_native_workflow.md](contributing/ai_native_workflow.md) | Agent contribution workflow |

Copy [`.env.example`](../.env.example) to `.env` for local Ollama or cloud API keys. Never commit `.env`.

---

## Tier 3 — Decide

| Doc | Content |
|---|---|
| [comparison.md](comparison.md) | vs orchestrators, eval harnesses, tracing — loose / tight / tailored coats |
| [ROADMAP.md](ROADMAP.md) | Shipped vs deferred (sole deferrals file for public docs) |
| [README.md](../README.md) | Project entry, quick start, badges |

---

## Optional — vision & reference

Not on the default onboarding path. Kept for ARPA stack context and long-form design language.

| Doc | Content |
|---|---|
| [narrative.md](narrative.md) | Long-form vision (coat, SoulSig, cybernetics) |
| [three-rings.md](three-rings.md) | Envelope · Field · Adapter model |
| [aura-levels.md](aura-levels.md) | Autonomy tiers (enforcement roadmap) |
| [field-services.md](field-services.md) | Twelve parallel services — shipped vs planned |
| [glossary.md](glossary.md) | Terminology reference |

---

## Specifications

Stable contracts for adapters and tooling.

| File | Purpose |
|---|---|
| [aura-event.schema.json](../spec/aura-event.schema.json) | Audit record |
| [sequencer.schema.json](../spec/sequencer.schema.json) | Step pipeline |
| [manifest.schema.json](../spec/manifest.schema.json) | Session/agent declaration |
| [type-plugin.contract.md](../spec/type-plugin.contract.md) | Adapter interface |
| [capability.registry.json](../spec/capability.registry.json) | Operation ids (roadmap) |

---

## ARPA ecosystem (optional)

| Project | Link |
|---|---|
| Skillware | [github.com/arpahls/skillware](https://github.com/arpahls/skillware) |
| Rooms | [github.com/arpahls/rooms](https://github.com/arpahls/rooms) |
| Legacy Protocol | [github.com/arpahls/legacy-protocol](https://github.com/arpahls/legacy-protocol) |
| Avatar | [github.com/arpahls/avatar](https://github.com/arpahls/avatar) |

---

*ARPA Hellenic Logical Systems*
