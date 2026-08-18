# Type Plugin Contract

Implementors follow this interface.

## Registration

```python
class AuraTypePlugin(Protocol):
    type_id: str          # e.g. "arpa.skills.bundle"
    version: int
    role: str             # brain | drive | guardrails | identity | skills | memory | soma | environment | auth | ...

    def register(self, registry: TypeRegistry) -> None: ...
    def validate(self, config: dict) -> None: ...       # raises on invalid manifest fragment
    def bind(self, session: Session, config: dict) -> TypeCapabilities: ...
    def hooks(self) -> list[HookRegistration]: ...
    def conformance_rules(self) -> list[ConformanceRule]: ...
    def teardown(self, session: Session) -> None: ...
```

## Capabilities Object

Returned from `bind()` — merged by core to derive effective Aura operations:

```python
@dataclass
class TypeCapabilities:
    emits: list[str]              # event kinds this type produces
    accepts_ops: list[str]        # ops that may run when this type is bound
    requires_ops: list[str]       # ops core must enable (e.g. audit.log)
    conformance: list[str]        # rule ids owned by this type
```

## Rules

1. **No provider switches in core** — all vendor logic lives in type plugins.
2. **Version type IDs** — breaking config → new plugin version.
3. **Every bind/teardown** emits `type.bound` / `type.unbound` on audit spine.
4. **Community types** use `custom.*` namespace; ARPA types use `arpa.*`.

## Built-in Type Roles (extensible)

| Role | Example type IDs |
|---|---|
| brain | `arpa.brain.gemini`, `arpa.brain.ollama`, `arpa.brain.claude` |
| drive | `arpa.drive.goal`, `arpa.drive.cron` |
| guardrails | `arpa.guardrails.ruleset`, `arpa.guardrails.evm`, `arpa.guardrails.whitelist` |
| identity | `arpa.identity.live_id`, `arpa.identity.ephemeral` |
| auth | `arpa.auth.live_id_cli`, `api_key` |
| skills | `arpa.skills.bundle`, `mcp.tools`, `langchain.tools` |
| memory | `arpa.memory.mnemolink`, `mem0` |
| soma | `arpa.soma.process`, `arpa.soma.vm`, `arpa.soma.device` |
| runtime | `arpa.runtime.python`, `arpa.runtime.langgraph`, `arpa.runtime.dsh` |
| environment | `arpa.env.rooms` |

New roles require no core change — only documentation and capability registry entry.

See [architecture.md](../docs/architecture.md) · [capability.registry.json](capability.registry.json).
