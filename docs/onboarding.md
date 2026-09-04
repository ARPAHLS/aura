# Onboarding — use AURA correctly

Step-by-step path from install to a reviewable session receipt. Full doc map: [INDEX.md](INDEX.md). For membrane detail see [using-aura.md](using-aura.md); for terms see [concepts.md](concepts.md).

---

## 1. Install and storage

```bash
git clone https://github.com/ARPAHLS/aura.git
cd aura
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Confirm the CLI and resolved paths:

```bash
aura version
aura config show
aura paths
```

| Path | Default | Override |
|---|---|---|
| Agent profiles | `{AURA_HOME}/agents/` | `AURA_HOME` env or `aura --home` |
| Session exports | `{AURA_HOME}/sessions/` | same |
| Project storage | global `~/.aura/` | `aura paths set-storage project` + `aura.project.yaml` |

Use a dedicated home for experiments: `AURA_HOME=/tmp/aura-demo aura paths`.

---

## 2. Choose a posture

AURA is the **coat** around your loop — not the loop itself.

| Posture | You want | Typical wiring |
|---|---|---|
| **Audit** | Record what happened; rules optional | `agent().session()`, `emit()`, export on close |
| **Prescriptive** | Declared steps, gates, conformance on close | Sequencer spec + tool host + rules + CI receipt check |

→ [using-aura.md — Choose a posture](using-aura.md#choose-a-posture)

Stack-specific bodies (Ollama, OpenAI, Skillware registry) live under [integrations/](integrations/README.md). Core patterns live under [examples/](../examples/README.md).

---

## 3. Identity and constitution

Create an agent with stable audit anchors:

```bash
aura agent create research-bot \
  --ref acme/research-bot \
  --purpose "Research and draft outreach"
```

| Field | Role |
|---|---|
| **`agent_ref`** | Human/CI anchor (`tenant/slug`) |
| **`aura_id`** | Internal ULID (auto unless you set `--aura-id`) |
| **`policy_version`** | Tie runs to a policy snapshot (profile or per-session) |
| **`purpose`** | Declared intent — appears in profile and spine |
| **`rules`** | Constitution — `confirm_before`, `allow_tools`, `deny_tools`, token limits |
| **`ids`** | Your external IDs (company, vendor assistant id) — AURA does not replace them |
| **`ids.operator`** (optional) | Human/service principal when using an identity adapter — see [integrations/identity](../integrations/identity/README.md) |

Update later: `aura agent set research-bot --ref acme/research-bot --variable model=gpt-4o-mini`.

→ [trust-paths.md](trust-paths.md) · [concepts.md — Agent](concepts.md#agent)

---

## 4. Wire the body

Pick how your loop executes inside the session:

| Body style | When | Entry |
|---|---|---|
| **Emit-only** | Custom script; you emit spine events yourself | [examples/08-emit-only-loop](../examples/08-emit-only-loop/) |
| **Tool host** | Skills/tools at egress; membrane enforces rules | `SkillwareHost` or any `ToolHost` — [reference-tool-host-capstone.md](guides/reference-tool-host-capstone.md) |
| **Sequencer** | Declared step order + gates | [sequencer_pipeline.py](../examples/sequencer_pipeline.py) |
| **Stack integration** | Ollama / cloud API as body | [integrations/README.md](integrations/README.md) |

Minimal SDK pattern (audit posture):

```python
from aura import agent, configure

configure()
ag = agent("research-bot")

with ag.session(mode="script") as run:
    run.emit("turn.start", {"input": "hello"})
    run.emit("turn.end", {"output": "done", "tokens": 42})

print(run.session_id, run.exports)
```

---

## 5. Run, approve gates, record principal

Run a script under an agent profile:

```bash
aura run research-bot path/to/script.py
```

When a rule requires confirmation, satisfy it in code and **record the approver**:

```python
run.approve(request_id, principal="operator@corp")
```

The principal appears in the audit trail, summary, and OTel export as `aura.principal`.

CLI after close:

```bash
aura logs aura_sess_xxxxxxxxxxxx
aura report show aura_sess_xxxxxxxxxxxx
aura report show aura_sess_xxxxxxxxxxxx --json
```

→ [using-aura.md — Session close and export](using-aura.md#session-close-and-export)

---

## 6. Review the receipt

On session close (default), AURA writes:

| Artifact | Use |
|---|---|
| `{session_id}.jsonl` | Hash-chained event trail |
| `{session_id}.summary.json` | Conformance + `AuditReport` |
| `{session_id}.otel.jsonl` | Span-style export (on close; refresh with `export-otel`) |

```bash
aura export aura_sess_xxxxxxxxxxxx
aura export-otel aura_sess_xxxxxxxxxxxx
aura verify chain ~/.aura/sessions/aura_sess_xxxxxxxxxxxx.jsonl
aura compare sess_a sess_b
```

Inspect verdict (`pass` / `warn` / `fail`), findings, and `hash_chain_valid` before treating a run as complete. A conformance pass can still `warn` when the report finds advisory issues.

→ [outputs.md](outputs.md)

---

## 7. CI hook (sketch)

Fail the job when the hash chain or report verdict is unacceptable:

```bash
pytest --ignore=tests/integration
aura verify chain "$SESSION_JSONL" || exit 1
aura report show "$SESSION_ID" --json | jq -e '.audit_report.verdict != "fail"'
```

Use project-scoped storage in CI: `AURA_HOME=$RUNNER_TEMP/aura`.

→ [TESTING.md](TESTING.md)

---

## Examples learning path

Run in order from repo root after `pip install -e .`:

| Step | Example | Teaches |
|---|---|---|
| 1 | [minimal_loop.py](../examples/minimal_loop.py) | Audit posture — emit + export |
| 2 | [guarded_tools.py](../examples/guarded_tools.py) | Rules, approval gates, allow/deny |
| 3 | [task_mode.py](../examples/task_mode.py) | Task mode + `complete_goal()` |
| 4 | [sequencer_pipeline.py](../examples/sequencer_pipeline.py) | Prescriptive pipeline + mock host |
| 5 | [05-skillware-skill-types](../examples/05-skillware-skill-types/) | ToolHost + three skill categories |
| 6 | [06-skillware-sequencer-chain](../examples/06-skillware-sequencer-chain/) | Declarative chain + conditional `when` |
| 7 | [07-observer-presets](../examples/07-observer-presets/) | Monitor + Break observer presets |
| 8 | [08-emit-only-loop](../examples/08-emit-only-loop/) | Loose coat — no tool host |
| 9 | [audit_pipeline.py](../examples/audit_pipeline.py) | Export slice — report, compare, verify |
| 10 | [10-observer-metrics-snapshot](../examples/10-observer-metrics-snapshot/) | Tailored coat — observer metrics snapshot |

Capstone checklist: [reference-tool-host-capstone.md](guides/reference-tool-host-capstone.md).

---

## Deferred (roadmap)

Not required for first successful run:

- **Goals and schedules** — tracked in [GH #46](https://github.com/ARPAHLS/aura/issues/46)
- **Run auth / gatekeeper coat** — [GH #56](https://github.com/ARPAHLS/aura/issues/56)

---

## Next

- [getting-started.md](getting-started.md) — install snippets
- [using-aura.md](using-aura.md) — SDK, CLI, membrane
- [integrations/README.md](integrations/README.md) — pick your stack
- [INDEX.md](INDEX.md) — full doc map
