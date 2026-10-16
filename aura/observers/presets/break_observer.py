"""Break observer preset — circuit-breaker alerts & trajectory cycle detector (#93).

Monitors causal spine events to detect:
1. Repeated Tool Intents: Global threshold count (backward compatible with V0.1).
2. Action Fixation (1-cycle): Identical tool + normalized args repeating consecutively.
3. State Oscillation (2-cycle): Alternating actions (A -> B -> A -> B) across turns.
4. Cyclic Choreography (3-cycle): Repetitive action sequences (A -> B -> C -> A -> B -> C).
5. Error Fingerprint Churn: Consecutive identical error codes or failure messages.
6. Reasoning Inertia: Consecutive turns exhibiting high thought text similarity (>85%).
7. FinOps Burn-Velocity Guard: Churn token tracking and rate alerts.
8. Non-Repudiable Cryptographic Deadlock Proofs: Captures entry/exit spine hashes.
9. Optional Watchdog Mode (Tier 2): Pluggable callable/model for semantic loop audit.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from aura.core.session import Session


@dataclass
class ActionRecord:
    tool: str
    args: dict[str, Any]
    sig: str
    turn: int
    spine_hash: str | None = None
    has_error: bool = False
    error_fingerprint: str = ""


@dataclass
class TurnRecord:
    turn: int
    thought: str


class BreakObserver:
    """
    Detect repeated identical tool intents, trajectory cycles, and cognitive churn.
    Emits observer.alert on the causal spine when runaway loops occur.
    Does not block egress — host or escalation layer acts on alerts.
    """

    def __init__(
        self,
        observer_id: str,
        session: Session,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.observer_id = observer_id
        self._session = session
        self._config = dict(config or {})

        # Configuration parameters
        self.window_size: int = int(self._config.get("window_size", 8))
        self.max_identical_intents: int = int(self._config.get("max_identical_intents", 5))
        self.max_identical_actions: int = int(self._config.get("max_identical_actions", 3))
        self.max_oscillation_cycles: int = int(self._config.get("max_oscillation_cycles", 2))
        self.max_choreography_cycles: int = int(self._config.get("max_choreography_cycles", 2))
        self.max_error_churn: int = int(self._config.get("max_error_churn", 3))
        self.thought_similarity_threshold: float = float(
            self._config.get("thought_similarity_threshold", 0.85)
        )
        self.max_thought_inertia: int = int(self._config.get("max_thought_inertia", 3))
        self.burn_velocity_guard: bool = bool(self._config.get("burn_velocity_guard", False))
        self.max_cycle_token_waste: int = int(self._config.get("max_cycle_token_waste", 0))

        self.action: str = str(self._config.get("action", "alert_only")).lower()
        self.mode: str = str(self._config.get("mode", "default")).lower()
        self.watchdog_fn: Callable[[list[dict[str, Any]]], dict[str, Any] | None] | None = (
            self._config.get("watchdog_fn") or self._config.get("watchdog_model")
        )

        # In-memory sliding trajectory window & counters
        self._current_turn: int = 1
        self._intent_signatures: dict[str, int] = {}
        self._action_history: list[ActionRecord] = []
        self._turn_history: list[TurnRecord] = []
        self._alerts: list[dict[str, Any]] = []
        self._tripped_dedup_keys: set[str] = set()
        self._cycle_token_accumulator: int = 0

    def on_event(self, event: dict[str, Any]) -> None:
        kind = event.get("kind")
        payload = dict(event.get("payload") or {})

        if kind == "turn.start":
            self._handle_turn_start(payload)
        elif kind in ("tool.intent", "tool.call"):
            self._handle_tool_action(kind, payload)
        elif kind in ("tool.result", "tool.error"):
            self._handle_tool_result(payload)
        elif kind == "turn.end":
            self._current_turn += 1

    def _handle_turn_start(self, payload: dict[str, Any]) -> None:
        thought = str(
            payload.get("thought") or payload.get("reasoning") or payload.get("prompt") or ""
        ).strip()
        if not thought:
            return

        turn_rec = TurnRecord(turn=self._current_turn, thought=thought)
        self._turn_history.append(turn_rec)
        if len(self._turn_history) > self.window_size:
            self._turn_history.pop(0)

        # Check reasoning inertia across recent consecutive turns
        if len(self._turn_history) >= self.max_thought_inertia:
            recent_thoughts = [t.thought for t in self._turn_history[-self.max_thought_inertia :]]
            similar_count = 0
            for i in range(len(recent_thoughts) - 1):
                t1, t2 = recent_thoughts[i], recent_thoughts[i + 1]
                ratio = difflib.SequenceMatcher(None, t1, t2).ratio()
                if ratio >= self.thought_similarity_threshold:
                    similar_count += 1

            if similar_count >= (self.max_thought_inertia - 1):
                directive = (
                    f"BREAK: Consecutive reasoning steps show >="
                    f"{int(self.thought_similarity_threshold * 100)}% text similarity "
                    f"across {self.max_thought_inertia} turns. Re-evaluate strategy or context."
                )
                self._emit_alert(
                    alert_type="loop_cycle_detected",
                    detail={
                        "pattern": "REASONING_INERTIA",
                        "tool": "host.reasoning",
                        "count": self.max_thought_inertia,
                        "threshold": self.max_thought_inertia,
                        "signature": f"thought_inertia_turn_{self._current_turn}",
                        "remedial_directive": directive,
                    },
                )

    def _handle_tool_action(self, kind: str, payload: dict[str, Any]) -> None:
        tool = str(payload.get("tool") or "unknown")
        raw_args = payload.get("args") or {}
        args_key = self._normalize_args(raw_args)
        sig = f"{tool}:{args_key}"

        # Global intent counting for 100% backward compatibility
        self._intent_signatures[sig] = self._intent_signatures.get(sig, 0) + 1
        count = self._intent_signatures[sig]

        # 1. Legacy global threshold alert
        if self.max_identical_intents > 0 and count >= self.max_identical_intents:
            self._emit_alert(
                alert_type="repeated_tool_intent",
                detail={
                    "tool": tool,
                    "count": count,
                    "threshold": self.max_identical_intents,
                    "signature": sig,
                    "pattern": "REPEATED_INTENT",
                    "remedial_directive": (
                        f"BREAK: Repeated identical tool intent '{tool}' "
                        f"{count} times. Alter parameters or revise approach."
                    ),
                },
            )

        # Record action in sliding trajectory window
        spine = getattr(self._session, "spine", None)
        last_hash = getattr(spine, "_last_content_hash", None) if spine else None

        action_rec = ActionRecord(
            tool=tool,
            args=raw_args if isinstance(raw_args, dict) else {},
            sig=sig,
            turn=self._current_turn,
            spine_hash=last_hash,
        )
        self._action_history.append(action_rec)
        if len(self._action_history) > self.window_size:
            self._action_history.pop(0)

        # 2. Action Fixation (1-cycle: A -> A -> A consecutively in recent window)
        self._check_action_fixation(tool, sig)

        # 3. State Oscillation (2-cycle: A -> B -> A -> B)
        self._check_oscillation_cycle()

        # 4. Choreography Cycle (3-cycle: A -> B -> C -> A -> B -> C)
        self._check_choreography_cycle()

        # 5. Optional Watchdog Mode (Tier 2 Model/Callable)
        if self.mode == "watchdog" and callable(self.watchdog_fn):
            self._check_watchdog_model()

    def _handle_tool_result(self, payload: dict[str, Any]) -> None:
        tool = str(payload.get("tool") or "")
        result = payload.get("result")
        error = payload.get("error")
        status = payload.get("status")

        # Track tokens for burn-velocity guard
        tokens = int(
            payload.get("tokens") or payload.get("token_count") or payload.get("total_tokens") or 0
        )
        self._cycle_token_accumulator += tokens

        has_error = False
        err_msg = ""
        if error:
            has_error = True
            err_msg = str(error)
        elif isinstance(result, dict) and ("error" in result or result.get("success") is False):
            has_error = True
            err_msg = str(result.get("error") or result.get("message") or "failure")
        elif isinstance(status, (int, str)) and str(status).isdigit() and int(status) >= 400:
            has_error = True
            err_msg = f"HTTP_{status}"

        if not has_error:
            return

        fingerprint = hashlib.sha256(err_msg.encode("utf-8")).hexdigest()[:8]
        if self._action_history:
            last_action = self._action_history[-1]
            last_action.has_error = True
            last_action.error_fingerprint = fingerprint

        # Check consecutive error status churn
        recent_errors = [a for a in self._action_history if a.has_error]
        if len(recent_errors) >= self.max_error_churn:
            last_fps = [a.error_fingerprint for a in recent_errors[-self.max_error_churn :]]
            if len(set(last_fps)) == 1:
                directive = (
                    f"BREAK: Tool '{tool}' returned identical error fingerprint "
                    f"({fingerprint}) {self.max_error_churn} consecutive times. "
                    f"Back off and resolve root cause before retrying."
                )
                self._emit_alert(
                    alert_type="loop_cycle_detected",
                    detail={
                        "pattern": "ERROR_STATUS_CHURN",
                        "tool": tool,
                        "count": self.max_error_churn,
                        "threshold": self.max_error_churn,
                        "signature": f"err_{fingerprint}",
                        "remedial_directive": directive,
                    },
                )

    def _check_action_fixation(self, tool: str, sig: str) -> None:
        """Detect identical action repeated N times consecutively in window."""
        if len(self._action_history) < self.max_identical_actions:
            return

        recent = self._action_history[-self.max_identical_actions :]
        if all(a.sig == sig for a in recent):
            directive = (
                f"BREAK: Repeated identical action '{tool}' "
                f"{self.max_identical_actions} times consecutively. "
                f"Alter parameters or revise approach."
            )
            self._emit_alert(
                alert_type="loop_cycle_detected",
                detail={
                    "pattern": "ACTION_FIXATION",
                    "tool": tool,
                    "count": self.max_identical_actions,
                    "threshold": self.max_identical_actions,
                    "signature": sig,
                    "remedial_directive": directive,
                },
            )

    def _check_oscillation_cycle(self) -> None:
        """Detect alternating 2-state oscillation: A -> B -> A -> B."""
        needed_length = self.max_oscillation_cycles * 2
        if len(self._action_history) < needed_length:
            return

        window = self._action_history[-needed_length:]
        sigs = [a.sig for a in window]
        a_sig, b_sig = sigs[0], sigs[1]

        if a_sig == b_sig:
            return  # Handled by action fixation

        # Check for alternating pattern: [A, B, A, B, ...]
        is_oscillating = True
        for i, s in enumerate(sigs):
            expected = a_sig if i % 2 == 0 else b_sig
            if s != expected:
                is_oscillating = False
                break

        if is_oscillating:
            tools = f"{window[0].tool} <-> {window[1].tool}"
            directive = (
                f"BREAK: Alternating 2-state oscillation cycle detected "
                f"({tools}) across {needed_length} steps. Reconcile conflicting "
                f"objectives rather than toggling state."
            )
            self._emit_alert(
                alert_type="loop_cycle_detected",
                detail={
                    "pattern": "OSCILLATION_CYCLE",
                    "tool": tools,
                    "count": self.max_oscillation_cycles,
                    "threshold": self.max_oscillation_cycles,
                    "signature": f"osc_{a_sig[:8]}_{b_sig[:8]}",
                    "sequence": [a.tool for a in window],
                    "remedial_directive": directive,
                },
            )

    def _check_choreography_cycle(self) -> None:
        """Detect 3-step action choreography cycle: A -> B -> C -> A -> B -> C."""
        needed_length = self.max_choreography_cycles * 3
        if len(self._action_history) < needed_length:
            return

        window = self._action_history[-needed_length:]
        sigs = [a.sig for a in window]
        a_sig, b_sig, c_sig = sigs[0], sigs[1], sigs[2]

        if len({a_sig, b_sig, c_sig}) < 3:
            return  # Handled by fixation or 2-cycle oscillation

        is_choreography = True
        pattern_seq = [a_sig, b_sig, c_sig]
        for i, s in enumerate(sigs):
            expected = pattern_seq[i % 3]
            if s != expected:
                is_choreography = False
                break

        if is_choreography:
            tools = f"{window[0].tool} -> {window[1].tool} -> {window[2].tool}"
            directive = (
                f"BREAK: Repetitive 3-step execution choreography detected "
                f"({tools}) across {needed_length} steps. Break execution sequence."
            )
            self._emit_alert(
                alert_type="loop_cycle_detected",
                detail={
                    "pattern": "CHOREOGRAPHY_CYCLE",
                    "tool": tools,
                    "count": self.max_choreography_cycles,
                    "threshold": self.max_choreography_cycles,
                    "signature": f"choreo_{a_sig[:6]}_{b_sig[:6]}_{c_sig[:6]}",
                    "sequence": [a.tool for a in window],
                    "remedial_directive": directive,
                },
            )

    def _check_watchdog_model(self) -> None:
        """Tier 2: Optional model watchdog for semantic stagnation."""
        if not callable(self.watchdog_fn):
            return

        trajectory_summary = [
            {
                "turn": a.turn,
                "tool": a.tool,
                "args": a.args,
                "has_error": a.has_error,
            }
            for a in self._action_history
        ]
        try:
            res = self.watchdog_fn(trajectory_summary)
            if isinstance(res, dict) and res.get("loop_detected"):
                directive = str(
                    res.get("remedial_directive")
                    or res.get("reason")
                    or "Watchdog model detected semantic execution stagnation."
                )
                self._emit_alert(
                    alert_type="loop_cycle_detected",
                    detail={
                        "pattern": "SEMANTIC_STAGNATION",
                        "tool": (
                            self._action_history[-1].tool if self._action_history else "unknown"
                        ),
                        "count": 1,
                        "threshold": 1,
                        "signature": f"watchdog_{self._current_turn}",
                        "remedial_directive": directive,
                    },
                )
        except Exception:
            pass  # Watchdog failure must never break the main loop

    def _emit_alert(self, alert_type: str, detail: dict[str, Any]) -> None:
        """Deduplicate, enrich with cryptographic spine hashes, and emit alert."""
        sig = str(detail.get("signature") or "")
        count = int(detail.get("count") or 0)
        pattern = str(detail.get("pattern") or "")
        dedup_key = f"{alert_type}:{pattern}:{sig}:{count}"
        if dedup_key in self._tripped_dedup_keys:
            return
        self._tripped_dedup_keys.add(dedup_key)

        alert = {
            "type": alert_type,
            **detail,
            "observer_id": self.observer_id,
            "window_size": self.window_size,
        }

        # Cryptographic spine hash capture for non-repudiable audit proofs
        spine = getattr(self._session, "spine", None)
        if spine is not None and hasattr(spine, "_last_content_hash"):
            rec_hash = spine._last_content_hash
            entry_hash = rec_hash
            if self._action_history:
                entry_hash = self._action_history[0].spine_hash or rec_hash
            if entry_hash:
                alert.setdefault("cycle_entry_hash", entry_hash)
            if rec_hash:
                alert.setdefault("cycle_recurrence_hash", rec_hash)

        # FinOps burn velocity guard check
        if self.burn_velocity_guard or self.max_cycle_token_waste > 0:
            alert["churn_tokens_estimate"] = self._cycle_token_accumulator
            if (
                self.max_cycle_token_waste > 0
                and self._cycle_token_accumulator >= self.max_cycle_token_waste
            ):
                alert["burn_rate_spike"] = True

        self._alerts.append(alert)

        # Enforce action if configured
        self._apply_configured_action(alert)

        if spine is not None:
            spine.append(
                "observer.alert",
                alert,
                agent_ids=self._session.agent_ids_trailer(),
            )

    def _apply_configured_action(self, alert: dict[str, Any]) -> None:
        """Enforce configured remedial action (pause session or trip egress circuit breaker)."""
        if self.action in ("pause", "pause_session"):
            pause_rule = {
                "type": "break_pause",
                "request_id": f"break_pause_{uuid.uuid4().hex[:10]}",
                "source": "break_observer",
                "pattern": alert.get("pattern"),
                "remedial_directive": alert.get("remedial_directive"),
            }
            if hasattr(self._session, "rules"):
                self._session.rules.append(pause_rule)
            if hasattr(self._session, "state"):
                self._session.state["_break_tripped"] = True
                self._session.state["_break_pause_rule"] = pause_rule

        if self.action in ("circuit_break", "trip"):
            circuit_rule = {
                "type": "circuit_break",
                "tool": alert.get("tool"),
                "signature": alert.get("signature"),
                "remedial_directive": alert.get("remedial_directive"),
            }
            if hasattr(self._session, "rules"):
                self._session.rules.append(circuit_rule)
            if hasattr(self._session, "state"):
                self._session.state["_break_tripped"] = True

    def summary(self) -> dict[str, Any]:
        return {
            "intent_signatures": dict(self._intent_signatures),
            "alerts_emitted": len(self._alerts),
            "cycles_detected": sum(1 for a in self._alerts if a.get("pattern")),
            "patterns": sorted(list({a.get("pattern") for a in self._alerts if a.get("pattern")})),
            "tripped": len(self._alerts) > 0,
        }

    @staticmethod
    def _normalize_args(args: Any) -> str:
        if not isinstance(args, dict):
            return str(args)
        return json.dumps(args, sort_keys=True, default=str)


def create_break_observer(session: Session, entry: dict[str, Any]) -> BreakObserver:
    obs_id = str(entry.get("id") or "break")
    config = entry.get("config") if isinstance(entry.get("config"), dict) else {}
    return BreakObserver(obs_id, session, config)
