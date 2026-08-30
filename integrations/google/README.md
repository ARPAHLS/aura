# Google Gemini + Skillware + AURA

Run Gemini as the **body** and Skillware skills at AURA **egress**.

## Where AURA sits

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Gemini    │     │  Your script │     │    Skillware    │
│  (body LLM) │◄────│  + AURA      │────►│  (tool skills)  │
└─────────────┘     │  session     │     └─────────────────┘
                    │  audit spine │
                    └──────────────┘
```

| Layer | Owns |
|---|---|
| **Google Generative AI** | Gemini inference |
| **Skillware** | Registry skills, manifests, CLI |
| **AURA** | Membrane egress, observers, export |
| **Your script** | Wiring and loop control |

## When to add AURA

Gemini + Skillware alone gives you tools and a model. AURA adds:

- **Egress gate** on every `host.execute()` — constitution, confirm-before, deny lists
- **Causal spine** — ordered events with session id and agent ref
- **CI conformance** — fail builds when sequencer order or rules diverge

## Setup

```powershell
.venv\Scripts\activate
pip install -e ".[skillware,google]"
copy .env.example .env
```

```
GOOGLE_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash
```

## Run

```powershell
python integrations/google/skillware_body_loop.py
```

Uses offline `security/prompt_injection_firewall` — no extra Skillware API keys.

## Related

- [aura-on-skillware.md](../../docs/guides/aura-on-skillware.md)
- [OpenAI](../openai/README.md) · [Anthropic](../anthropic/README.md)
- [Ollama local loop](../ollama/README.md)
