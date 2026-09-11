# Integrations

Attach AURA to your stack — models, tool runtimes, frameworks, sandboxes.

**Skillware + AURA:** start with [guides/aura-on-skillware.md](../guides/aura-on-skillware.md).

| Integration | Path | Notes |
|---|---|---|
| **Overview** | [`integrations/README.md`](../../integrations/README.md) | Pick your stack and run command |
| **Skillware** | [`integrations/skillware/`](../../integrations/skillware/) | Reference ToolHost adapter; `[skillware]` extra |
| **Operator identity** | [`integrations/identity/`](../../integrations/identity/) | Optional OIDC/Auth0/manual/mock adapters; `[identity]` extra |
| **Ollama (local)** | [`integrations/ollama/`](../../integrations/ollama/) | Dev default: `llama3.2:1b` via `.env`; stdlib HTTP |
| **Ollama + Skillware** | [`integrations/skillware/ollama_skill_loop.py`](../../integrations/skillware/ollama_skill_loop.py) | Local model body with Skillware egress |
| **OpenAI (ChatGPT)** | [`integrations/openai/`](../../integrations/openai/) | Body loop + Skillware egress; `[openai]` extra |
| **Anthropic (Claude)** | [`integrations/anthropic/`](../../integrations/anthropic/) | Body loop + Skillware egress; `[anthropic]` extra |
| **Google Gemini** | [`integrations/google/`](../../integrations/google/) | Body loop + Skillware egress; `[google]` extra |
| **LangGraph** | [`integrations/langgraph/`](../../integrations/langgraph/) | Planned framework wrapper |

Copy [`.env.example`](../../.env.example) to `.env` for local Ollama or cloud API keys. Do not commit `.env`.

Use the project **`.venv`** for installs (`pip install -e ".[integrations]"`), not global Python.

## Runnable examples

Full catalog: [examples/README.md](../../examples/README.md) (**01–13**, each `NN-name/main.py`).

| Example | Shows |
|---|---|
| [01-minimal-loop](../../examples/01-minimal-loop/) | Emit + export (loose coat) |
| [04-sequencer-pipeline](../../examples/04-sequencer-pipeline/) | Sequencer with mocks |
| [05-skillware-skill-types](../../examples/05-skillware-skill-types/) | Three skill categories under AURA |
| [06-skillware-sequencer-chain](../../examples/06-skillware-sequencer-chain/) | Sequencer chain with conditional `when` steps |
| [07-observer-presets](../../examples/07-observer-presets/) | Monitor + Break + Limit; `spectrum.services[]` |
| [09-audit-pipeline](../../examples/09-audit-pipeline/) | Export slice — report, compare, verify |
| [12-escalation-playbooks](../../examples/12-escalation-playbooks/) | Escalation playbooks on observer/SLO triggers |
| [13-operator-identity](../../examples/13-operator-identity/) | Verified operator trailer (mock adapter) |

## Related docs

- [reference-tool-host-capstone.md](../guides/reference-tool-host-capstone.md) — **360° ToolHost checklist** (AURA-first)
- [skillware-integration.md](../skillware-integration.md) — API reference
- [sequencer.md](../sequencer.md) — step model, gates, and `when`
- [observers.md](../observers.md) — packaged presets and `spectrum.services[]` wiring
- [ROADMAP.md](../ROADMAP.md) — shipped vs deferred
