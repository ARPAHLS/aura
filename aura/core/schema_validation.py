"""JSON Schema validation for tool.call / tool.result at egress (#78)."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from aura.agents.profile import AgentProfile

STATE_SCHEMA_REFS = "_schema_refs"


def parse_schema_refs(variables: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """
    Parse ``variables.schema_refs`` into a ref → spec map.

    Each entry may include ``tool``, ``skill_id``, ``on`` (call|result|both),
    and inline ``schema`` (JSON Schema object).
    """
    if not isinstance(variables, dict):
        return {}
    raw = variables.get("schema_refs")
    if not isinstance(raw, dict):
        return {}
    refs: dict[str, dict[str, Any]] = {}
    for name, spec in raw.items():
        if not isinstance(spec, dict):
            continue
        schema = spec.get("schema")
        if not isinstance(schema, dict):
            continue
        refs[str(name)] = dict(spec)
    return refs


def rules_from_schema_refs(
    refs: dict[str, dict[str, Any]],
    *,
    source: str = "profile",
    level: str | None = None,
) -> list[dict[str, Any]]:
    """Build ``schema_check`` rules from named schema refs."""
    rules: list[dict[str, Any]] = []
    for ref_name, spec in refs.items():
        rule: dict[str, Any] = {
            "type": "schema_check",
            "ref": ref_name,
            "schema": spec["schema"],
            "source": source,
        }
        if spec.get("tool"):
            rule["tool"] = spec["tool"]
        if spec.get("skill_id"):
            rule["skill_id"] = spec["skill_id"]
        on = spec.get("on") or spec.get("phase") or "call"
        rule["on"] = str(on).lower()
        if level:
            rule["level"] = level
        rules.append(rule)
    return rules


def schema_enforcement_enabled(profile: AgentProfile) -> bool:
    """Whether spectrum auto-wires schema refs at high/full bind."""
    from aura.core.spectrum_enforcement import effective_spectrum

    spectrum = profile.spectrum or {}
    if spectrum.get("schema_enforcement") is False:
        return False
    level = effective_spectrum(profile).level.lower()
    return level in {"high", "full"}


def merge_schema_rules(
    profile: AgentProfile,
    merged_rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Append auto-generated schema rules when spectrum high/full and refs exist.

    Explicit ``schema_check`` entries in ``profile.rules`` are left untouched.
    Mid-only profiles are not auto-wired unless rules are explicit.
    """
    refs = parse_schema_refs(profile.variables)
    if not refs or not schema_enforcement_enabled(profile):
        return merged_rules
    from aura.core.spectrum_enforcement import effective_spectrum

    level = effective_spectrum(profile).level.lower()
    auto = rules_from_schema_refs(refs, source="spectrum", level=level)
    if not auto:
        return merged_rules
    return list(merged_rules) + auto


def attach_schema_state(session: Any) -> None:
    """Store parsed schema refs on session state for ``ref`` resolution."""
    session.state[STATE_SCHEMA_REFS] = parse_schema_refs(session.profile.variables)


def resolve_schema(rule: dict[str, Any], session_state: dict[str, Any]) -> dict[str, Any] | None:
    """Inline ``schema`` on the rule, or lookup ``ref`` in session state."""
    schema = rule.get("schema")
    if isinstance(schema, dict):
        return schema
    ref_name = rule.get("ref")
    if not ref_name:
        return None
    refs = session_state.get(STATE_SCHEMA_REFS) or {}
    spec = refs.get(str(ref_name))
    if not isinstance(spec, dict):
        return None
    inner = spec.get("schema")
    return inner if isinstance(inner, dict) else None


def validate_payload(schema: dict[str, Any], data: Any) -> list[str]:
    """Validate data against JSON Schema; return human-readable error strings."""
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema package required for schema_check rules (pip install jsonschema)"]

    validator = jsonschema.Draft202012Validator(schema)
    errors: list[str] = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in err.path) or "(root)"
        errors.append(f"{path}: {err.message}")
    return errors


def payload_subject(payload: dict[str, Any], event_kind: str) -> Any:
    """Extract the value to validate from a tool event payload."""
    if event_kind == "tool.call":
        args = payload.get("args")
        return args if isinstance(args, dict) else {}
    if event_kind == "tool.result":
        return payload.get("result")
    return None


def rule_applies_to_event(rule: dict[str, Any], event_kind: str, payload: dict[str, Any]) -> bool:
    """Whether this schema_check rule applies to the current event."""
    on = str(rule.get("on") or rule.get("phase") or "call").lower()
    if event_kind == "tool.call" and on not in {"call", "both"}:
        return False
    if event_kind == "tool.result" and on not in {"result", "both"}:
        return False
    if event_kind not in {"tool.call", "tool.result"}:
        return False

    tool = rule.get("tool")
    if tool:
        payload_tool = payload.get("tool") or payload.get("name") or payload.get("tool_name")
        skill_id = payload.get("skill_id")
        if str(tool) not in {str(payload_tool), str(skill_id)}:
            return False

    skill_id = rule.get("skill_id")
    if skill_id and str(payload.get("skill_id")) != str(skill_id):
        return False

    return True
