<div align="center">

<img src="docs/assets/aura_splash.png" alt="αύρα — AURA Harness" width="550" />

<br>

**AURA Harness - The runtime coat around agent loops.**

<br>

[![ARPA Hellenic Logical Systems](https://img.shields.io/badge/ARPA-Hellenic%20Logical%20Systems-A793AC?labelColor=e8e0e4&style=flat-square)](https://github.com/arpahls)
[![Manifesto](https://img.shields.io/badge/docs-manifesto-f5e6d3?labelColor=e8e0e4&style=flat-square)](https://github.com/ARPAHLS/manifesto)
[![Getting started](https://img.shields.io/badge/docs-getting%20started-d4e4f7?labelColor=e8e0e4&style=flat-square)](docs/getting-started.md)
[![Architecture](https://img.shields.io/badge/docs-architecture-c8dde8?labelColor=e8e0e4&style=flat-square)](docs/architecture.md)
[![Examples](https://img.shields.io/badge/examples-runnable-b8d4e8?labelColor=e8e0e4&style=flat-square)](examples/)
[![Comparison](https://img.shields.io/badge/docs-comparison-c8dde8?labelColor=e8e0e4&style=flat-square)](docs/comparison.md)
[![Spec](https://img.shields.io/badge/spec-schemas-e8f0f8?labelColor=e8e0e4&style=flat-square)](spec/)

<br>

[Overview](#overview) ·
[Architecture](#aura-architecture) ·
[How It Works](#how-it-works) ·
[Documentation](#documentation) ·
[Development](#development)

</div>

---

## Overview

**αύρα** *(aura)* — in Greek, a surrounding presence: the field that wraps what is inside it. In ARPA Logical Systems, if an agent loop is an active **body**, aura is not the loop/runtime/body itself, but the conditions that make the loop viable — what we call a **harness**.

**AURA Harness** wraps whatever hosts your loop — a script, a framework, a device — and works **alongside** it, not instead of it. It records a causal audit log, enforces your rules, and exports session summaries you can ship to logs or observability tools.

What you plug in is open-ended: models, tools, memory, identity, policy, and more — via adapters over time, not hardcoded vendors. **v0.2** adds the **membrane** (ingress/egress), **sequencer**, **observers**, and a **Skillware host** (optional extra). The v0.1 kernel remains: agent registry, sessions, constraints, JSONL export, Python SDK.

| | |
|---|---|
| **Conformance** | Did the run stay within declared rules? |
| **Auditability** | Every meaningful event logged in order, with causal IDs |

---

## AURA Architecture

This is the **AURA Harness** view — not the full [ARPA manifesto stack](https://github.com/ARPAHLS/manifesto). Soul, Rooms, Legacy, and the birth chain live there. Here, parallel **inputs** feed the **body**; **Aura** wraps it; an **audit trail** records everything; **session export** delivers the log on close.

```mermaid
flowchart LR
    IN["Ingress"] --> BODY["Body / Runtime"]
    ID["Identity"] -.-> BODY
    BRAIN["Brain"] -.-> BODY
    MEM["Memory"] -.-> BODY
    TOOLS["Tools"] -.-> BODY
    CONST["Constitution"] -.-> BODY

    BODY --> EG["Egress / Aura"]
    EG --> TRAIL["Audit Trail"]
    TRAIL --> EXPORT["Session Export"]
    TRAIL -.-> OBS["Observers"]
```

| Layer | Role in AURA |
| :--- | :--- |
| **Identity** | Agent ID trailer — `AURA-000n`, optional name, your external IDs |
| **Brain** | Model / reasoning (adapter — any provider) |
| **Memory** | Retention, persona (adapter — optional) |
| **Tools** | Skills, MCP, APIs, [Skillware](https://github.com/arpahls/skillware) bundles (adapter) |
| **Constitution** | Rules, guardrails, constraints — what the run must obey |
| **Body / Runtime** | Whatever hosts the loop — script, framework, device |
| **Aura / Membrane** | **This project** — ingress, egress, attach, enforce, record |
| **Observers** | Parallel subscribers to the audit trail (v0.2) |
| **Sequencer** | Declarative step pipelines inside a session (v0.2) |
| **Audit Trail** | Append-only causal event log during the run |
| **Session Export** | JSONL log + conformance summary when the session closes |

All inputs are optional except a body to wrap. Use any subset; AURA adapts.

→ Deeper detail: [stack-position.md](docs/stack-position.md) · Full ARPA vision: [Manifesto](https://github.com/ARPAHLS/manifesto)

---

## How It Works

**v0.2 flow:**

```
Agent (AURA-000n)  →  Session open (ingress)  →  body / sequencer  →  egress + emit  →  close  →  JSONL + summary
```

| Component | Status | Role |
| :--- | :--- | :--- |
| **Agent registry** | Shipped | Permanent `AURA-000n` IDs, optional name, user ID trailer |
| **Session** | Shipped | Modes: `script`, `task`, `continuous` |
| **Membrane** | Shipped | Ingress context + egress guarded tool calls |
| **Audit spine** | Shipped | Append-only JSONL with causal event IDs |
| **Constraint engine** | Shipped | Token limits, confirm-before-action, allow/deny tools |
| **Conformance summary** | Shipped | Rules + sequencer order vs observed events |
| **Sequencer** | Shipped | Linear steps: skill, op, gate, prompt; retries, human_confirm |
| **Skillware host** | Shipped | Optional `[skillware]` extra; mock skills for tests |
| **Observers** | Shipped | Parallel spine subscribers |
| **Python SDK + CLI** | Shipped | `agent()`, `session()`, `run_sequencer()`, export |
| **Type adapters** | Roadmap | Brain, memory plugins — see [ROADMAP](docs/ROADMAP.md) |
| **HTTP fleet API** | Roadmap | Remote session management — deferred |

Lite identity: AURA assigns `AURA-0001`, `AURA-0002`, … if you provide no name. Your own IDs nest under `ids` — no identity service required.

→ [using-aura.md](docs/using-aura.md) · [concepts.md](docs/concepts.md) · [getting-started.md](docs/getting-started.md) · [examples/](examples/)

---

## Documentation

| Topic | Links |
| :--- | :--- |
| **Start here** | [getting-started.md](docs/getting-started.md) · [using-aura.md](docs/using-aura.md) · [concepts.md](docs/concepts.md) · [examples/](examples/) |
| **Integration** | [skillware-integration.md](docs/skillware-integration.md) · [sequencer.md](docs/sequencer.md) |
| **Comparison** | [comparison.md](docs/comparison.md) — vs DSH, LangGraph, eval harnesses, tracing |
| **Index** | [docs/INDEX.md](docs/INDEX.md) |
| **Architecture** | [architecture.md](docs/architecture.md) · [stack-position.md](docs/stack-position.md) |
| **Identity** | [trust-paths.md](docs/trust-paths.md) — lite ID trailer, no Live ID required |
| **Roadmap** | [ROADMAP.md](docs/ROADMAP.md) |
| **Specifications** | [spec/](spec/) — schemas for adapters and events |
| **Vision (long-form)** | [narrative.md](docs/narrative.md) |

---

## Development

Requires **Python 3.10+**.

Requires **Python 3.10+**. Use a local venv (`.venv/` is gitignored):

```bash
git clone https://github.com/ARPAHLS/aura.git
cd aura
py -3.13 -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"
# optional Skillware:
pip install -e ".[dev,skillware]"
pytest
aura version
```

Quick start:

```python
from aura import agent, configure
from aura.hosts import MockSkill, SkillwareHost

configure()
ag = agent("my-bot", sequencer={"steps": [{"id": "ping", "type": "op", "ref": "health"}]})
with ag.session() as run:
    run.run_sequencer()
print(run.exports)
```

→ [getting-started.md](docs/getting-started.md) · [examples/](examples/) · [CHANGELOG.md](CHANGELOG.md) · [CONTRIBUTING.md](CONTRIBUTING.md)

---

<div align="center">

<br>
<div align="center">
  <img src="https://raw.githubusercontent.com/ARPAHLS/.github/main/Group%202062.png" width="50" alt="ARPA Logo">
  <br>
  <sub>Developed and Maintained by <b>ARPA HELLENIC LOGICAL SYSTEMS</b></sub>
  <br>
  <sub>Support: systems@arpacorp.net</sub>
</div>
