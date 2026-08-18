# Three Rings

Cross-cutting model from [design/direction-draft.md](design/direction-draft.md).

---

```
┌─────────────────────────────────────────────────────────┐
│  ENVELOPE — Identity, SoulSig, Legacy export, trust tier │
│  ┌───────────────────────────────────────────────────┐  │
│  │  FIELD — Parallel services (monitor, limit, …)    │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │  ADAPTER — Hooks on the loop (Soma)         │  │  │
│  │  │     [ Brain → tool → result → … ]           │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

| Ring | Role |
|---|---|
| **Adapter** | Hook pipeline on loop ticks — pre/post tool, drift, error |
| **Field** | Twelve services + op plugins — parallel on event stream |
| **Envelope** | Identity context, constitution hash, export to Legacy/Rooms |

**Sequencer** and **middleware stack** sit between Field and Adapter when manifest declares pipelines.

---

## Cybernetic Frame

Wiener's governor: compare where you are vs where you should be → self-correct before drift becomes damage. AURA is that governor for agent loops.

---

## Greek Frame

**αύρα** — surrounding presence, breath, field. Not the flame — the conditions that keep the flame steady. Consciousness-as-frequency rhymes (see human unit essay) — harness as tuning, not substance.

Also referenced as **AVRA**.
