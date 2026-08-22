# Integrations

Attach AURA to your stack — models, tool runtimes, frameworks, sandboxes.

| Integration | Path | Notes |
|---|---|---|
| **Overview** | this page | Start here to find your stack |
| **Anthropic** | `integrations/anthropic/` (planned) | Claude API via `.env` |
| **Google Gemini** | `integrations/google/` (planned) | Gemini API via `.env` |
| **LangGraph / CrewAI** | planned | Framework wrap examples |
| **Ollama (local)** | `integrations/ollama/` (planned) | Dev default: `llama3.2:1b` via `.env` |
| **OpenAI** | `integrations/openai/` (planned) | OpenAI API via `.env` |
| **Skillware** | `integrations/skillware/` (planned) | Tool runtime; `[skillware]` extra |

Copy [`.env.example`](../../.env.example) to `.env` for local Ollama or cloud API keys. Do not commit `.env`.

Core AURA patterns (no specific stack): [`examples/`](../examples/) (after flat restructure).

Tight and tailored coat postures may use Skillware bundles for membrane-level operations (limiters, mail, compression, etc.) — see coat-ops docs when shipped.

See also: [skillware-integration.md](../skillware-integration.md) (relocated to `integrations/skillware/` when that folder ships).
