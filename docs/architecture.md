# Architecture

*Index: [INDEX.md](INDEX.md)*

---

## Principles

1. **Hardcode core, never hardcode the world** — inputs and ops are plugins
2. **Wrap, don't replace** — the loop stays in the body
3. **Events before features** — AuraEvent spine is the foundation
4. **Conformance + audit** — run as declared; log everything
5. **Same harness, many inputs** — any brain, skills framework, identity model

---

## Layers

```
TYPE PLUGINS       brain · identity · skills · memory · soma · drive · guardrails · …
       ↓
BRIDGES            Live ID · Rooms · Legacy · … (when present)
       ↓
CORE               registry · session · spine · pipeline · conformance · spectrum
       ↓
SEQUENCER          steps · middleware · retries · state
       ↓
OPS                field services · middleware handlers
       ↓
EXPORTERS          JSON · OTel · CSV · webhook · continuity stream
```

---

## Mechanisms

| Mechanism | Doc |
|---|---|
| Three rings | [three-rings.md](three-rings.md) |
| Field services | [field-services.md](field-services.md) |
| AURA Levels | [aura-levels.md](aura-levels.md) |
| Sequencer | [sequencer.md](sequencer.md) |
| Type registry | [spec/type-plugin.contract.md](../spec/type-plugin.contract.md) |
| Trust paths | [trust-paths.md](trust-paths.md) |
| Stack position | [stack-position.md](stack-position.md) |
| Outputs | [outputs.md](outputs.md) |

---

## Runtime Flow

1. Parse manifest
2. Validate type bindings
3. Resolve capabilities → spectrum + effective operations
4. Open session
5. Bind types; register hooks
6. Run sequencer or ad-hoc loop
7. Hook pipeline on every tick; spine records all
8. Field services parallel on event stream
9. Conformance compares observed vs declared
10. Close session → exporters → bridges

---

## Hook Pipeline

`pre_manifest` → `post_bind` → `pre_turn` → `pre_step` → `pre_tool` → `post_tool` → `post_step` → `on_drift` → `on_error` → `turn_end` → `post_session`

---

## Robustness

Robust · Safe · Secure · Fast · Precise · Auditable · Maintainable · Continuous · Memory-correct · Self-healing

An agent under AURA is guaranteed to **fail visibly, bounded, and recoverably**.

→ [narrative.md](narrative.md)
