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
        op = step.ref or step.config.get("op", "noop")
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
        session: Session,
        backend: StepBackend | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.session = session
        self.backend = backend or DefaultStepBackend(session)
        self.spec = spec or {}

    def run(self, spec: dict[str, Any] | None = None) -> dict[str, Any]:
        steps = load_steps(spec or self.spec)
        if not steps:
            return {"completed": [], "steps": 0}

        completed: list[str] = []
        for step in steps:
            self._validate_dependencies(step, completed)
            result = self._run_step(step)
            self.session.state.setdefault("sequencer", {})[step.id] = result
            completed.append(step.id)

        self.session.emit("sequencer.complete", {"steps": completed})
        return {"completed": completed, "steps": len(completed)}

    def _validate_dependencies(self, step: SequencerStep, completed: list[str]) -> None:
        missing = [d for d in step.depends_on if d not in completed]
        if missing:
            raise RuntimeError(f"Step {step.id} depends on incomplete steps: {missing}")

    def _run_step(self, step: SequencerStep) -> Any:
        for gate in step.gates:
            self._apply_gate(gate, step)

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
