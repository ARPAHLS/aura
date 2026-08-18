"""Type plugin registry — extensible bindings, no hardcoded providers."""

from typing import Any, Protocol


class TypePlugin(Protocol):
    type_id: str
    version: int
    role: str

    def validate(self, config: dict[str, Any]) -> None: ...
    def bind(self, session: Any, config: dict[str, Any]) -> dict[str, Any]: ...


class TypeRegistry:
    """Register and resolve Aura type plugins by type_id."""

    def __init__(self) -> None:
        self._plugins: dict[str, TypePlugin] = {}

    def register(self, plugin: TypePlugin) -> None:
        self._plugins[plugin.type_id] = plugin

    def get(self, type_id: str) -> TypePlugin | None:
        return self._plugins.get(type_id)

    def list_types(self, role: str | None = None) -> list[str]:
        if role is None:
            return list(self._plugins)
        return [p.type_id for p in self._plugins.values() if p.role == role]
