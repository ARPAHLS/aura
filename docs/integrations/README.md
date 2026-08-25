# Integrations

Attach AURA to your stack — models, tool runtimes, frameworks, sandboxes.

**Skillware + AURA:** start with [guides/aura-on-skillware.md](../guides/aura-on-skillware.md).

| Integration | Path | Notes |
|---|---|---|
| **Overview** | this page | Start here to find your stack |
| **Skillware** | [`integrations/skillware/`](../../integrations/skillware/) | Reference ToolHost adapter; `[skillware]` extra |
| **Ollama (local)** | [`integrations/skillware/ollama_skill_loop.py`](../../integrations/skillware/ollama_skill_loop.py) | Dev default: `llama3.2:1b` via `.env` |
| **OpenAI (ChatGPT)** | [`integrations/openai/`](../../integrations/openai/) | Body loop + Skillware egress; `[openai]` extra |
| **Anthropic (Claude)** | [`integrations/anthropic/`](../../integrations/anthropic/) | Body loop + Skillware egress; `[anthropic]` extra |
| **Google Gemini** | [`integrations/google/`](../../integrations/google/) | Body loop + Skillware egress; `[google]` extra |
| **LangGraph / CrewAI** | planned | Framework wrap examples |

Copy [`.env.example`](../../.env.example) to `.env` for local Ollama or cloud API keys. Do not commit `.env`.

Use the project **`.venv`** for installs (`pip install -e ".[integrations]"`), not global Python.

## Runnable examples

| Example | Shows |
|---|---|
| [05-skillware-skill-types](../examples/05-skillware-skill-types/) | Three skill categories under AURA |
| [06-skillware-sequencer-chain](../examples/06-skillware-sequencer-chain/) | Sequencer chain with conditional `when` steps |
| [07-observer-presets](../examples/07-observer-presets/) | Monitor + Break observer presets |
| [08-emit-only-loop](../examples/08-emit-only-loop/) | Emit-only coat — no tool host |
| [sequencer_pipeline.py](../examples/sequencer_pipeline.py) | Sequencer with mocks |

## Related docs

- [reference-tool-host-capstone.md](../guides/reference-tool-host-capstone.md) — **360° ToolHost checklist** (AURA-first)
- [skillware-integration.md](../skillware-integration.md) — API reference
- [sequencer.md](../sequencer.md) — step model, gates, and `when`
- [skillware-follow-ups.md](../guides/skillware-follow-ups.md) — post-#12 backlog
