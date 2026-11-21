# Skillware integration

AURA wraps Skillware skills at **egress** — policy, approval, and audit — without owning Skillware's runtime.

**Full guide (recommended):** [guides/aura-on-skillware.md](guides/aura-on-skillware.md) — stack position, skill types, provider loops, sequencer chains, best practices.

---

## Position in the stack

| Layer | Owner |
|---|---|
| **Skillware** | Skill bundles, `execute()`, tool implementations |
| **Body / host** | Loads skills, runs the loop |
| **AURA membrane** | Ingress context, egress guard on every tool call |
| **Audit trail** | JSONL spine + session export |

Skillware is **optional**: `pip install "machine-aura[skillware]"` (see [Version compatibility](#version-compatibility) below). Tests and examples use `MockSkill` when Skillware is not installed.

---

## Version compatibility

AURA pins a **semver range**, not an exact patch — so `pip install -U` picks up Skillware **0.6.x** fixes without editing AURA on every patch release:

```text
skillware>=0.6.2,<0.7
```

| Policy | Meaning |
|---|---|
| **Floor (`>=0.6.2`)** | Minimum tested API — Manifest v2 taxonomy (`manifest_schema`), async `aexecute`, `SkillContext`, `secret_provider`, provenance `report_hash`, deprecation lifecycle, and `audit.py` dispatch hooks (`0.6.2+` / `0.6.3`) |
| **Ceiling (`<0.7`)** | Conscious bump when Skillware ships breaking 0.7 API — update floor + docs in one PR |
| **Graceful probing** | `skillware_version()` and `skillware_capabilities()` detect installed features at runtime so AURA degrades cleanly without `[skillware]` or before `audit.py` lands on PyPI |
| **What's new** | Read [Skillware CHANGELOG](https://github.com/arpahls/skillware/blob/main/CHANGELOG.md) — we do not duplicate every skill release in AURA |

CI **`skillware-live`** installs the latest compatible release from PyPI on each run. Local dev checkout: `pip install -e ../skillware` alongside AURA.

---

## Skillware `SkillContext`, dispatch audit bridge, and dual-ledger verification

Skillware **0.6.2+** adds host-level orchestration (`run_chain()`, `SkillContext`, `aexecute()`, and optional dispatch audit hooks via `on_dispatch` / `audit_log_path`) that complements AURA's audited membrane:

| | **Skillware `run_chain()` / `SkillContext`** | **AURA membrane & sequencer** |
|---|---|---|
| **Owner** | Skillware host / body script | Agent profile or session spec |
| **Audit** | Optional `AuditDispatcher` (`on_dispatch` / hash-chained JSONL) | Full spine: `skill.registered`, `skill.dispatch`, `tool.*`, FinOps telemetry, export receipt |
| **Policy** | Host code + param validation + hardware warning | Egress gates (`allow`/`deny`/`confirm_before`, physical-target gate, `capability_scope`, `schema_check`), conformance on close |
| **Conditional skip** | Step `when:` in `chains:` YAML | Step `when:` on prior step result |
| **Best for** | Scripts, CI, model tool routing | Compliance SOPs, regulated pipelines, FinOps governance |

**Rule:** Route every skill `execute()` / `aexecute()` through **`SkillwareHost`** so AURA enforces egress policy and records every call regardless of whether ordering comes from Skillware or AURA sequencer.

### Wrapping `SkillContext` with dispatch audit bridging

Use `SkillwareHost.create_context()` or `SkillwareHost.from_skill_context()` to bind a Skillware `SkillContext` directly into AURA's audit spine.

- **Single-ledger mode (default, recommended):** Omit `audit_log_path`. AURA bridges `on_dispatch` events into AURA's single immutable SHA-256 `AuditSpine` JSONL with zero duplicate disk I/O.
- **Dual-ledger mode (optional split-custody):** Pass `audit_log_path=...` when compliance requires Skillware to write a separate hash-chained JSONL log alongside AURA's spine, and verify both logs together with `verify_dual_audit_chain()` or `aura verify chain <aura.jsonl> --skillware-log <skillware.jsonl>`.

```python
from aura import agent, configure
from aura.hosts import SkillwareHost

configure()

with agent("auditable-bot", skills=["optimization/prompt_rewriter"]).session(export=True) as run:
    # Single-ledger default: bridges Skillware on_dispatch into AURA's AuditSpine JSONL
    host = SkillwareHost.create_context(
        run._session,
        skills=["optimization/prompt_rewriter"],
        max_concurrency=4,
    )
    result = host.execute(
        "optimization/prompt_rewriter",
        "optimization/prompt_rewriter",
        {"raw_text": "Please kindly summarize this brief.", "compression_aggression": "low"},
        audit_meta={"model": "gpt-4o", "prompt_tokens": 1200, "completion_tokens": 300},
    )
```

If using optional dual-ledger mode (`audit_log_path=Path("skillware_audit.jsonl")`), cross-verify both SHA-256 chains via Python (`verify_dual_audit_chain(run.exports["jsonl"], "skillware_audit.jsonl")`) or CLI (`aura verify chain <aura.jsonl> --skillware-log skillware_audit.jsonl`).

What AURA adds on top of Skillware's `AuditDispatcher`:

- **No double counting**: Bridged `skill.dispatch` and outer `tool.result`/`tool.error` share `span_id` and `trace_id`; FinOps cost/token aggregation deduplicates by `span_id`.
- **Unguarded bypass detection**: If host code invokes `ctx.execute()` directly while AURA's `on_dispatch` hook is attached, AURA still captures the dispatch, emits `skill.egress_bypass`, and raises `UNGUARDED_SKILL_DISPATCH` (`severity: high`) in the audit report.
- **Dual-ledger cross-anchoring**: When `audit_log_path` is enabled on Skillware, AURA anchors `skillware_event_hash` and `skillware_prev_hash` on the spine. `verify_dual_audit_chain()` validates both SHA-256 chains and flags tampering, truncation, or unanchored shadow executions.
- **Provenance hash promotion**: Outputs carrying `provenance.report_hash` (e.g. `finance/wallet_screening` v2.1.0) are promoted to `tool.result` telemetry and OTel attribute `aura.provenance_hash`.
- **Unified secret redaction & FinOps**: AURA scrubs raw credential patterns (`sk-...`, `ghp_...`, `AIza...`, `AKIA...`, `Bearer ...`, PEM keys) in args, results, and error messages, tracks per-model/per-skill USD spend in `scorecard.finops`, and supports `max_cost_usd` alerts in `LimitObserver`.

### Async execution (`aexecute`)

`SkillwareHost.aexecute()` routes async calls through `guarded_tool_call_async`, honoring `max_concurrency` (`asyncio.Semaphore`), per-call `timeout` (emitting `tool.error` with `error_type: "TimeoutError"`), and thread-safe hash-chain locking on `AuditSpine`:

```python
result = await host.aexecute(
    "optimization/prompt_rewriter",
    "optimization/prompt_rewriter",
    {"raw_text": "Summarize quarterly results.", "compression_aggression": "low"},
    timeout=10.0,
    audit_meta={"model": "gemini-2.5-flash", "prompt_tokens": 500, "completion_tokens": 120},
)
```

### Manifest v2 validation, physical safety gate, and credential isolation

At skill registration (`skill.registered`), `SkillwareHost` inspects Skillware Manifest v2 metadata:

- **Validation (`manifest_validation="warn" | "strict" | "off"`)**: Validates `shape`, `tier`, `target`, `tags`, and required fields (`name`, `version`, `description`) via `skillware.core.manifest_schema` (with built-in fallback). Minimal guardrail-only `MockSkill` manifests remain valid. `"strict"` emits `skill.manifest_invalid` and raises `ManifestValidationError`.
- **Physical substrate safety gate (`hardware_gate="auto" | "confirm" | "off"`):** In `"auto"` mode (default), exclusively physical skills (`hardware`/`bioware` without `software`), or any physical skill at `high`/`full` spectrum, automatically receive a `confirm_before` constraint rule requiring explicit `run.approve(request_id, principal=...)` unless `SkillwareHost(..., allow_hardware_execution=True)` is set. Dual-domain `[software, hardware]` engineering utilities (like `unit_normalizer`) run normally at default/low/mid spectrum while still logging `physical_target: true` on `skill.registered`. Use `hardware_gate="confirm"` to require approval on all physical targets.
- **High-spectrum schema auto-wiring**: Under `spectrum.level` `high` or `full` (when `schema_enforcement` is not `false`), manifest `parameters` JSON Schemas auto-wire into egress `schema_check` rules.
- **Deprecation tracking**: Skills marked `deprecated: true` record `deprecated` / `deprecation_notice` on `skill.registered` and emit `SKILL_DEPRECATED` (`severity: info`).
- **Secret isolation**: When a session uses `secret_broker`, `SkillwareHost` passes a `credential_fn` / `secret_provider` bridge to Skillware 0.6+ skills without mutating `os.environ`, and automatically registers resolved credentials for spine leak scrubbing.

Reference parity: Skillware's `sanitize_input` chain (firewall -> rewriter when `is_safe`) matches [example 06](../../examples/06-skillware-sequencer-chain/) — AURA adds the session receipt. Audit bridge, FinOps, physical gate, and async demo: [example 16](../../examples/16-skillware-audit-bridge/).

-> Skillware docs: [skill_chaining.md](https://github.com/arpahls/skillware/blob/main/docs/usage/skill_chaining.md) · [audit_trail.md](https://github.com/arpahls/skillware/blob/main/docs/usage/audit_trail.md)

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
    host.execute("research", "search", {"query": "AURA"})
```

Every execution emits:

1. `skill.registered` — when the skill carries a manifest (merged into session rules)
2. `tool.intent` — egress intent
3. `tool.call` — constraint checks (allow/deny, confirm_before, `capability_scope` when `capabilities[]` is set, `schema_check` when refs or rules are set, …)
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

### Observer presets (AURA-native)

Monitor, Break, Limit, goal_drift, and schedule_slo presets are **host-agnostic** — they work with any `ToolHost`, including `SkillwareHost`. Full preset catalog, config, and `spectrum.services[]` wiring: [observers.md](observers.md).

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

Runnable example: [examples/04-sequencer-pipeline](../examples/04-sequencer-pipeline/). Conditional steps via `when` (prior step result): [examples/06-skillware-sequencer-chain](../examples/06-skillware-sequencer-chain/) · [sequencer.md](sequencer.md).

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
python examples/04-sequencer-pipeline/main.py            # MockSkill
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
