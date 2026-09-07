"""Limit observer preset — rate and token budget circuit breaker."""

from __future__ import annotations

import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from aura.core.session import Session


class LimitObserver:
    """
    Track tool-call rate and per-step token budgets.

    Emits observer.note as limits approach; observer.alert on breach.
    Alert-only — does not block egress (playbooks / host act on alerts).
    """

    def __init__(
        self, observer_id: str, session: Session, config: dict[str, Any] | None = None
    ) -> None:
        self.observer_id = observer_id
        self._session = session
        self._config = dict(config or {})
        self._call_times: list[float] = []
        self._notes: list[dict[str, Any]] = []
        self._alerts: list[dict[str, Any]] = []

    def on_event(self, event: dict[str, Any]) -> None:
        kind = event.get("kind") or ""
        payload = dict(event.get("payload") or {})

        if kind == "tool.call":
            self._call_times.append(time.monotonic())
            self._prune_call_window()
            self._check_call_rate()
            tokens = payload.get("tokens")
            if tokens is not None:
                self._check_tokens(int(tokens))
        elif kind in {"turn.end", "tool.result"} and payload.get("tokens") is not None:
            self._check_tokens(int(payload["tokens"]))

    def summary(self) -> dict[str, Any]:
        return {
            "calls_in_window": len(self._call_times),
            "notes_emitted": len(self._notes),
            "alerts_emitted": len(self._alerts),
        }

    def _prune_call_window(self) -> None:
        cutoff = time.monotonic() - 60.0
        self._call_times = [t for t in self._call_times if t >= cutoff]

    def _check_call_rate(self) -> None:
        max_calls = int(self._config.get("max_tool_calls_per_minute", 0))
        if max_calls <= 0:
            return
        count = len(self._call_times)
        if count > max_calls:
            self._emit_alert(
                "rate_limit_exceeded",
                {
                    "count": count,
                    "threshold": max_calls,
                    "window_seconds": 60,
                },
            )
        elif count == max_calls:
            self._emit_note(
                "rate_limit_warning",
                {
                    "count": count,
                    "threshold": max_calls,
                    "window_seconds": 60,
                },
            )

    def _check_tokens(self, tokens: int) -> None:
        max_tokens = int(self._config.get("max_tokens_per_step", 0))
        if max_tokens <= 0:
            return
        warn_ratio = float(self._config.get("warn_ratio", 0.8))
        warn_at = int(max_tokens * warn_ratio)
        if tokens > max_tokens:
            self._emit_alert(
                "token_budget_exceeded",
                {
                    "tokens": tokens,
                    "threshold": max_tokens,
                },
            )
        elif tokens >= warn_at:
            self._emit_note(
                "token_budget_warning",
                {
                    "tokens": tokens,
                    "threshold": max_tokens,
                    "warn_at": warn_at,
                },
            )

    def _emit_note(self, note_type: str, detail: dict[str, Any]) -> None:
        signature = f"note:{note_type}:{detail.get('threshold')}"
        if self._notes and self._notes[-1].get("signature") == signature:
            return
        note = {
            "type": note_type,
            "signature": signature,
            "observer_id": self.observer_id,
            **detail,
        }
        self._notes.append(note)
        spine = self._session.spine
        if spine is not None:
            spine.append(
                "observer.note",
                note,
                agent_ids=self._session.agent_ids_trailer(),
            )

    def _emit_alert(self, alert_type: str, detail: dict[str, Any]) -> None:
        signature = f"alert:{alert_type}:{detail.get('threshold')}"
        if self._alerts and self._alerts[-1].get("signature") == signature:
            return
        alert = {
            "type": alert_type,
            "signature": signature,
            "observer_id": self.observer_id,
            **detail,
        }
        self._alerts.append(alert)
        spine = self._session.spine
        if spine is not None:
            spine.append(
                "observer.alert",
                alert,
                agent_ids=self._session.agent_ids_trailer(),
            )


def create_limit_observer(session: Session, entry: dict[str, Any]) -> LimitObserver:
    obs_id = str(entry.get("id") or "limit")
    config = entry.get("config") if isinstance(entry.get("config"), dict) else {}
    return LimitObserver(obs_id, session, config)
