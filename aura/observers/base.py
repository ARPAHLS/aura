"""Observer protocol — parallel subscribers to the audit trail."""

from __future__ import annotations

from typing import Any, Protocol


class Observer(Protocol):
    """Receives every audit event after append. Must not block the host."""

    observer_id: str

    def on_event(self, event: dict[str, Any]) -> None: ...


class CallableObserver:
    """Wrap a callable as an observer."""

    def __init__(self, observer_id: str, handler: Any) -> None:
        self.observer_id = observer_id
        self._handler = handler

    def on_event(self, event: dict[str, Any]) -> None:
        self._handler(event)


class ObserverRegistry:
    def __init__(self) -> None:
        self._observers: dict[str, Observer] = {}

    def register(self, observer: Observer) -> None:
        self._observers[observer.observer_id] = observer

    def unregister(self, observer_id: str) -> None:
        self._observers.pop(observer_id, None)

    def dispatch(self, event: dict[str, Any]) -> None:
        for obs in self._observers.values():
            try:
                obs.on_event(event)
            except Exception:
                continue

    def get(self, observer_id: str) -> Observer | None:
        return self._observers.get(observer_id)

    def list_ids(self) -> list[str]:
        return list(self._observers.keys())


_global_registry = ObserverRegistry()


def get_registry() -> ObserverRegistry:
    return _global_registry
