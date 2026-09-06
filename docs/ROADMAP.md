# Roadmap

Shipped work stays in [CHANGELOG.md](../CHANGELOG.md). This file lists what is **next**.

---

## Shipped (summary)

| Version | Highlights |
|---|---|
| **v0.1** | Registry, sessions, constraints, JSONL export, SDK |
| **v0.2** | Membrane, sequencer, Skillware host, observers |
| **v0.3** | ULID + `agent_ref`, audit report, hash chain, OTel export (+ promoted attrs), compare CLI, ToolHost reference coat |
| **v0.3.4** | Onboarding guide, `report show`, flat core examples, Monitor/Break presets, capstone + examples 05–08 |
| **Unreleased (on main / open PRs)** | Identity ([#55](https://github.com/ARPAHLS/aura/issues/55)), session invariants ([#15](https://github.com/ARPAHLS/aura/issues/15)), integrations ([#19](https://github.com/ARPAHLS/aura/issues/19), [#20](https://github.com/ARPAHLS/aura/issues/20)), comparison refresh ([#39](https://github.com/ARPAHLS/aura/issues/39)), audit pipeline ([#23](https://github.com/ARPAHLS/aura/issues/23)), **spectrum enforcement** ([#27](https://github.com/ARPAHLS/aura/issues/27)), **goal drift + schedule SLO** ([#46](https://github.com/ARPAHLS/aura/issues/46)), Skillware 0.5.4 sync, host stress sim + coat flow report |

---

## Next

| Item | Why |
|---|---|
| **`spectrum.services[]` runtime activation** | Metadata on ingress today; toggling Monitor/Break/Limit presets per service list |
| **Constitution / schema checks at high bind** | Skill allowlist shipped; manifest schema validation at egress still open |
| Brain / memory adapters | Plug models and retention without core changes |
| **Limit** observer preset | Rate/budget circuit breaker — goal/SLO presets shipped ([#46](https://github.com/ARPAHLS/aura/issues/46)); Limit still planned ([#79](https://github.com/ARPAHLS/aura/issues/79)) |
| Middleware ops | PII mask, compress — schema exists |
| Signed audit packs | WORM / external sink hooks |
| HTTP fleet API | Remote session management |
| DID / VC operator adapter | Decentralized identity enrichment (follow-up to #55) |
| Auto-discovery | LangGraph / MCP probe where stable |

**Shipped in v0.2–v0.3 (reference ToolHost epic):** `ToolHost` protocol, manifest merge at bind, Monitor + Break observer presets, ingress bind enrichment, OTel promoted attributes, sequencer `when`, capstone guide, examples 01–09. Details in [CHANGELOG.md](../CHANGELOG.md) and [reference-tool-host-capstone.md](guides/reference-tool-host-capstone.md).

---

## Explicitly not in core

- Central identity service or Live ID requirement (adapter only, when available)
- Replacing user loops — AURA wraps, never owns the body
- Full batch eval (RAGAS) — export feeds external pipelines

---

Open an issue with use case + minimal repro to influence priority.
