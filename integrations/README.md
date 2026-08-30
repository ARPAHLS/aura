# Integrations

Pick your stack, then run the matching AURA loop.

| Stack | Path | Run |
|---|---|---|
| Ollama (local body) | [ollama/](ollama/) | `python integrations/ollama/llama_loop.py` |
| Ollama + Skillware | [skillware/](skillware/) | `python integrations/skillware/ollama_skill_loop.py` |
| Skillware (tools only) | [skillware/](skillware/) | `python integrations/skillware/mock_tools.py` |
| Operator identity | [identity/](identity/) | `python examples/09-operator-identity/main.py` |
| OpenAI (ChatGPT) | [openai/](openai/) | `python integrations/openai/skillware_body_loop.py` |
| Anthropic (Claude) | [anthropic/](anthropic/) | `python integrations/anthropic/skillware_body_loop.py` |
| Google Gemini | [google/](google/) | `python integrations/google/skillware_body_loop.py` |
| LangGraph | [langgraph/](langgraph/) | Planned framework wrapper |

`examples/` stays focused on core AURA patterns: minimal loop, guarded tools,
task mode, observer presets, and sequencer demos. `integrations/` is for
stack-specific wiring, optional clients, and provider-specific run notes.

Use the project virtualenv:

```bash
pip install -e ".[integrations]"
```

Copy [`.env.example`](../.env.example) to `.env` when a stack needs local model
or API settings. Do not commit `.env`.

Every integration records the same AURA boundary: session identity, model/body
events when present, egress tool calls, policy outcomes, and JSONL export paths.
