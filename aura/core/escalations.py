"""Escalation playbooks — configurable responses to observer / SLO events (#47)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from aura.core.spectrum_enforcement import effective_spectrum

if TYPE_CHECKING:
    from aura.core.session import Session

EscalationHandler = Callable[[dict[str, Any], dict[str, Any]], None]

TRIGGER_KINDS: frozenset[str] = frozenset(
    {
        "slo.missed",
        "conformance.drift",
        "observer.alert",
        "constraint.violated",
    }
)

DESTRUCTIVE_ACTIONS: frozenset[str] = frozenset({"pause", "wake"})

DEFAULT_ACTIONS: list[str] = ["log"]


@dataclass
class EscalationRule:
    """One profile escalation rule."""

    on: str
    actions: list[str] = field(default_factory=lambda: list(DEFAULT_ACTIONS))
    after_minutes: int | None = None
    id: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> EscalationRule | None:
        if not isinstance(raw, dict):
            return None
        trigger = raw.get("on") or raw.get("trigger")
        if not trigger:
            return None
        actions_raw = raw.get("actions")
        if actions_raw is None:
            actions = list(DEFAULT_ACTIONS)
        elif isinstance(actions_raw, list):
            actions = [str(item) for item in actions_raw if item]
        else:
            actions = [str(actions_raw)]
        after = raw.get("after_minutes")
        return cls(
            on=str(trigger),
            actions=actions or list(DEFAULT_ACTIONS),
            after_minutes=int(after) if after is not None else None,
            id=str(raw["id"]) if raw.get("id") else None,
        )


def parse_escalation_rules(raw: list[dict[str, Any]] | None) -> list[EscalationRule]:
    if not raw:
        return []
    rules: list[EscalationRule] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        rule = EscalationRule.from_dict(entry)
        if rule is not None:
            rules.append(rule)
    return rules


def parse_action(action: str) -> tuple[str, str | None]:
    """Parse ``nudge:msg``, ``email:ops@corp.com``, or ``pause``."""
    text = str(action).strip()
    if ":" in text:
        name, arg = text.split(":", 1)
        return name.strip().lower(), arg.strip() or None
    return text.lower(), None


def spectrum_allows_destructive(profile: Any) -> bool:
    level = effective_spectrum(profile).level.lower()
    return level in {"mid", "high", "full"}


class EscalationEngine:
    """
    Match spine trigger events to profile ``escalations[]`` and run actions.

    Emits ``escalation.fired`` (and action-specific events such as ``membrane.nudge``).
    """

    def __init__(
        self,
        session: Session,
        rules: list[EscalationRule],
        *,
        custom_handler: EscalationHandler | None = None,
    ) -> None:
        self._session = session
        self._rules = rules
        self._custom_handler = custom_handler
        self._bare_append: Any | None = None
        self._in_dispatch = False
        self._fired: list[dict[str, Any]] = []

    @property
    def fired(self) -> list[dict[str, Any]]:
        return list(self._fired)

    def bind_spine_append(self, bare_append: Any) -> None:
        self._bare_append = bare_append

    def on_event(self, event: dict[str, Any]) -> None:
        if self._in_dispatch:
            return
        kind = str(event.get("kind") or "")
        if kind not in TRIGGER_KINDS or kind.startswith("escalation."):
            return
        for rule in self._rules:
            if rule.on != kind:
                continue
            self._run_rule(rule, event)

    def _run_rule(self, rule: EscalationRule, trigger_event: dict[str, Any]) -> None:
        context = {
            "rule_id": rule.id,
            "trigger_kind": trigger_event.get("kind"),
            "trigger_event_id": trigger_event.get("event_id"),
            "after_minutes": rule.after_minutes,
        }
        results: list[dict[str, Any]] = []
        for action in rule.actions:
            results.append(self._execute_action(action, rule, trigger_event, context))
        self._append_spine(
            "escalation.fired",
            {
                "trigger_kind": trigger_event.get("kind"),
                "trigger_event_id": trigger_event.get("event_id"),
                "rule_id": rule.id,
                "actions": results,
                "after_minutes": rule.after_minutes,
            },
        )

    def _execute_action(
        self,
        action: str,
        rule: EscalationRule,
        trigger_event: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        name, arg = parse_action(action)
        if name in DESTRUCTIVE_ACTIONS and not spectrum_allows_destructive(self._session.profile):
            return {
                "action": name,
                "status": "skipped",
                "reason": "destructive actions require spectrum level mid or higher",
            }

        if name == "log":
            return {"action": "log", "status": "ok"}

        if name == "alert":
            self._append_spine(
                "observer.note",
                {
                    "type": "escalation_alert",
                    "trigger_kind": trigger_event.get("kind"),
                    "rule_id": rule.id,
                    "message": arg or "Escalation playbook fired",
                },
            )
            return {"action": "alert", "status": "ok"}

        if name == "nudge":
            message = arg or "Review session posture and realign to declared goal."
            self._append_spine(
                "membrane.nudge",
                {
                    "message": message,
                    "source": "escalation",
                    "trigger_kind": trigger_event.get("kind"),
                    "rule_id": rule.id,
                },
            )
            return {"action": "nudge", "status": "ok", "message": message}

        if name == "pause":
            request_id = f"escal_pause_{uuid.uuid4().hex[:10]}"
            pause_rule = {
                "type": "escalation_pause",
                "request_id": request_id,
                "source": "escalation",
                "trigger_event_id": trigger_event.get("event_id"),
            }
            self._session.rules.append(pause_rule)
            self._session.state["_escalation_pause_request_id"] = request_id
            return {"action": "pause", "status": "ok", "request_id": request_id}

        if name == "email":
            recipient = arg or "ops@example.com"
            self._append_spine(
                "escalation.email",
                {
                    "to": recipient,
                    "trigger_kind": trigger_event.get("kind"),
                    "trigger_event_id": trigger_event.get("event_id"),
                    "rule_id": rule.id,
                    "delivery": "stub",
                    "note": "Coat op / webhook delivery deferred to issue #49",
                },
            )
            return {"action": "email", "status": "ok", "to": recipient}

        if name == "wake":
            self._append_spine(
                "escalation.wake",
                {
                    "trigger_kind": trigger_event.get("kind"),
                    "trigger_event_id": trigger_event.get("event_id"),
                    "rule_id": rule.id,
                    "note": "Wake field service stub — re-queue handled by host",
                },
            )
            return {"action": "wake", "status": "ok"}

        if name == "custom":
            if self._custom_handler is None:
                return {"action": "custom", "status": "skipped", "reason": "no handler registered"}
            try:
                self._custom_handler(trigger_event, context)
            except Exception as exc:
                return {"action": "custom", "status": "error", "error": str(exc)}
            return {"action": "custom", "status": "ok"}

        return {"action": name, "status": "skipped", "reason": "unknown action"}

    def _append_spine(self, kind: str, payload: dict[str, Any]) -> None:
        append = self._bare_append
        if append is None:
            spine = self._session.spine
            if spine is None:
                return
            append = spine.append
        self._in_dispatch = True
        try:
            record = {
                "kind": kind,
                "payload": payload,
                "event_id": f"escal_{uuid.uuid4().hex[:12]}",
            }
            self._fired.append(record)
            append(
                kind,
                payload,
                agent_ids=self._session.agent_ids_trailer(),
            )
        finally:
            self._in_dispatch = False


def attach_escalation_engine(
    session: Session,
    *,
    custom_handler: EscalationHandler | None = None,
) -> EscalationEngine | None:
    """Wire escalation playbooks when profile declares ``escalations[]``."""
    rules = parse_escalation_rules(getattr(session.profile, "escalations", None))
    if not rules and custom_handler is None:
        return None

    if not rules and custom_handler is not None:
        rules = [
            EscalationRule(on="slo.missed", actions=["custom"]),
            EscalationRule(on="conformance.drift", actions=["custom"]),
            EscalationRule(on="observer.alert", actions=["custom"]),
        ]

    engine = EscalationEngine(session, rules, custom_handler=custom_handler)
    spine = session.spine
    if spine is None:
        return engine

    original_append = spine.append

    def append_with_escalation(*args: Any, **kwargs: Any) -> Any:
        event = original_append(*args, **kwargs)
        engine.on_event(event.to_dict())
        return event

    engine.bind_spine_append(original_append)
    spine.append = append_with_escalation  # type: ignore[method-assign]
    session._escalation_engine = engine
    return engine


def escalation_summary(profile: Any) -> dict[str, Any]:
    rules = parse_escalation_rules(getattr(profile, "escalations", None))
    return {
        "rule_count": len(rules),
        "triggers": sorted({rule.on for rule in rules}),
        "destructive_requires_spectrum": "mid|high|full",
    }
