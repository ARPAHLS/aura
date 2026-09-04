# AURA + ToolHost — follow-up issues (suggested)

Track these **after** closing the reference ToolHost epic ([#12](https://github.com/ARPAHLS/aura/issues/12), PRs #42 + #43). Skillware remains one live reference adapter — these items extend CI, docs, and demos without changing the core coat.

**Shipped with #12 closure:** `ToolHost` protocol ([#22](https://github.com/ARPAHLS/aura/issues/22)), manifest merge + `skill.registered`, Monitor + Break observer presets ([#34](https://github.com/ARPAHLS/aura/issues/34)), ingress bind enrichment ([#33](https://github.com/ARPAHLS/aura/issues/33)), OTel promoted attributes ([#35](https://github.com/ARPAHLS/aura/issues/35)), capstone guide ([#40](https://github.com/ARPAHLS/aura/issues/40)), examples 05–08 ([#41](https://github.com/ARPAHLS/aura/issues/41) partial), example smoke ([#16](https://github.com/ARPAHLS/aura/issues/16)).

→ Canonical checklist: [reference-tool-host-capstone.md](reference-tool-host-capstone.md)

---

## CI & quality

| Title | Scope |
|---|---|
| **Integration script smoke in CI** | Run `reference_tool_host.py` mock path; examples 05–08 without `SKILLWARE_LIVE` |
| **Provider integration opt-in job** | Manual `workflow_dispatch` with secrets for OpenAI/Anthropic/Gemini smoke |
| **Reusable CI workflow** ([#17](https://github.com/ARPAHLS/aura/issues/17)) | Single workflow definition shared by PR and publish jobs |

---

## Documentation & examples

| Title | Scope |
|---|---|
| **Flat examples restructure** ([#21](https://github.com/ARPAHLS/aura/issues/21)) | Align paths referenced in docs after examples layout change (remainder of [#41](https://github.com/ARPAHLS/aura/issues/41)) |
| **Multi-provider comparison page** | One doc comparing Ollama vs GPT vs Claude vs Gemini with the same skill chain (extends capstone) |
| **Skill catalog appendix** | Table of bundled Skillware skills: offline vs API, suggested AURA guardrails |
| **Docs sweep** ([#14](https://github.com/ARPAHLS/aura/issues/14)) | Cross-link INDEX, ROADMAP — onboarding ([#13](https://github.com/ARPAHLS/aura/issues/13)) shipped |
| ~~Integrations layout + Ollama~~ | **Shipped** ([#19](https://github.com/ARPAHLS/aura/issues/19), [#20](https://github.com/ARPAHLS/aura/issues/20), PRs #51/#53) |
| **Skillware 0.5.4 sync** | **Shipped** — semver range, chains vs sequencer docs, example 10 metrics snapshot |
| **Audit pipeline example** | **Shipped** ([#23](https://github.com/ARPAHLS/aura/issues/23)) — `examples/audit_pipeline.py` |

---

## Product / adapter

| Title | Scope |
|---|---|
| **Limit observer preset** | Rate/budget circuit breaker (third packaged preset alongside monitor, break) |
| **Constitution → rules mapper** | Optional transform of Skillware constitution text to AURA machine rules (opt-in) |
| **`SkillwareHost` async execute** | If Skillware adds async skills, mirror at egress |

---

## Reference demos (nice-to-have)

| Skill | Demo idea |
|---|---|
| `compliance/pii_masker` | Pre-LLM redaction pipeline with Ollama micro-f1-mask |
| `office/gmail_handler` | Sequencer with `human_confirm` on send |
| `compliance/tos_evaluator` | Legal review chain with export for audit |

Each should follow the same pattern: **body LLM optional**, **skills at egress**, **AURA session export**.

---

## How to use this doc

Copy rows into GitHub issues when ready. Link back to [reference-tool-host-capstone.md](reference-tool-host-capstone.md) for the AURA-first integration story and [aura-on-skillware.md](aura-on-skillware.md) for the Skillware reference path.
