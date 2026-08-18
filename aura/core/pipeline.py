"""Cross-cutting hook pipeline — pre/post interception on loop ticks."""

from enum import Enum
from typing import Any, Callable


class HookStage(str, Enum):
    PRE_MANIFEST = "pre_manifest"
    POST_BIND = "post_bind"
    PRE_TURN = "pre_turn"
    PRE_STEP = "pre_step"
    PRE_TOOL = "pre_tool"
    POST_TOOL = "post_tool"
    POST_STEP = "post_step"
    ON_DRIFT = "on_drift"
    ON_ERROR = "on_error"
    TURN_END = "turn_end"
    POST_SESSION = "post_session"


Handler = Callable[[dict[str, Any]], dict[str, Any]]


class HookPipeline:
    """Ordered handlers per stage — extensible by ops and type plugins."""

    def __init__(self) -> None:
        self._handlers: dict[HookStage, list[Handler]] = {s: [] for s in HookStage}

    def register(self, stage: HookStage, handler: Handler) -> None:
        self._handlers[stage].append(handler)

    def run(self, stage: HookStage, ctx: dict[str, Any]) -> dict[str, Any]:
        for handler in self._handlers[stage]:
            ctx = handler(ctx)
        return ctx
