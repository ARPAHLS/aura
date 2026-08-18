"""Session lifecycle — manifest, session_id, state, constitution hash."""

from dataclasses import dataclass, field
from typing import Any
import uuid


@dataclass
class Session:
    """One runtime activation of a manifest."""

    manifest: dict[str, Any]
    session_id: str = field(default_factory=lambda: f"aura_sess_{uuid.uuid4().hex[:12]}")
    task_id: str | None = None
    state: dict[str, Any] = field(default_factory=dict)
    constitution_hash: str | None = None

    def open(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
