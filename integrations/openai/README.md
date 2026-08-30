# OpenAI (ChatGPT) + Skillware + AURA

Run ChatGPT as the **body** and Skillware skills at AURA **egress**.

## Where AURA sits

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   OpenAI    │     │  Your script │     │    Skillware    │
│  (body LLM) │◄────│  + AURA      │────►│  (tool skills)  │
└─────────────┘     │  session     │     └─────────────────┘
                    │  audit spine │
                    └──────────────┘
```

| Layer | Owns |
|---|---|
| **OpenAI API** | Model inference, chat completions |
| **Skillware** | Skill bundles, `execute(params)` implementations |
| **AURA** | Session identity, egress policy, approval gates, JSONL audit export |
| **Your script** | Loop order: when to call the model vs when to call skills |

AURA does **not** hold your API keys beyond what your script passes to the OpenAI client. It **does** record every Skillware call and enforce rules at `tool.call`.

## When to add AURA

Add AURA when you need:

- **Provable audit** — who ran which skill, with what args (redacted as configured)
- **Policy at egress** — deny, confirm-before, token limits on tool calls
- **Conformance** — declared sequencer steps vs spine on close
- **Export** — JSONL + summary for compliance or CI gates

Skip AURA for one-off scripts with no audit or policy requirements.

## Setup

Use the **project venv** (do not install into global Python):

```powershell
cd AURA_Harness
.venv\Scripts\activate
pip install -e ".[skillware,openai]"
copy .env.example .env
```

Set in `.env`:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

## Run

```powershell
python integrations/openai/skillware_body_loop.py
```

The script:

1. Opens an AURA session (`agent` + `session`)
2. Calls OpenAI for a short security narration (`model.call` on spine)
3. Runs `security/prompt_injection_firewall` through `SkillwareHost.execute()` (egress)
4. Closes session and prints exports path

## Extend

- Register more skills: `SkillwareHost.from_registry(session, [...])`
- Chain skills: see [example 06](../../examples/06-skillware-sequencer-chain/)
- Add rules: agent profile `rules` or skill manifest `guardrails`

## Related

- [Skillware integration guide](../../docs/guides/aura-on-skillware.md)
- [Anthropic integration](../anthropic/README.md)
- [Gemini integration](../google/README.md)
- [Ollama (local), no API key](../ollama/README.md)
