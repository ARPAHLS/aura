"""Load and validate sequencer specs."""

from __future__ import annotations

from typing import Any

from aura.sequencer.step import SequencerStep


def load_steps(spec: dict[str, Any] | None) -> list[SequencerStep]:
    raw = (spec or {}).get("steps") or []
    return [
        SequencerStep(
            id=s["id"],
            step_type=s["type"],
            ref=s.get("ref"),
            version=s.get("version"),
            depends_on=list(s.get("depends_on") or []),
            retry=dict(s.get("retry") or {}),
            gates=list(s.get("gates") or []),
            config=dict(s.get("config") or {}),
        )
        for s in raw
    ]


def merge_sequencer_spec(profile_spec: dict[str, Any] | None, override: dict[str, Any] | None) -> dict[str, Any]:
    base = dict(profile_spec or {})
    if override:
        base.update(override)
        if "steps" in override:
            base["steps"] = override["steps"]
    return base
