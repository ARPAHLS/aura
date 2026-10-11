"""Middleware stack — ordered operations per step or model request (#58)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aura.core.constraints import ConstraintViolation
from aura.sequencer.pii_mask import PiiMasker


@dataclass
class MiddlewarePolicy:
    scope: str = "per_step"
    order: list[dict[str, Any]] = field(default_factory=list)
    middleware: str | None = None
    config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.middleware and not self.order:
            self.order = [{"op": self.middleware, "config": self.config}]

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any]) -> "MiddlewarePolicy | None":
        raw = manifest.get("middleware")
        if not raw:
            return None
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "MiddlewarePolicy | None":
        if not isinstance(raw, dict):
            return None
        return cls(
            scope=str(raw.get("scope", "per_step")),
            order=list(raw.get("order") or []),
        )


class MiddlewareStack:
    def __init__(
        self,
        policy: MiddlewarePolicy | list[MiddlewarePolicy] | None = None,
        *,
        policies: list[MiddlewarePolicy] | None = None,
    ) -> None:
        if policies:
            combined_order: list[dict[str, Any]] = []
            scope = "per_step"
            for p in policies:
                scope = p.scope
                combined_order.extend(p.order)
            self.policy = MiddlewarePolicy(scope=scope, order=combined_order)
        elif isinstance(policy, list):
            combined_order: list[dict[str, Any]] = []
            scope = "per_step"
            for p in policy:
                scope = p.scope
                combined_order.extend(p.order)
            self.policy = MiddlewarePolicy(scope=scope, order=combined_order)
        elif isinstance(policy, MiddlewarePolicy):
            self.policy = policy
        else:
            self.policy = MiddlewarePolicy()
        self._masker = PiiMasker()

    def run_inbound(
        self,
        ctx: dict[str, Any],
        *,
        session: Any = None,
        step: Any = None,
    ) -> dict[str, Any]:
        """Apply inbound middleware transformations."""
        out = dict(ctx)
        for entry in self.policy.order:
            op = str(entry.get("op", "noop"))
            config = dict(entry.get("config") or {})
            res = self._invoke(op, out, config, direction="inbound", session=session, step=step)
            if isinstance(res, dict):
                out = res
        return out

    def run_outbound(
        self,
        result: Any,
        *,
        session: Any = None,
        step: Any = None,
    ) -> Any:
        """Apply outbound middleware transformations to step result."""
        out = result
        for entry in self.policy.order:
            op = str(entry.get("op", "noop"))
            config = dict(entry.get("config") or {})
            out = self._invoke(op, out, config, direction="outbound", session=session, step=step)
        return out

    def _invoke(
        self,
        op_id: str,
        data: Any,
        config: dict[str, Any],
        *,
        direction: str = "inbound",
        session: Any = None,
        step: Any = None,
    ) -> Any:
        clean_op = op_id.strip().lower()
        if clean_op in ("middleware.pii_mask", "pii_mask"):
            dir_cfg = str(config.get("direction", "both")).strip().lower()
            if dir_cfg not in (direction, "both"):
                return data

            session_state = getattr(session, "state", None) if session else None
            mask_result = self._masker.mask(data, config, session_state=session_state)

            if (
                mask_result.total_redactions > 0
                and session is not None
                and hasattr(session, "emit")
            ):
                step_id = getattr(step, "id", None) if step else None
                session.emit(
                    "middleware.applied",
                    {
                        "op": "middleware.pii_mask",
                        "middleware": "middleware.pii_mask",
                        "step_id": step_id,
                        "scope": self.policy.scope,
                        "direction": direction,
                        "strategy": config.get("strategy", "redact"),
                        "entities_detected": mask_result.entities_detected,
                        "total_redactions": mask_result.total_redactions,
                        "redacted_count": mask_result.total_redactions,
                        "fields_modified": mask_result.fields_modified,
                    },
                    step_id=step_id,
                )

            if config.get("strict") and mask_result.total_redactions > 0:
                raise ConstraintViolation(
                    f"PII detected by middleware.pii_mask "
                    f"({mask_result.total_redactions} entities in {direction})"
                )

            return mask_result.data

        return data
