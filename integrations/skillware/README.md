# Skillware integration (reference adapter)

AURA wraps [Skillware](https://github.com/arpahls/skillware) at **egress** — policy, approval, and audit on every tool call. Skillware supplies installable skills; AURA does not replace Skillware's runtime.

**Start here:** [docs/guides/aura-on-skillware.md](../../docs/guides/aura-on-skillware.md) — full guide, skill types, sequencer chains, best practices.

## Install (project venv)

```powershell
.venv\Scripts\activate
pip install -e ".[dev,skillware]"     # aura-harness + skillware>=0.5.1
pip install -e ".[integrations]"      # + ollama, openai, anthropic, google clients
```

Copy [`.env.example`](../../.env.example) to `.env`. See provider sections below.

Verify Skillware:

```bash
skillware list
skillware doctor optimization/prompt_rewriter
skillware doctor security/prompt_injection_firewall
```

## Scripts in this folder

| Script | Purpose |
|---|---|
| [`reference_tool_host.py`](reference_tool_host.py) | Mock (default) or live Skillware via `SKILLWARE_LIVE=1` |
| [`ollama_skill_loop.py`](ollama_skill_loop.py) | Ollama `llama3.2:1b` + real `prompt_injection_firewall` through AURA |

## Examples (repo root)

| Example | Purpose |
|---|---|
| [05-skillware-skill-types](../../examples/05-skillware-skill-types/) | Security + optimization + monitoring skills |
| [06-skillware-sequencer-chain](../../examples/06-skillware-sequencer-chain/) | Declarative scan → compress → budget pipeline |
| [sequencer_pipeline.py](../../examples/sequencer_pipeline.py) | Sequencer concepts with mocks |

Set `$env:SKILLWARE_LIVE = "1"` for live registry skills in examples 05 and 06.

## Cloud body + Skillware egress

| Provider | README | Script |
|---|---|---|
| OpenAI (ChatGPT) | [../openai/README.md](../openai/README.md) | `../openai/skillware_body_loop.py` |
| Anthropic (Claude) | [../anthropic/README.md](../anthropic/README.md) | `../anthropic/skillware_body_loop.py` |
| Google Gemini | [../google/README.md](../google/README.md) | `../google/skillware_body_loop.py` |
| Ollama (local) | this folder | `ollama_skill_loop.py` |

All follow the same pattern: **LLM body turn** + **Skillware skills at AURA egress** + **session export**.

## Python API

```python
from aura import agent, configure
from aura.hosts import SkillwareHost, load_registry_skill

configure()
with agent("demo", skills=["security/prompt_injection_firewall"]).session() as run:
    host = SkillwareHost(run._session)
    host.register_registry_skill("security/prompt_injection_firewall")
    result = host.execute(
        "security/prompt_injection_firewall",
        "security/prompt_injection_firewall",
        {"source_text": untrusted_text, "sensitivity": "balanced"},
    )
```

## Architecture

```
Session open → membrane.ingress
Skill register → skill.registered (+ optional rule merge)
Tool call → tool.intent → tool.call (constraints) → Skillware.execute(params) → tool.result
Session close → JSONL + summary + audit report
```

Parent epic: [#12](https://github.com/ARPAHLS/aura/issues/12) · API reference: [skillware-integration.md](../../docs/skillware-integration.md)
