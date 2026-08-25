"""Ollama loop tests with mocked HTTP."""

from __future__ import annotations

import json
from pathlib import Path

from integrations.ollama import llama_loop


class _MockResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps({"message": {"content": "mocked llama reply"}}).encode("utf-8")


def test_ollama_loop_emits_model_call_without_network(monkeypatch, aura_home):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        seen["body"] = json.loads(request.data.decode("utf-8"))
        return _MockResponse()

    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:1b")
    monkeypatch.setattr(llama_loop.urllib.request, "urlopen", fake_urlopen)

    result = llama_loop.run_loop("hello")

    assert result["output"] == "mocked llama reply"
    assert result["model"] == "llama3.2:1b"
    assert seen["url"] == "http://ollama.test/api/chat"
    assert seen["body"]["stream"] is False
    assert seen["body"]["model"] == "llama3.2:1b"
    assert [m["role"] for m in seen["body"]["messages"]] == ["system", "user"]

    jsonl = Path(result["exports"]["jsonl"])
    kinds = [json.loads(line)["kind"] for line in jsonl.read_text(encoding="utf-8").splitlines()]
    assert "model.call" in kinds
    assert kinds.index("turn.start") < kinds.index("model.call") < kinds.index("turn.end")
