"""Single step in a sequencer pipeline."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SequencerStep:
    id: str
    step_type: str  # skill | prompt | op | subflow | gate
    ref: str | None = None
    version: str | None = None
    depends_on: list[str] = field(default_factory=list)
    retry: dict[str, Any] = field(default_factory=dict)
    gates: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
