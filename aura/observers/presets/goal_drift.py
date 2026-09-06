"""Goal drift observer preset — declared goal vs observed tool behavior."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from aura.core.goal_slo import (
    detect_goal_drift,
    extract_searchable_text,
    resolve_goal_drift_config,
)

if TYPE_CHECKING:
    from aura.core.session import Session


class GoalDriftObserver:
    """
    Compare tool intents/calls against profile goal variables and forbidden topics.
    Emits ``conformance.drift`` on the spine; does not block egress.
    """

    def __init__(self, observer_id: str, session: Session, entry: dict[str, Any]) -> None:
        self.observer_id = observer_id
        self._session = session
        self._config = resolve_goal_drift_config(session.profile, entry)
        self._drifts: list[dict[str, Any]] = []

    def on_event(self, event: dict[str, Any]) -> None:
        kind = event.get("kind") or ""
        if kind not in self._config["event_kinds"]:
            return
        payload = dict(event.get("payload") or {})
        text = extract_searchable_text(payload)
        reason = detect_goal_drift(
            text,
            goal=self._config.get("goal"),
            forbidden_topics=self._config["forbidden_topics"],
            required_keywords=self._config["required_keywords"],
            require_all_keywords=self._config["required_keywords_explicit"],
        )
        if not reason:
            return
        self._emit_drift(
            reason,
            {
                "kind": kind,
                "tool": payload.get("tool") or payload.get("name"),
                "goal": self._config.get("goal"),
            },
        )

    def summary(self) -> dict[str, Any]:
        return {"drifts_emitted": len(self._drifts)}

    def _emit_drift(self, reason: str, detail: dict[str, Any]) -> None:
        signature = f"{detail.get('kind')}:{detail.get('tool')}:{reason}"
        if self._drifts and self._drifts[-1].get("signature") == signature:
            return
        drift = {
            "type": "conformance.drift",
            "reason": reason,
            "signature": signature,
            "observer_id": self.observer_id,
            **detail,
        }
        self._drifts.append(drift)
        spine = self._session.spine
        if spine is not None:
            spine.append(
                "conformance.drift",
                drift,
                agent_ids=self._session.agent_ids_trailer(),
            )


def create_goal_drift_observer(session: Session, entry: dict[str, Any]) -> GoalDriftObserver:
    obs_id = str(entry.get("id") or "goal-drift")
    return GoalDriftObserver(obs_id, session, entry)
