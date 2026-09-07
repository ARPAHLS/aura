# Example 07 — Observer presets (Monitor + Break + Limit)

Shows **after-call** membrane analytics — observers subscribe to the spine and emit side signals. They **do not block** egress; enforcement stays at `tool.call`.

| Preset | Emits | Use |
|---|---|---|
| **monitor** | `observer.note` | Counts, timing, soft repeat warnings |
| **break** | `observer.alert` | Circuit-breaker when identical tool intents exceed threshold |
| **limit** | `observer.note` + `observer.alert` | Rate/token budget warnings then breach alerts |

Two wiring paths:

1. **Explicit** — `profile.observers[]` with `{ preset: monitor }` / `{ preset: break }`
2. **Declarative** — `spectrum.services: [limit]` on a profile with a `spectrum` block ([#77](https://github.com/ARPAHLS/aura/issues/77))

Uses `MockSkill` for the explicit path; limit demo uses emit-only `tool.call` events.

```powershell
.venv\Scripts\activate
python examples/07-observer-presets/main.py
```

Inspect JSONL for `observer.note` / `observer.alert` and `session.open` → `spectrum.services_activation`.

→ [field-services.md](../../docs/field-services.md) · [sequencer.md](../../docs/sequencer.md) · [reference-tool-host-capstone.md](../../docs/guides/reference-tool-host-capstone.md)
