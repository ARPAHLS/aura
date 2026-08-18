# Trust & identity (v0.1)

AURA does **not** run an identity service.

## Lite ID

- Every agent gets **`AURA-000n`** (monotonic, never reused).
- Optional **name** and **`ids.external`** for your existing identifiers.
- Live ID, SoulSig, or any future protocol attach as **optional metadata** in `ids` — not required to run.

## Sessions

Each run gets `aura_sess_*`. Events carry `aura_id`, session id, and the ID trailer for third-party correlation.

## Enrichment adapters (roadmap)

When present, adapters may add fields to events (constitution hash, UBH, etc.). Core behavior is unchanged when they are absent.

→ [concepts.md](concepts.md) · [getting-started.md](getting-started.md)
