"""Break observer preset — circuit-breaker alerts for runaway tool patterns."""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from aura.core.session import Session


class BreakObserver:
    """
    Detect repeated identical tool intents and emit observer.alert on the spine.
    Does not block egress — host or escalation layer acts on alerts.
    """

    def __init__(
        self, observer_id: str, session: Session, config: dict[str, Any] | None = None
    ) -> None:
        self.observer_id = observer_id
        self._session = session
        self._config = dict(config or {})
        self._intent_signatures: dict[str, int] = {}
        self._alerts: list[dict[str, Any]] = []

    def on_event(self, event: dict[str, Any]) -> None:
        if event.get("kind") != "tool.intent":
            return
        payload = dict(event.get("payload") or {})
        tool = str(payload.get("tool") or "unknown")
        args_key = json.dumps(payload.get("args") or {}, sort_keys=True)
        sig = f"{tool}:{args_key}"
        self._intent_signatures[sig] = self._intent_signatures.get(sig, 0) + 1
        threshold = int(self._config.get("max_identical_intents", 5))
        count = self._intent_signatures[sig]
        if threshold > 0 and count >= threshold:
            self._emit_alert(
                "repeated_tool_intent",
                {
                    "tool": tool,
                    "count": count,
                    "threshold": threshold,
                    "signature": sig,
                },
            )

    def summary(self) -> dict[str, Any]:
        return {
            "intent_signatures": dict(self._intent_signatures),
            "alerts_emitted": len(self._alerts),
        }

    def _emit_alert(self, alert_type: str, detail: dict[str, Any]) -> None:
        last = self._alerts[-1] if self._alerts else None
        if (
            last
            and last.get("type") == alert_type
            and last.get("signature") == detail.get("signature")
        ):
            if last.get("count") == detail.get("count"):
                return
        alert = {"type": alert_type, **detail, "observer_id": self.observer_id}
        self._alerts.append(alert)
        spine = self._session.spine
        if spine is not None:
            spine.append(
                "observer.alert",
                alert,
                agent_ids=self._session.agent_ids_trailer(),
            )


def create_break_observer(session: Session, entry: dict[str, Any]) -> BreakObserver:
    obs_id = str(entry.get("id") or "break")
    config = entry.get("config") if isinstance(entry.get("config"), dict) else {}
    return BreakObserver(obs_id, session, config)
