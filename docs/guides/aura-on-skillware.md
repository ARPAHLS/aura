# AURA on top of Skillware

How to combine [Skillware](https://github.com/arpahls/skillware) (skills) with AURA Harness (audit, policy, export) — with runnable examples, provider integrations, and best practices.

**Audience:** Teams running Skillware skills behind an LLM host who need provenance, egress policy, or compliance-ready session exports.

→ Quick API reference: [skillware-integration.md](../skillware-integration.md)  
→ Sequencer details: [sequencer.md](../sequencer.md)

---

## Stack position

```
                    ┌──────────────────────────────────────┐
                    │           Your host script            │
                    │  (loop, routing, provider API calls)  │
                    └───────────────┬──────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         │                          │                          │
         ▼                          ▼                          ▼
   ┌───────────┐            ┌─────────────┐            ┌─────────────┐
   │ Body LLM  │            │    AURA     │            │  Skillware  │
   │ Ollama /  │            │  membrane   │            │   skills    │
   │ GPT / etc │            │ audit+policy│            │  execute()  │
   └───────────┘            └──────┬──────┘            └──────▲──────┘
                                   │                         │
                                   │    tool.intent/call     │
                                   └─────────────────────────┘
                                              egress
```

| Component | Responsibility |
|---|---|
| **Skillware** | Skill registry, manifests, `BaseSkill.execute(params)`, CLI (`skillware list`, `doctor`) |
| **Body LLM** | Language, planning, user-facing replies (Ollama, OpenAI, Claude, Gemini, …) |
| **AURA** | Session identity, ingress context, **egress guard** on every tool call, spine + export |
| **Sequencer** (optional) | Declarative step order inside a session — skill chains with gates |

AURA is **not** a skill framework and **not** an LLM runtime. It wraps the boundary where Skillware skills are invoked.

---

## When to use AURA (and when not to)

### Use AURA when you need

| Need | AURA feature |
|---|---|
| Audit trail of tool calls | `tool.intent` → `tool.call` → `tool.result` on JSONL spine |
| Deny / confirm-before on tools | Session rules + manifest `guardrails` merged at bind |
| Human approval on risky steps | `human_confirm` gate + `run.approve()` |
| Proof of pipeline order | Sequencer + conformance check on close |
| Export for compliance / SIEM | `.summary.json`, audit report, optional OTel |
| Same skills, different hosts | `SkillwareHost` adapter — swap body, keep audit |

### Skip AURA when

- Prototype with no audit or policy requirements
- Skillware CLI alone is enough (`skillware run …`)
- You only need unit tests inside Skillware, not session-level provenance

---

## Installation (project venv)

Always use the repo **`.venv`**, not global Python:

```powershell
cd AURA_Harness
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev,skillware]"
```

Optional provider clients:

```powershell
pip install -e ".[integrations]"     # skillware + ollama + openai + anthropic + google
pip install -e ".[openai]"           # OpenAI only
```

Verify Skillware:

```bash
skillware list
skillware doctor optimization/prompt_rewriter
skillware doctor security/prompt_injection_firewall
```

---

## Core pattern: SkillwareHost at egress

Every Skillware call should go through `SkillwareHost.execute()` so AURA can enforce rules and record events.

```python
from aura import agent, configure
from aura.hosts import SkillwareHost

configure()

with agent("my-agent", skills=["security/prompt_injection_firewall"]).session() as run:
    host = SkillwareHost.from_registry(run._session, ["security/prompt_injection_firewall"])
    result = host.execute(
        "security/prompt_injection_firewall",
        "security/prompt_injection_firewall",
        {"source_text": untrusted_text, "sensitivity": "balanced"},
    )
# run.exports → jsonl, summary, otel
```

**Execute contract:** Skillware uses `execute(params: dict)`. The second argument to `host.execute()` is the audit label (usually the registry skill id). AURA's adapter detects the signature automatically.

---

## Skill types walkthrough

These three bundled skills are **offline** (no API keys) and illustrate different categories:

| Registry id | Category | Role in a loop |
|---|---|---|
| `security/prompt_injection_firewall` | Security | Scan untrusted text **before** it enters LLM context |
| `optimization/prompt_rewriter` | Optimization | Compress verbose prompts to save tokens |
| `monitoring/token_limiter` | Monitoring | Return CONTINUE / WARN / FORCE_TERMINATE for budget |

### Runnable tour

| Example | What it shows |
|---|---|
| [05-skillware-skill-types](../../examples/05-skillware-skill-types/) | All three skills in one session (mock default) |
| [06-skillware-sequencer-chain](../../examples/06-skillware-sequencer-chain/) | Same three as a declarative pipeline |

Live mode (real Skillware registry):

```powershell
$env:SKILLWARE_LIVE = "1"
python examples/05-skillware-skill-types/main.py
```

Other registry skills (may need API keys or local models): `compliance/pii_masker`, `office/gmail_handler`, `finance/wallet_screening` — same host API, different manifests.

---

## Body LLM + Skillware + AURA

The **body** (LLM) and **tools** (Skillware) are separate concerns. AURA records both if you emit model events.

Recommended loop:

1. `turn.start` — user input on spine  
2. **Skillware pre-flight** — e.g. injection firewall on untrusted input  
3. **Body LLM call** — emit `model.call` with provider + model id  
4. **Skillware tools** as needed — always via `host.execute()`  
5. `turn.end` — close turn; session export on context exit  

### Provider integration scripts

| Provider | Path | Env vars |
|---|---|---|
| Ollama (local) | [integrations/skillware/ollama_skill_loop.py](../../integrations/skillware/ollama_skill_loop.py) | `OLLAMA_MODEL`, `OLLAMA_BASE_URL` |
| OpenAI | [integrations/openai/](../../integrations/openai/) | `OPENAI_API_KEY`, `OPENAI_MODEL` |
| Anthropic | [integrations/anthropic/](../../integrations/anthropic/) | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |
| Google Gemini | [integrations/google/](../../integrations/google/) | `GOOGLE_API_KEY`, `GEMINI_MODEL` |

Each script demonstrates the same architecture: **LLM body + Skillware egress under one AURA session**.

---

## Sequencer: skill chaining

For fixed SOPs (scan → transform → budget check), declare steps instead of imperative calls:

```yaml
sequencer:
  steps:
    - id: scan_input
      type: skill
      ref: security/prompt_injection_firewall
      config:
        tool: security/prompt_injection_firewall
        args: { source_text: "...", sensitivity: balanced }
    - id: compress_prompt
      type: skill
      ref: optimization/prompt_rewriter
      depends_on: [scan_input]
      config:
        tool: optimization/prompt_rewriter
        args: { raw_text: "...", compression_aggression: high }
```

Run with:

```python
result = run.run_sequencer(spec=pipeline, host=host)
```

See [example 06](../../examples/06-skillware-sequencer-chain/) and [sequencer.md](../sequencer.md).

Add `gates: [human_confirm]` on steps that send email, move funds, or export data.

---

## Manifests, guardrails, and constitution

| Skillware field | AURA behavior at bind |
|---|---|
| `name`, `parameters` | Snapshot on `skill.registered` |
| `constitution` (text) | Audit metadata — **not** auto-enforced as machine rules |
| `guardrails` (AURA extension) | Merged into session constraint rules |

Example overlay:

```yaml
guardrails:
  deny_tools: ["send.bulk"]
  confirm_before: ["send"]
```

Skillware's textual constitution remains visible in exports; add `guardrails` when you need machine-enforceable rules.

---

## Best practices

1. **Always egress through `SkillwareHost`** — direct `skill.execute()` bypasses policy and audit.  
2. **Scan before context** — run security skills on external input before passing to the body LLM.  
3. **Emit model calls** — `run.emit("model.call", {provider, model, ...})` separates body from tools on the spine.  
4. **Mock in CI, live locally** — examples use `SKILLWARE_LIVE=1` for registry skills; default mock keeps CI green.  
5. **Use sequencer for compliance paths** — declarative order + conformance on close.  
6. **Project venv** — `pip install -e ".[skillware]"` inside `.venv`, not system Python.  
7. **Verify skills** — `skillware doctor <id>` before wiring into production hosts.

---

## Testing

```powershell
.venv\Scripts\activate
pytest -m "not ollama"                    # default CI
pytest -m skillware                       # live registry skills
python examples/05-skillware-skill-types/main.py
python examples/06-skillware-sequencer-chain/main.py
```

→ [TESTING.md](../TESTING.md)

---

## File map

| Path | Purpose |
|---|---|
| `aura/hosts/protocol.py` | `ToolHost` protocol (any skill runtime) |
| `aura/hosts/bind.py` | Bind context for `skill.registered` |
| `aura/hosts/skillware.py` | `SkillwareHost`, `from_registry()` |
| `aura/observers/presets/` | Monitor + Break packaged presets |
| `integrations/skillware/` | Ollama + reference scripts |
| `integrations/openai/`, `anthropic/`, `google/` | Cloud body loops |
| `examples/sequencer_pipeline.py` | Sequencer with mocks |
| `examples/05-*` … `08-*` | ToolHost tour: skills, chain, observers, emit-only |
| `docs/skillware-integration.md` | API-focused reference |
| `docs/guides/reference-tool-host-capstone.md` | AURA-first 360° checklist |

---

## Follow-up work

See [skillware-follow-ups.md](skillware-follow-ups.md) for post–#12 backlog: flat examples ([#21](https://github.com/ARPAHLS/aura/issues/21)), limit preset, multi-provider comparison page, docs sweep.

---

## Related

- [using-aura.md](../using-aura.md) — membrane and postures  
- [stack-position.md](../stack-position.md) — where AURA fits in the agent stack  
- [Skillware repository](https://github.com/arpahls/skillware)
