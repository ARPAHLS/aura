"""Monitor observer preset — after-call analytics on the audit spine."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING
import json
import time

if TYPE_CHECKING:
    from aura.core.session import Session


class MonitorObserver:
    """
    Track tool intents/calls and step timing; emit observer.note on the spine.
    Does not enforce policy (observers never block egress).
    """

    def __init__(
        self, observer_id: str, session: Session, config: dict[str, Any] | None = None
    ) -> None:
        self.observer_id = observer_id
        self._session = session
        self._config = dict(config or {})
        self._tool_call_counts: dict[str, int] = {}
        self._intent_signatures: dict[str, int] = {}
        self._step_started: dict[str, float] = {}
        self._notes: list[dict[str, Any]] = []

    def on_event(self, event: dict[str, Any]) -> None:
        kind = event.get("kind") or ""
        payload = dict(event.get("payload") or {})

        if kind == "tool.call":
            tool = str(payload.get("tool") or payload.get("name") or "unknown")
            self._tool_call_counts[tool] = self._tool_call_counts.get(tool, 0) + 1
        elif kind == "tool.intent":
            tool = str(payload.get("tool") or "unknown")
            args_key = json.dumps(payload.get("args") or {}, sort_keys=True)
            sig = f"{tool}:{args_key}"
            self._intent_signatures[sig] = self._intent_signatures.get(sig, 0) + 1
            max_identical = int(self._config.get("max_identical_intents", 0))
            if max_identical > 0 and self._intent_signatures[sig] >= max_identical:
                self._append_note(
                    "repeated_tool_intent",
                    {"tool": tool, "count": self._intent_signatures[sig], "signature": sig},
                )
        elif kind == "sequencer.step.start":
            step_id = payload.get("step_id") or event.get("step_id")
            if step_id:
                self._step_started[str(step_id)] = time.monotonic()
        elif kind == "sequencer.step.end":
            step_id = payload.get("step_id") or event.get("step_id")
            if step_id:
                started = self._step_started.pop(str(step_id), None)
                if started is not None:
                    elapsed_ms = int((time.monotonic() - started) * 1000)
                    self._append_note("step_timing", {"step_id": step_id, "elapsed_ms": elapsed_ms})

        self._maybe_flush_log()

    def summary(self) -> dict[str, Any]:
        return {
            "tool_call_counts": dict(self._tool_call_counts),
            "intent_signatures": dict(self._intent_signatures),
            "notes_emitted": len(self._notes),
        }

    def _append_note(self, note_type: str, detail: dict[str, Any]) -> None:
        note = {"type": note_type, **detail, "observer_id": self.observer_id}
        self._notes.append(note)
        spine = self._session.spine
        if spine is not None:
            spine.append(
                "observer.note",
                note,
                agent_ids=self._session.agent_ids_trailer(),
            )
        self._write_log_line(note)

    def _maybe_flush_log(self) -> None:
        log_path = self._config.get("log_path")
        if not log_path or not self._tool_call_counts:
            return
        # Periodic summary on tool activity (lightweight side log).
        path = Path(str(log_path))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.summary(), indent=2) + "\n", encoding="utf-8")

    def _write_log_line(self, note: dict[str, Any]) -> None:
        log_path = self._config.get("log_path")
        if not log_path:
            return
        path = Path(str(log_path))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(note, sort_keys=True) + "\n")


def create_monitor_observer(session: Session, entry: dict[str, Any]) -> MonitorObserver:
    obs_id = str(entry.get("id") or "monitor")
    config = entry.get("config") if isinstance(entry.get("config"), dict) else {}
    return MonitorObserver(obs_id, session, config)
