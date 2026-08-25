#!/usr/bin/env python3
"""Minimal Ollama body loop under an AURA session."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from integrations._shared.env import load_dotenv  # noqa: E402

load_dotenv(_REPO)

from aura import agent, configure  # noqa: E402


def _ollama_chat(
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    timeout: int = 30,
) -> str:
    url = f"{base_url.rstrip('/')}/api/chat"
    body = json.dumps({"model": model, "messages": messages, "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    return str(payload.get("message", {}).get("content", ""))


def run_loop(prompt: str) -> dict[str, Any]:
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    model = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
    configure()

    ag = agent(
        "ollama-llama-loop",
        purpose="Ollama body loop under AURA audit",
    )
    with ag.session(mode="script") as run:
        run.emit("turn.start", {"input": prompt, "provider": "ollama", "model": model})
        output = _ollama_chat(
            base_url,
            model,
            [
                {"role": "system", "content": "Answer briefly."},
                {"role": "user", "content": prompt},
            ],
        )
        run.emit("model.call", {"provider": "ollama", "model": model, "output": output[:500]})
        run.emit("turn.end", {"output": output})

    return {
        "session_id": run.session_id,
        "provider": "ollama",
        "model": model,
        "output": output,
        "exports": run.exports,
    }


def main() -> None:
    prompt = "Say hello from AURA."
    print(json.dumps(run_loop(prompt), indent=2, default=str))


if __name__ == "__main__":
    main()
