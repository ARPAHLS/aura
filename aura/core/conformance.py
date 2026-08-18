"""Conformance engine — declared vs observed runtime behavior."""

from typing import Any


class ConformanceEngine:
    """Evaluate runtime against manifest and type conformance rules."""

    def check(self, session: Any, observation: dict[str, Any]) -> list[dict[str, Any]]:
        return []
