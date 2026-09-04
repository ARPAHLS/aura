# Skillware integration

AURA Harness wraps Skillware skills at **egress** — policy, approval, and audit — without owning Skillware's runtime.

**Full guide (recommended):** [guides/aura-on-skillware.md](guides/aura-on-skillware.md) — stack position, skill types, provider loops, sequencer chains, best practices.

---

## Position in the stack

| Layer | Owner |
|---|---|
| **Skillware** | Skill bundles, `execute()`, tool implementations |
| **Body / host** | Loads skills, runs the loop |
| **AURA membrane** | Ingress context, egress guard on every tool call |
| **Audit trail** | JSONL spine + session export |

Skillware is **optional**: `pip install "aura-harness[skillware]"` (see [Version compatibility](#version-compatibility) below). Tests and examples use `MockSkill` when Skillware is not installed.

---

## Version compatibility

AURA pins a **semver range**, not an exact patch — so `pip install -U` picks up Skillware **0.5.x** fixes without editing AURA on every patch release:

```text
skillware>=0.5.4,<0.6
```

| Policy | Meaning |
|---|---|
| **Floor (`>=0.5.4`)** | Minimum tested API — `SkillContext`, named `chains:`, security support window ([Skillware SECURITY.md](https://github.com/arpahls/skillware/blob/main/SECURITY.md)) |
| **Ceiling (`<0.6`)** | Conscious bump when Skillware ships breaking 0.6 API — update floor + docs in one PR |
| **What's new** | Read [Skillware CHANGELOG](https://github.com/arpahls/skillware/blob/main/CHANGELOG.md) — we do not duplicate every skill release in AURA |

CI **`skillware-live`** installs the latest compatible release from PyPI on each run. Local dev checkout: `pip install -e ../skillware` alongside AURA.

---

## Skillware chains vs AURA sequencer

Skillware **0.5.4+** adds host-level orchestration that complements (does not replace) AURA's audited sequencer:

| | **Skillware `run_chain()` / `SkillContext`** | **AURA sequencer** |
|---|---|---|
| **Owner** | Skillware host / body script | Agent profile or session spec |
| **Audit** | None by default | Full spine: `sequencer.step.*`, `tool.*`, export receipt |
| **Policy** | Host code | Egress gates, constitution, conformance on close |
| **Conditional skip** | Step `when:` in `chains:` YAML | Step `when:` on prior step result |
| **Best for** | Scripts, CI, model tool routing | Compliance SOPs, regulated pipelines |

**Rule:** Route every skill `execute()` through **`SkillwareHost`** so AURA records egress regardless of whether ordering comes from Skillware chains or AURA sequencer.

Reference parity: Skillware's `sanitize_input` chain (firewall → rewriter when `is_safe`) matches [example 06](../../examples/06-skillware-sequencer-chain/) — AURA adds the session receipt.

→ Skillware docs: [skill_chaining.md](https://github.com/arpahls/skillware/blob/main/docs/usage/skill_chaining.md) (`SkillContext`, `run_chain`, `chains:` in `.skillware.yaml`)

---

## Quick start (mock skills)

Same host API as real Skillware — swap mocks for live skills later.

```python
from aura import agent, configure, ApprovalRequired
from aura.hosts import SkillwareHost, MockSkill

configure()

ag = agent("demo", skills=["research"])

with ag.session() as run:
    host = SkillwareHost(run._session)
    host.register(
        MockSkill("research", {"search": lambda args: {"results": []}})
    )
    host.execute("research", "search", {"query": "AURA harness"})
```

Every execution emits:

1. `skill.registered` — when the skill carries a manifest (merged into session rules)
2. `tool.intent` — egress intent
3. `tool.call` — constraint checks (allow/deny, confirm_before, …)
4. `tool.result` or `tool.error`

### Manifest guardrails at bind

Pass optional `manifest` on `MockSkill` (or on live skills) to merge allow/deny/confirm rules into the session constitution at register time:

```python
MockSkill(
    "gmail",
    {"send": lambda args: {"sent": True}},
    manifest={"deny_tools": ["send.bulk"]},
)
```

Emits `skill.registered` on the spine with `manifest_snapshot_hash`, `agent_ref`, `policy_version`, plus bind context: `host.bind`, `bound_skill_ids`, `session_snapshot_hash` (see [reference-tool-host-capstone.md](guides/reference-tool-host-capstone.md)).

### Monitor observer preset

Add to agent profile `observers`:

```yaml
observers:
  - preset: monitor
    id: loop-monitor
    config:
      max_identical_intents: 5
      log_path: .aura/monitor.log
```

Tracks tool calls and emits `observer.note` events (analytics only — does not block egress).

### Break observer preset

Circuit-breaker **alerts** on repeated identical tool intents — emits `observer.alert` (analytics only; does not block egress):

```yaml
observers:
  - preset: break
    id: loop-break
    config:
      max_identical_intents: 3
      window_seconds: 60
```

Runnable tour: [examples/07-observer-presets](../../examples/07-observer-presets/).

---

## ToolHost protocol

Any runtime can implement `ToolHost` (`register`, `execute` through egress). `SkillwareHost` is the reference adapter — see `aura.hosts.ToolHost` and [reference-tool-host-capstone.md](guides/reference-tool-host-capstone.md).

---

## Real Skillware registry skills

Install Skillware (bundled skills ship with the package):

```bash
pip install -e ".[dev,skillware]"
skillware list
skillware doctor optimization/prompt_rewriter
```

Load a registry skill and run through AURA egress:

```python
from aura import agent, configure
from aura.hosts import SkillwareHost, load_registry_skill

configure()

with agent("demo", skills=["optimization/prompt_rewriter"]).session() as run:
    host = SkillwareHost(run._session)
    skill = host.register_registry_skill("optimization/prompt_rewriter")
    result = host.execute(
        skill.skill_id,
        skill.skill_id,
        {"raw_text": "Please kindly read everything.", "compression_aggression": "high"},
    )
```

Or use the loader directly:

```python
from aura.hosts import load_registry_skill

skill = load_registry_skill("security/prompt_injection_firewall")
host.register(skill)
host.execute(skill.skill_id, skill.skill_id, {"source_text": untrusted, "sensitivity": "balanced"})
```

**Execute contract:** Skillware `BaseSkill.execute(params: dict)` — AURA passes manifest parameters as `args`; the `tool` label is for audit (`tool.intent` / `tool.call`).

**Offline starter skills** (no API keys): `optimization/prompt_rewriter`, `security/prompt_injection_firewall`, `monitoring/token_limiter`.

Integration scripts: [`integrations/skillware/`](../integrations/skillware/) — `mock_tools.py`, `live_tools.py`, and `reference_tool_host.py`; Ollama lives under [`integrations/ollama/`](../integrations/ollama/).

---

## Ollama + Skillware (local dev)

Use [`.env.example`](../.env.example) — default `OLLAMA_MODEL=llama3.2:1b`:

```bash
pip install -e ".[integrations]"   # skillware + ollama client
ollama pull llama3.2:1b
python integrations/skillware/ollama_skill_loop.py
```

Ollama provides the **body** LLM turn; Skillware skills run through `SkillwareHost` at egress. Use explicit `OLLAMA_BASE_URL=http://127.0.0.1:11434` on Windows ( bare `ollama.Client()` may not connect).

Real stack tests: `pytest tests/integration/ -v` (excluded from default CI).

---

## Constitution merge

Rules come from:

1. Agent profile `rules` (AURA constitution)
2. Session overrides passed to `agent.session(rules=[...])`
3. Optional `guardrails` block on skill manifest at bind (merged into session rules)

Skillware `constitution` text is recorded in the manifest snapshot on `skill.registered` but is **not** auto-converted to machine rules — add an explicit `guardrails` overlay when needed:

```yaml
guardrails:
  deny_tools: ["send.bulk"]
```

Constraints apply at **egress** on `tool.call`.

---

## Sequencer + Skillware pipeline

Declare skills in sequencer steps; host routes `type: skill` steps through egress:

```yaml
sequencer:
  steps:
    - id: research
      type: skill
      ref: research
      config:
        tool: search
        args: { query: "compliance brief" }
    - id: send
      type: skill
      ref: gmail
      gates: [human_confirm]
      config:
        tool: send
        args: { to: "team@example.com", subject: "Brief" }
```

Runnable example: [examples/sequencer_pipeline.py](../examples/sequencer_pipeline.py). Conditional steps via `when` (prior step result): [examples/06-skillware-sequencer-chain](../examples/06-skillware-sequencer-chain/) · [sequencer.md](sequencer.md).

---

## OTel export

`aura export-otel` maps spine events to span-style JSONL. Promoted resource attributes on spans:

| Attribute | Source |
|---|---|
| `aura.agent_ref` | Session agent reference |
| `aura.policy_version` | Policy version at session open |
| `aura.principal` | Approver on gated tool calls |
| `aura.skill_id` | Skill id on tool / registration events |

See [outputs.md](outputs.md) and [reference-tool-host-capstone.md](guides/reference-tool-host-capstone.md).

---

## CLI and CI

```bash
pip install -e ".[dev]"
python examples/sequencer_pipeline.py                  # MockSkill
pip install -e ".[skillware]"
pytest -m skillware tests/test_skillware_integration.py   # real registry skills
pytest -m "not ollama"                                    # default CI (no Ollama daemon)
SKILLWARE_LIVE=1 python integrations/skillware/reference_tool_host.py
```

Use session export `.summary.json` `conformance.passed` in CI to fail builds when rules or sequencer order diverge.

---

## Related

- [using-aura.md](using-aura.md) — membrane and postures
- [sequencer.md](sequencer.md) — step model and gates
- [integrations/skillware/](../integrations/skillware/) — reference scripts and README
- [Skillware repo](https://github.com/arpahls/skillware) — skill registry, manifests, CLI
