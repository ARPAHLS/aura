# Ollama + AURA

Run a local Ollama model as the **body** inside an AURA session.

This example uses only Python stdlib HTTP and the shared stdlib `.env` loader in
`integrations/_shared/env.py`; it does not require `python-dotenv` or the Ollama
Python package.

## Setup

```powershell
ollama pull llama3.2:1b
copy .env.example .env
```

Set in `.env`:

```
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:1b
```

`AURA_HOME` is optional and controls where AURA writes local session data.

Cloud body loops use the same `.env` pattern:

- `OPENAI_API_KEY`, `OPENAI_MODEL` in [`../openai/`](../openai/)
- `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` in [`../anthropic/`](../anthropic/)
- `GOOGLE_API_KEY`, `GEMINI_MODEL` in [`../google/`](../google/)

## Run

```powershell
python integrations/ollama/llama_loop.py
```

The script opens `with ag.session()`, emits `turn.start`, calls Ollama
`/api/chat`, emits `model.call`, then emits `turn.end`.
