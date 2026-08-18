# Trust Paths

Two deployment modes — same harness.

---

## Live ID + SoulSig

Accountable autonomy. Production, regulated workloads, continuity guarantees.

```
Live ID (UBH) → SoulSig birth → Manifest → AURA wraps body → run
     → sessions under agent → Legacy · Rooms
```

Manifest populated from birth contract: identity, constitution, brain profile, guardrails, spectrum.

---

## Bring Your Own

Universal wrap. Any stack, any identity label, user-owned export.

```
Declare bindings → AURA wraps loop → AuraEvent output → your storage
```

| If omitted | Default |
|---|---|
| Identity | Auto `session_id` |
| SoulSig | Manifest guardrails only |
| Legacy bridge | User export destination |

---

## Comparison

| | Live ID path | Bring your own |
|---|---|---|
| Setup | Registration, agreement | API / manifest file |
| UBH binding | Yes | No |
| Constitution | SoulSig | Manual |
| Audit retention | Live ID + Legacy | User-owned |
| Effective level cap | Full tier available | Conservative defaults |

---

## Identifiers

| ID | Lifetime |
|---|---|
| **Live ID** | Permanent — human/org, UBH |
| **Agent ID** | Permanent — logical system entity |
| **SoulSig** | Permanent on agent — birth contract |
| **Session ID** | One runtime activation |

---

## CLI

```bash
aura auth login
aura agents list
aura run --agent <id>
```

→ [architecture.md](architecture.md)
