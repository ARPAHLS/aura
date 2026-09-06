"""Schedule SLO observer preset — deadline conformance for required work."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, TYPE_CHECKING

from aura.core.goal_slo import (
    is_past_deadline,
    resolve_schedule_slo_config,
)

if TYPE_CHECKING:
    from aura.core.session import Session


class ScheduleSLOObserver:
    """
    Track required tool completion against a daily schedule + grace window.
    Emits ``slo.missed`` when the session closes without required work in time.
    """

    def __init__(self, observer_id: str, session: Session, entry: dict[str, Any]) -> None:
        self.observer_id = observer_id
        self._session = session
        self._config = resolve_schedule_slo_config(session.profile, entry)
        self._now_fn: Callable[[], datetime] | None = self._config.get("now_fn")
        self._session_start = self._current_time()
        self._completed = False
        self._miss_emitted = False
        self._alerts: list[dict[str, Any]] = []

    def on_event(self, event: dict[str, Any]) -> None:
        kind = event.get("kind") or ""
        payload = dict(event.get("payload") or {})

        if kind == self._config["required_kind"]:
            tool = str(payload.get("tool") or payload.get("name") or "")
            skill_id = payload.get("skill_id")
            if self._config["required_skill"] and skill_id != self._config["required_skill"]:
                return
            if tool != self._config["required_tool"]:
                return
            if not is_past_deadline(
                self._session_start,
                self._config["deadline"],
                self._config["grace_minutes"],
                now_fn=self._now_fn,
            ):
                self._completed = True
            return

        if kind == "session.close":
            self._evaluate_on_close()

    def summary(self) -> dict[str, Any]:
        return {
            "completed_in_window": self._completed,
            "miss_emitted": self._miss_emitted,
            "alerts_emitted": len(self._alerts),
        }

    def _evaluate_on_close(self) -> None:
        if self._completed or self._miss_emitted:
            return
        past = is_past_deadline(
            self._session_start,
            self._config["deadline"],
            self._config["grace_minutes"],
            now_fn=self._now_fn,
        )
        phase = "deadline_missed" if past else "incomplete_at_close"
        self._emit_miss(
            f"required tool {self._config['required_tool']!r} not completed within schedule window",
            {
                "required_tool": self._config["required_tool"],
                "deadline": self._config["deadline"].strftime("%H:%M"),
                "grace_minutes": self._config["grace_minutes"],
                "phase": phase,
            },
        )

    def _emit_miss(self, reason: str, detail: dict[str, Any]) -> None:
        self._miss_emitted = True
        alert = {
            "type": "slo.missed",
            "reason": reason,
            "observer_id": self.observer_id,
            **detail,
        }
        self._alerts.append(alert)
        spine = self._session.spine
        if spine is not None:
            spine.append(
                "slo.missed",
                alert,
                agent_ids=self._session.agent_ids_trailer(),
            )

    def _current_time(self) -> datetime:
        if self._now_fn:
            return self._now_fn()
        return datetime.now().astimezone()


def create_schedule_slo_observer(session: Session, entry: dict[str, Any]) -> ScheduleSLOObserver:
    obs_id = str(entry.get("id") or "schedule-slo")
    return ScheduleSLOObserver(obs_id, session, entry)
