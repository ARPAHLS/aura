<div align="center">

<img src="docs/assets/aura_splash.png" alt="αύρα — AURA Harness" width="550" />

<br>

**AURA Harness - The runtime coat around agent loops.**

*Also AVRA · αύρα — the field that wraps what is inside it.*

<br>

[![ARPA Hellenic Logical Systems](https://img.shields.io/badge/ARPA-Hellenic%20Logical%20Systems-A793AC?labelColor=e8e0e4&style=flat-square)](https://github.com/arpahls)
[![Manifesto](https://img.shields.io/badge/docs-manifesto-f5e6d3?labelColor=e8e0e4&style=flat-square)](https://github.com/ARPAHLS/manifesto)
[![Narrative](https://img.shields.io/badge/docs-narrative-d4e4f7?labelColor=e8e0e4&style=flat-square)](docs/narrative.md)
[![Architecture](https://img.shields.io/badge/docs-architecture-c8dde8?labelColor=e8e0e4&style=flat-square)](docs/architecture.md)
[![Stack](https://img.shields.io/badge/docs-stack%20position-b8d4e8?labelColor=e8e0e4&style=flat-square)](docs/stack-position.md)
[![Spec](https://img.shields.io/badge/spec-schemas-e8f0f8?labelColor=e8e0e4&style=flat-square)](spec/)

<br>

[Overview](#overview) ·
[Stack](#where-aura-sits-in-the-stack) ·
[How It Works](#how-it-works) ·
[Levels](#aura-levels) ·
[Documentation](#documentation) ·
[Development](#development)

</div>

---

## Overview

**αύρα** *(aura)* — in Greek, a surrounding presence. Not the loop itself. The conditions that make the loop viable.

AURA Harness wraps the active **body** while it runs: monitoring, enforcing, recording, recovering. It takes **inputs** — brain, identity, skills, memory, guardrails, host — and produces **normalized output**: causal audit trails, conformance records, exports to continuity and environment.

| | |
|---|---|
| **Conformance** | The agent runs as declared — goals, guardrails, constitution, level |
| **Auditability** | Every step, tool call, API touch, correction — logged in order |

---

## Where AURA Sits in the Stack

Identity births the soul. The soul inhabits a body. Feeds converge on the body while it runs. **AURA wraps the body** and projects outward into space and continuity.

```mermaid
flowchart LR
    LIVE["Identity"] -->|"SoulSig / Birth"| SOUL["Soul"]
    SOUL --> SOMA["Body / Runtime"]

    BRAIN["Brain"] -.-> SOMA
    MEM["Memory"] -.-> SOMA
    SKILL["Neural System"] -.-> SOMA
    SEC["Sovereignty"] -.-> SOMA

    SOMA --> AURA["Aura"]
    LIVE -.-> AURA
    SOUL -.-> AURA
    SOMA -.-> AURA

    AURA --> ROOMS["Space / Env"]
    AURA --> LEG["Continuity"]
```

| Readable | ARPA | Role |
| :--- | :--- | :--- |
| **Identity** | Live ID | Who is accountable |
| **Soul** | SoulSig | Birth contract, constitution |
| **Body / Runtime** | Soma | Whatever hosts the run |
| **Brain** | Logical Systems | Reasoning substrate — use, do not own |
| **Memory** | MnemoLink | Personas, experience, retention |
| **Neural System** | Skillware | Capabilities, tool pathways |
| **Sovereignty** | Synapuls | Security across every surface |
| **Aura** | AURA Harness | **Runtime coat — this project** |
| **Space / Env** | Rooms | Collaboration, environments |
| **Continuity** | Legacy | Record beyond the host |

SoulSig persists on identity. Soma is temporal — the host for this chapter. AURA governs the loop and routes results to Rooms and Legacy.

→ Full stack vision: [Manifesto](https://github.com/ARPAHLS/manifesto) · [Stack position](docs/stack-position.md)

---

## How It Works

```
Inputs (any types)  →  Manifest + Spectrum  →  Harness  →  AuraEvent output
```

**Inputs** are registered **types** — not hardcoded vendors. Brain can be Gemini, Claude, Ollama, or custom. Skills can be any framework. Identity can be Live ID or ephemeral session. The harness adapts; the output shape stays the same.

| Mechanism | Role |
|---|---|
| **Type registry** | Extensible input bindings |
| **Spectrum** | AURA Levels, budgets, guardrails, services |
| **Hook pipeline** | Interception on every loop tick |
| **Sequencer** | Ordered pipelines — steps, retries, middleware |
| **Field services** | Monitor, audit, limit, break, recover, … — parallel to the loop |
| **Exporters** | JSON, OTel, CSV, webhook, continuity stream |

---

## AURA Levels

Autonomy is tiered, explicit, enforceable:

| Level | Posture |
|---|---|
| **Low** | Suggest; human approves before action |
| **Mid** | Act in scope; escalate at boundaries |
| **High** | Independent within guardrails |
| **Full** | Self-directed within constitution; accountability via audit |

→ [aura-levels.md](docs/aura-levels.md)

---

## Documentation

| Topic | Links |
| :--- | :--- |
| **Index** | [docs/INDEX.md](docs/INDEX.md) |
| **Narrative** | [docs/narrative.md](docs/narrative.md) |
| **Architecture** | [docs/architecture.md](docs/architecture.md) · [three-rings.md](docs/three-rings.md) |
| **Runtime** | [sequencer.md](docs/sequencer.md) · [field-services.md](docs/field-services.md) · [outputs.md](docs/outputs.md) |
| **Trust & identity** | [trust-paths.md](docs/trust-paths.md) |
| **Specifications** | [spec/](spec/) |

---

## Development

Requires **Python 3.10+**.

```bash
git clone https://github.com/ARPAHLS/aura.git
cd aura
pip install -e ".[dev]"
pytest
aura version
```

---

<div align="center">

<br>
<div align="center">
  <img src="assets/arpalogo26.png" width="50" alt="ARPA Logo">
  <br>
  <sub>Developed and Maintained by <b>ARPA HELLENIC LOGICAL SYSTEMS</b></sub>
  <br>
  <sub>Support: systems@arpacorp.net</sub>
</div>
