"""Sequencer runner — linear prescriptive steps with gates and retries."""

from __future__ import annotations

import time
from typing import Any, Protocol

from aura.core.constraints import ApprovalRequired
from aura.core.session import Session
from aura.sequencer.spec import load_steps
from aura.sequencer.step import SequencerStep


class StepBackend(Protocol):
    def run_skill(self, step: SequencerStep) -> Any: ...

    def run_op(self, step: SequencerStep) -> Any: ...

    def run_prompt(self, step: SequencerStep) -> Any: ...

    def run_gate(self, step: SequencerStep) -> Any: ...


class DefaultStepBackend:
    """Emit-only backend when no host is wired."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def run_skill(self, step: SequencerStep) -> Any:
        return {"status": "declared", "ref": step.ref, "type": "skill"}

    def run_op(self, step: SequencerStep) -> Any:
        raw_op = step.ref or step.config.get("op") or "noop"
        op: str = str(raw_op).strip()
        clean_op: str = op.lower()
        if clean_op == "echo":
            self.session.emit(
                "sequencer.op",
                {"op": op, "config": step.config},
                step_id=step.id,
            )
            return dict(step.config)

        if clean_op in ("middleware.pii_mask", "pii_mask"):
            from aura.core.constraints import ConstraintViolation
            from aura.sequencer.pii_mask import PiiMasker

            config = dict(step.config)
            source_step = config.get("source_step")
            seq_state = self.session.state.get("sequencer") or {}
            raw_data = None
            if source_step:
                if source_step in seq_state:
                    raw_data = seq_state[source_step]
                elif source_step in self.session.state.get("steps", {}):
                    raw_data = self.session.state["steps"][source_step].get("result")
            elif "data" in config:
                raw_data = config["data"]
            elif "args" in config:
                raw_data = config["args"]
            elif seq_state:
                last_step_id = list(seq_state.keys())[-1]
                raw_data = seq_state[last_step_id]

            masker = PiiMasker()
            res = masker.mask(raw_data, config, session_state=self.session.state)

            self.session.emit(
                "sequencer.op",
                {"op": op, "config": step.config},
                step_id=step.id,
            )
            self.session.emit(
                "middleware.applied",
                {
                    "op": "middleware.pii_mask",
                    "middleware": "middleware.pii_mask",
                    "step_id": step.id,
                    "scope": "step_op",
                    "direction": "step",
                    "strategy": config.get("strategy", "redact"),
                    "entities_detected": res.entities_detected,
                    "total_redactions": res.total_redactions,
                    "redacted_count": res.total_redactions,
                    "fields_modified": res.fields_modified,
                },
                step_id=step.id,
            )
            if config.get("strict") and res.total_redactions > 0:
                raise ConstraintViolation(f"PII detected by {op} ({res.total_redactions} entities)")
            return res.data

        self.session.emit(
            "sequencer.op",
            {"op": op, "config": step.config},
            step_id=step.id,
        )
        return {"op": op, "status": "ok"}

    def run_prompt(self, step: SequencerStep) -> Any:
        prompt = step.ref or step.config.get("prompt", "")
        self.session.emit(
            "sequencer.prompt",
            {"prompt": prompt, "config": step.config},
            step_id=step.id,
        )
        return {"prompt": prompt, "status": "declared"}

    def run_gate(self, step: SequencerStep) -> Any:
        gate = step.ref or step.config.get("gate", "human_confirm")
        self.session.emit(
            "sequencer.gate",
            {"gate": gate, "config": step.config},
            step_id=step.id,
        )
        return {"gate": gate, "status": "ok"}


class HostStepBackend(DefaultStepBackend):
    """Route skill steps through a Skillware/mock host."""

    def __init__(self, session: Session, host: Any) -> None:
        super().__init__(session)
        self.host = host

    def run_skill(self, step: SequencerStep) -> Any:
        skill_id = step.ref or step.config.get("skill_id", "")
        tool = step.config.get("tool") or step.config.get("action", "execute")
        args = dict(step.config.get("args") or {})
        return self.host.execute(skill_id, tool, args, step_id=step.id)


class SequencerRunner:
    """Execute declared step order; emit per-step telemetry on the audit spine."""

    def __init__(
        self,
        session: Any = None,
        backend: StepBackend | None = None,
        spec: dict[str, Any] | None = None,
        *,
        steps: list[SequencerStep] | None = None,
        middleware_stack: Any | None = None,
    ) -> None:
        real_session = getattr(session, "_session", session)
        self.session = real_session
        self.backend = backend or (DefaultStepBackend(real_session) if real_session else None)
        default_spec = (
            getattr(real_session, "sequencer_spec", None)
            or getattr(getattr(real_session, "profile", None), "sequencer", None)
            or {}
        )
        self.spec = dict(spec or default_spec)
        if steps is not None:
            self.spec["steps"] = steps
        self._custom_middleware_stack = middleware_stack

    def run(
        self,
        spec_or_session: Any = None,
        spec: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        target_spec = spec
        if hasattr(spec_or_session, "_session"):
            self.session = spec_or_session._session
            if self.backend is None:
                self.backend = DefaultStepBackend(self.session)
        elif isinstance(spec_or_session, Session):
            self.session = spec_or_session
            if self.backend is None:
                self.backend = DefaultStepBackend(self.session)
        elif isinstance(spec_or_session, dict):
            target_spec = spec_or_session

        merged_spec = target_spec or self.spec
        steps = load_steps(merged_spec)
        if not steps:
            return {"completed": [], "steps": 0, "success": True}

        from aura.sequencer.middleware import MiddlewarePolicy, MiddlewareStack

        middleware_policy = (
            MiddlewarePolicy.from_manifest(merged_spec)
            or MiddlewarePolicy.from_manifest(getattr(self.session, "manifest", None) or {})
            or (
                MiddlewarePolicy.from_manifest(self.session.profile.sequencer)
                if self.session
                and getattr(self.session, "profile", None)
                and getattr(self.session.profile, "sequencer", None)
                else None
            )
        )
        middleware_stack = self._custom_middleware_stack or (
            MiddlewareStack(middleware_policy) if middleware_policy else None
        )

        completed: list[str] = []
        try:
            for step in steps:
                self._validate_dependencies(step, completed)
                skip_reason = self._skip_reason(step)
                if skip_reason:
                    result = self._skip_step(step, skip_reason)
                else:
                    result = self._run_step(step, middleware_stack=middleware_stack)
                self.session.state.setdefault("sequencer", {})[step.id] = result
                self.session.state.setdefault("steps", {})[step.id] = {"result": result}
                completed.append(step.id)

            self.session.emit("sequencer.complete", {"steps": completed})
            return {"completed": completed, "steps": len(completed), "success": True}
        except ApprovalRequired:
            raise
        except Exception as exc:
            return {
                "completed": completed,
                "steps": len(completed),
                "success": False,
                "error": str(exc),
            }

    def _skip_reason(self, step: SequencerStep) -> str | None:
        when = step.when
        if not when:
            return None
        prior = when.get("prior_step")
        field = when.get("field")
        if not prior or not field:
            return None
        state = self.session.state.get("sequencer") or {}
        prior_result = state.get(prior)
        if not isinstance(prior_result, dict):
            return f"prior step {prior!r} has no result"
        actual = prior_result.get(field)
        if "equals" in when and actual != when.get("equals"):
            return f"{field}={actual!r} expected {when.get('equals')!r}"
        if when.get("truthy") and not actual:
            return f"{field} is falsy"
        return None

    def _skip_step(self, step: SequencerStep, reason: str) -> dict[str, Any]:
        self.session.emit(
            "sequencer.step.start",
            {"type": step.step_type, "ref": step.ref, "attempt": 0, "skipped": True},
            step_id=step.id,
        )
        payload = {"status": "skipped", "reason": reason}
        self.session.emit("sequencer.step.skipped", payload, step_id=step.id)
        self.session.emit(
            "sequencer.step.end",
            {"status": "skipped", "reason": reason},
            step_id=step.id,
        )
        return payload

    def _validate_dependencies(self, step: SequencerStep, completed: list[str]) -> None:
        missing = [d for d in step.depends_on if d not in completed]
        if missing:
            raise RuntimeError(f"Step {step.id} depends on incomplete steps: {missing}")

    def _run_step(self, step: SequencerStep, *, middleware_stack: Any | None = None) -> Any:
        for gate in step.gates:
            self._apply_gate(gate, step)

        if middleware_stack is not None and step.config:
            step.config = middleware_stack.run_inbound(step.config, session=self.session, step=step)

        max_attempts = int(step.retry.get("max", 0)) + 1
        backoff = step.retry.get("backoff", "none")
        last_error: Exception | None = None

        for attempt in range(max_attempts):
            self.session.emit(
                "sequencer.step.start",
                {"type": step.step_type, "ref": step.ref, "attempt": attempt + 1},
                step_id=step.id,
            )
            try:
                result = self._execute_step(step)
                if middleware_stack is not None:
                    result = middleware_stack.run_outbound(result, session=self.session, step=step)
                self.session.emit(
                    "sequencer.step.end",
                    {"status": "ok", "attempt": attempt + 1},
                    step_id=step.id,
                )
                return result
            except ApprovalRequired:
                raise
            except Exception as exc:
                last_error = exc
                self.session.emit(
                    "sequencer.step.end",
                    {"status": "error", "error": str(exc), "attempt": attempt + 1},
                    step_id=step.id,
                )
                if attempt + 1 >= max_attempts:
                    break
                self._sleep_backoff(backoff, attempt)

        if last_error:
            raise last_error
        return None

    def _execute_step(self, step: SequencerStep) -> Any:
        if step.step_type == "skill":
            return self.backend.run_skill(step)
        if step.step_type == "op":
            return self.backend.run_op(step)
        if step.step_type == "prompt":
            return self.backend.run_prompt(step)
        if step.step_type == "gate":
            return self.backend.run_gate(step)
        if step.step_type == "subflow":
            nested = step.config.get("steps") or []
            nested_runner = SequencerRunner(self.session, self.backend, {"steps": nested})
            return nested_runner.run()
        raise ValueError(f"Unknown step type: {step.step_type}")

    def _apply_gate(self, gate: str, step: SequencerStep) -> None:
        if gate == "human_confirm":
            request_id = f"sequencer.gate.{step.id}"
            if request_id in self.session._approved:
                return
            self.session.require_approval(
                request_id,
                f"Human confirmation required before step: {step.id}",
                {"type": "human_confirm", "step_id": step.id},
                step_id=step.id,
            )
        elif gate == "constitution":
            self.session.emit(
                "sequencer.gate.constitution",
                {"step_id": step.id},
                step_id=step.id,
            )
        elif gate == "budget":
            self.session.emit(
                "sequencer.gate.budget",
                {"step_id": step.id, "config": step.config},
                step_id=step.id,
            )

    @staticmethod
    def _sleep_backoff(kind: str, attempt: int) -> None:
        if kind == "linear":
            time.sleep(0.05 * (attempt + 1))
        elif kind == "exponential":
            time.sleep(0.05 * (2**attempt))
