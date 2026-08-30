# Using AURA Harness

How to attach AURA to your agent loop — from lightweight audit logging to prescriptive pipelines.

→ New here? [onboarding.md](onboarding.md) walks install through session receipt.

---

## Choose a posture

| Posture | Goal | Typical setup |
|---|---|---|
| **Audit** | Wrap any custom loop and review what happened | `agent().session()`, `emit()`, rules optional |
| **Prescriptive** | Require declared steps, gates, and conformance | Sequencer spec, a tool host, gates, session export in CI |

AURA is the **harness (coat)**, not the runtime. Your **body** owns the loop; AURA wraps it with **membrane** boundaries and an **audit trail**.

---

## Membrane model

```
Ingress → [ Body / host cavity ] → Egress → Audit sink
              ↑
         Observers (parallel subscribers)
```

| Boundary | Role |
|---|---|
| **Ingress** | Normalize agent context at session open (`membrane.ingress` event) |
| **Body** | Your loop — script, Skillware host, LangGraph, device |
| **Egress** | Policy + audit before tools/skills execute (`tool.intent` → `tool.call` → `tool.result`) |
| **Observers** | Parallel handlers on every spine event — monitoring, alerts, custom analytics |
| **Audit sink** | Append-only JSONL + session export on close |

Ingress and egress are **conceptual boundaries** implemented in `aura/membrane/`. Observers never block the host.

## Session close and export

When a session closes with export enabled (the default), AURA writes three files under the configured sessions directory:

| File | Use |
|---|---|
| `{session_id}.jsonl` | Append-only event trail, including the hash chain |
| `{session_id}.summary.json` | Identity, conformance, and the `AuditReport` receipt |
| `{session_id}.otel.jsonl` | Span-shaped export for telemetry tools; written on close by default, refreshed by `aura export-otel` |

The summary's `audit_report` contains the verdict (`pass`, `warn`, or `fail`), a scorecard, findings, recommendations, and `hash_chain_valid`. A passing conformance check can still produce a `warn` verdict when the report finds advisory issues; inspect the findings before treating a run as complete. When a gated call is approved, its `principal` is recorded in the audit trail and appears in the summary and OTel export as `aura.principal`.

```json
{
  "audit_report": {
    "verdict": "pass",
    "scorecard": {"policy": {}, "tools": {}, "sequencer": {}, "events": 12},
    "findings": [],
    "recommendations": [],
    "hash_chain_valid": true
  }
}
```

Use the CLI to review the receipt or feed structured output to CI:

```bash
aura report show aura_sess_xxxxxxxxxxxx
aura report show aura_sess_xxxxxxxxxxxx --json
aura export aura_sess_xxxxxxxxxxxx
aura export-otel aura_sess_xxxxxxxxxxxx
aura verify chain ~/.aura/sessions/aura_sess_xxxxxxxxxxxx.jsonl
```

See [outputs.md](outputs.md) for the complete artifact schema and [comparison.md](comparison.md) for comparing two summary files. If the JSONL hash chain is broken, `aura verify chain` reports the first affected event and exits with status 1.

With `export=False`, no files are written, but `run.summary` and `run.audit_report` are still populated when the context exits — use them for tests and programmatic gates. After close, further `emit` or `approve` calls raise `SessionClosedError`.

---

## Python SDK (primary)

```python
from aura import agent, configure
from aura.hosts import SkillwareHost, MockSkill

configure()

ag = agent(
    "pipeline-bot",
    skills=["research", "gmail"],
    sequencer={"steps": [...]},
    rules=[{"type": "confirm_before", "tools": ["send"]}],
)

with ag.session(mode="task") as run:
    host = SkillwareHost(run._session)
    host.register(MockSkill("research", {"search": lambda a: {"hits": 1}}))
    run.run_sequencer(host=host)
```

| API | Purpose |
|---|---|
| `configure()` | Merge global + project config |
| `agent(name)` | Get/create agent profile |
| `agent.session()` | Open session, auto-export on close |
| `run.summary` / `run.audit_report` | In-memory receipt (always built; disk write optional via `export=`) |
| `session(identity_adapter=...)` / `operator=` | Optional verified operator trailer ([#55](https://github.com/ARPAHLS/aura/issues/55)) |
| `run.emit(kind, payload)` | Append audited event |
| `run.approve(request_id, principal="operator@corp")` | Satisfy confirm/gate and record the approver |
| `run.run_sequencer(host=...)` | Run declared step pipeline |
| `current_session()` | Active handle inside context |

Submodules: `aura.sequencer`, `aura.hosts`, `aura.observers`, `aura.membrane`.

---

## Sequencer vs emergent tool loop

| | **Sequencer** | **Emergent agent loop** |
|---|---|---|
| Control | You declare step order upfront | Model chooses tools step-by-step |
| Conformance | Declared steps vs spine on close | Rule checks per event only |
| Use case | Compliance pipelines, SOPs | Open-ended research, chat |

Both can coexist: run a sequencer inside a session, or emit events manually in a free-form loop.

Step types: `skill`, `op`, `prompt`, `gate`, `subflow`. Gates: `human_confirm`, `constitution`, `budget`.

→ [sequencer.md](sequencer.md) · [skillware-integration.md](skillware-integration.md)

---

## Observers

Register global or per-session subscribers:

```python
from aura.observers import CallableObserver, get_registry

get_registry().register(CallableObserver("metrics", lambda e: print(e["kind"])))
```

Profile observers (by id) attach at session open. Handlers must be non-blocking.

Packaged presets: `preset: monitor` (analytics notes) and `preset: break` (repeated-intent alerts) — see [examples/07-observer-presets](../examples/07-observer-presets/) and [reference-tool-host-capstone.md](guides/reference-tool-host-capstone.md).

---

## CLI

Mirrors the SDK for agent management and script runs:

```bash
aura                    # interactive splash + menu (after pip install)
aura --help             # grouped command reference
aura config show        # merged config + resolved paths
aura paths              # view paths; set-project / set-storage persist YAML
aura agent create my-bot --purpose "compliance"
aura agent set my-bot --ref acme/my-bot --skill research --variable model=llama3.2
aura run my-bot examples/sequencer_pipeline.py
aura logs aura_sess_xxxxxxxxxxxx
aura export aura_sess_xxxxxxxxxxxx
aura report show aura_sess_xxxxxxxxxxxx
aura report show aura_sess_xxxxxxxxxxxx --json
aura verify chain ~/.aura/sessions/aura_sess_xxxxxxxxxxxx.jsonl
```

Profiles live as JSON under `{AURA_HOME}/agents/`. Global defaults: `~/.aura/config.yaml`. Project overrides: `{project}/aura.project.yaml`. Use env vars for API keys; store non-secret refs in profile `variables`.

Interactive menu: **agents** (list/show/create/edit), **sessions**, **run**, **paths**, help, version.

---

## YAML agent profiles

Agent fields (JSON on disk under `~/.aura/agents/`):

```yaml
name: compliance-bot
purpose: Research → draft → approve → notify
skills: [research, gmail]
sequencer:
  steps:
    - id: research
      type: skill
      ref: research
      config: { tool: search, args: { query: "..." } }
    - id: notify
      type: skill
      ref: gmail
      gates: [human_confirm]
      config: { tool: send, args: { to: "team@example.com" } }
rules:
  - type: confirm_before
    tools: [send]
observers:
  - id: slack-alerts
```

Schema: [sequencer.schema.json](../spec/sequencer.schema.json)

---

## Optional Skillware

```bash
pip install "aura-harness[skillware]"
```

Skillware ≥ 0.5.1 runs inside the body; AURA wraps `execute()` at egress. See [skillware-integration.md](skillware-integration.md).

---

## What AURA does not own

- Model inference or tool implementation (body / Skillware)
- Full batch eval (RAGAS) — export feeds eval pipelines later
- HTTP fleet API — deferred

→ [comparison.md](comparison.md) · [ROADMAP.md](ROADMAP.md)
