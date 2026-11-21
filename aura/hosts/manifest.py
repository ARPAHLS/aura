"""Skill manifest -> session constraint rules, Manifest v2 validation, and taxonomy (host bind)."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
import re
from typing import Any

VALID_SHAPES = ("atomic", "workflow", "middleware", "stream")
VALID_TIERS = ("core", "cloud", "enterprise")
VALID_TARGETS = ("software", "hardware", "bioware")
PHYSICAL_TARGETS = frozenset({"hardware", "bioware"})

DEFAULT_SHAPE = "atomic"
DEFAULT_TIER = "core"
DEFAULT_TARGET = ["software"]
DEFAULT_TAGS: list[str] = []

TAG_PATTERN = r"^[a-z0-9_-]+$"
TAG_REGEX = re.compile(TAG_PATTERN)

_FULL_MANIFEST_HINT_KEYS = frozenset(
    {"name", "version", "description", "parameters", "outputs", "issuer"}
)


class ManifestValidationError(ValueError):
    """Raised when a bound skill manifest fails strict Manifest v2 validation."""

    def __init__(self, skill_id: str, errors: list[str]) -> None:
        self.skill_id = skill_id
        self.errors = list(errors)
        joined = "; ".join(self.errors)
        super().__init__(f"Invalid manifest for skill '{skill_id}': {joined}")


def normalize_skill_manifest(manifest: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a copy of manifest with Skillware Manifest v2 taxonomy defaults applied."""
    if not manifest:
        return {}
    try:
        from skillware.core.manifest_schema import normalize_manifest_v2

        return dict(normalize_manifest_v2(manifest))
    except ImportError:
        pass

    normalized = dict(manifest)

    raw_shape = normalized.get("shape")
    if raw_shape is not None and str(raw_shape).strip().lower() in VALID_SHAPES:
        normalized["shape"] = str(raw_shape).strip().lower()
    else:
        normalized["shape"] = DEFAULT_SHAPE

    raw_tier = normalized.get("tier")
    if raw_tier is not None and str(raw_tier).strip().lower() in VALID_TIERS:
        normalized["tier"] = str(raw_tier).strip().lower()
    else:
        normalized["tier"] = DEFAULT_TIER

    raw_target = normalized.get("target")
    if isinstance(raw_target, list) and raw_target:
        deduped_targets: list[str] = []
        for item in raw_target:
            clean = str(item).strip().lower()
            if clean in VALID_TARGETS and clean not in deduped_targets:
                deduped_targets.append(clean)
        normalized["target"] = deduped_targets or list(DEFAULT_TARGET)
    else:
        normalized["target"] = list(DEFAULT_TARGET)

    raw_tags = normalized.get("tags")
    if isinstance(raw_tags, list):
        deduped_tags: list[str] = []
        for item in raw_tags:
            if item:
                clean = str(item).strip().lower()
                if clean not in deduped_tags:
                    deduped_tags.append(clean)
        normalized["tags"] = deduped_tags[:10]
    else:
        normalized["tags"] = list(DEFAULT_TAGS)

    return normalized


def extract_manifest_taxonomy(manifest: Mapping[str, Any] | None) -> dict[str, Any]:
    """Extract normalized Manifest v2 taxonomy metadata (shape, tier, target, tags)."""
    norm = normalize_skill_manifest(manifest)
    return {
        "shape": norm.get("shape", DEFAULT_SHAPE),
        "tier": norm.get("tier", DEFAULT_TIER),
        "target": list(norm.get("target") or DEFAULT_TARGET),
        "tags": list(norm.get("tags") or DEFAULT_TAGS),
    }


def has_physical_target(manifest: Mapping[str, Any] | None) -> bool:
    """Return True when manifest declares hardware or bioware execution substrate."""
    if not isinstance(manifest, Mapping):
        return False
    raw = manifest.get("target")
    if raw is None:
        return False
    targets = raw if isinstance(raw, list) else [raw]
    return any(str(t).strip().lower() in PHYSICAL_TARGETS for t in targets)


def requires_physical_approval_gate(
    manifest: Mapping[str, Any] | None,
    *,
    allow_hardware_execution: bool = False,
    hardware_gate: str = "auto",
    spectrum_level: str | None = None,
) -> bool:
    """
    Decide whether a physical-target skill requires an auto-injected ``confirm_before`` gate.

    - ``allow_hardware_execution=True`` or ``hardware_gate="off"``: never auto-gate.
    - ``hardware_gate="confirm"``: gate any skill declaring ``hardware`` or ``bioware``.
    - ``hardware_gate="auto"`` (default): gate exclusively physical skills (no ``software``
      target) or any physical skill under ``high``/``full`` spectrum, while allowing
      dual-domain ``[software, hardware]`` math/data utilities (e.g. ``unit_normalizer``)
      at default/low/mid spectrum without blocking.
    """
    mode = str(hardware_gate or "auto").strip().lower()
    if allow_hardware_execution or mode == "off":
        return False
    if not has_physical_target(manifest):
        return False
    if mode == "confirm":
        return True
    assert manifest is not None
    raw = manifest.get("target")
    targets = raw if isinstance(raw, list) else [raw]
    clean = {str(t).strip().lower() for t in targets if t}
    if "software" not in clean:
        return True
    if spectrum_level and str(spectrum_level).strip().lower() in {"high", "full"}:
        return True
    return False


def _validate_taxonomy_fields(data: Mapping[str, Any], prefix: str) -> list[str]:
    errors: list[str] = []
    shape = data.get("shape")
    if shape is not None:
        if str(shape).strip().lower() not in VALID_SHAPES:
            errors.append(
                f"{prefix}Invalid shape '{shape}'. Must be one of: {', '.join(VALID_SHAPES)}."
            )

    tier = data.get("tier")
    if tier is not None:
        if str(tier).strip().lower() not in VALID_TIERS:
            errors.append(
                f"{prefix}Invalid tier '{tier}'. Must be one of: {', '.join(VALID_TIERS)}."
            )

    target = data.get("target")
    if target is not None:
        if not isinstance(target, list) or not target:
            errors.append(
                f"{prefix}Target must be a non-empty list of substrates: "
                f"{', '.join(VALID_TARGETS)}."
            )
        else:
            for item in target:
                if str(item).strip().lower() not in VALID_TARGETS:
                    errors.append(
                        f"{prefix}Invalid target substrate '{item}'. "
                        f"Must be one of: {', '.join(VALID_TARGETS)}."
                    )

    tags = data.get("tags")
    if tags is not None:
        if not isinstance(tags, list):
            errors.append(f"{prefix}Tags must be a list of lowercase string keywords.")
        else:
            if len(tags) > 10:
                errors.append(f"{prefix}Tags list cannot exceed 10 keywords (found {len(tags)}).")
            if len(tags) != len(set(tags)):
                errors.append(f"{prefix}Tags list contains duplicate keywords.")
            for tag in tags:
                if not isinstance(tag, str) or not TAG_REGEX.match(tag.strip()):
                    errors.append(f"{prefix}Invalid tag '{tag}'. Tags must match '{TAG_PATTERN}'.")
    return errors


def validate_skill_manifest(
    manifest: Mapping[str, Any],
    *,
    skill_id: str | None = None,
    strict_required: bool = False,
) -> list[str]:
    """
    Validate a skill manifest against Skillware Manifest v2 rules.

    Lightweight AURA guardrail-only mock manifests (without name/version/description/parameters)
    still have any present taxonomy fields checked without failing on omitted Skillware metadata,
    unless ``strict_required=True``.
    """
    prefix = f"Skill '{skill_id}': " if skill_id else ""
    if not isinstance(manifest, Mapping):
        return [f"{prefix}Manifest must be a mapping/dict, got {type(manifest).__name__}."]

    looks_like_full_manifest = strict_required or bool(
        _FULL_MANIFEST_HINT_KEYS.intersection(manifest.keys())
    )
    if not looks_like_full_manifest:
        return sorted(set(_validate_taxonomy_fields(manifest, prefix)))

    try:
        from skillware.core.manifest_schema import validate_manifest_schema

        return list(validate_manifest_schema(manifest, skill_id=skill_id))
    except ImportError:
        pass

    errors = _validate_taxonomy_fields(manifest, prefix)
    for req in ("name", "version", "description"):
        val = manifest.get(req)
        if not isinstance(val, str) or not val.strip():
            errors.append(f"{prefix}Missing or invalid required field '{req}'.")
    return sorted(set(errors))


def manifest_to_rules(
    manifest: dict[str, Any],
    *,
    skill_id: str | None = None,
    allow_hardware_execution: bool = False,
    hardware_gate: str = "auto",
    spectrum_level: str | None = None,
    auto_schema: bool = False,
) -> list[dict[str, Any]]:
    """Convert a skill manifest guardrails block and safety metadata into constraint rules."""
    if not manifest:
        return []
    rules: list[dict[str, Any]] = []
    guardrails = (
        manifest.get("guardrails") if isinstance(manifest.get("guardrails"), dict) else manifest
    )

    allow = guardrails.get("allow_tools") or guardrails.get("allow")
    if allow:
        rules.append({"type": "allow_tools", "tools": list(allow)})

    deny = guardrails.get("deny_tools") or guardrails.get("deny")
    if deny:
        rules.append({"type": "deny_tools", "tools": list(deny)})

    confirm = guardrails.get("confirm_before")
    if confirm:
        tools = confirm.get("tools") if isinstance(confirm, dict) else confirm
        if tools:
            rules.append({"type": "confirm_before", "tools": list(tools)})

    limit = guardrails.get("max_tokens_per_step") or guardrails.get("max_tokens")
    if limit is not None:
        rules.append({"type": "max_tokens_per_step", "limit": int(limit)})

    # Physical substrate safety gate: hardware/bioware skills require explicit operator approval
    # according to hardware_gate ("auto" | "confirm" | "off") and spectrum level.
    if (
        requires_physical_approval_gate(
            manifest,
            allow_hardware_execution=allow_hardware_execution,
            hardware_gate=hardware_gate,
            spectrum_level=spectrum_level,
        )
        and skill_id
    ):
        gate_tools: list[str] = [skill_id]
        manifest_name = manifest.get("name")
        if isinstance(manifest_name, str) and manifest_name and manifest_name not in gate_tools:
            gate_tools.append(manifest_name)
        rules.append(
            {
                "type": "confirm_before",
                "tools": gate_tools,
                "reason": "physical_target_safety_gate",
            }
        )

    # High/full spectrum auto-wiring: validate tool.call args against manifest parameters schema.
    if auto_schema and skill_id:
        params_schema = manifest.get("parameters")
        if isinstance(params_schema, dict) and params_schema:
            normalized_schema = dict(params_schema)
            normalized_schema.setdefault("type", "object")
            rules.append(
                {
                    "type": "schema_check",
                    "ref": f"manifest:{skill_id}",
                    "skill_id": skill_id,
                    "on": "call",
                    "schema": normalized_schema,
                    "source": "manifest",
                }
            )

    return rules


def manifest_snapshot_hash(skill_id: str, manifest: dict[str, Any]) -> str:
    blob = json.dumps({"skill_id": skill_id, "manifest": manifest}, sort_keys=True, default=str)
    return sha256(blob.encode()).hexdigest()[:16]


def merge_manifest_into_rules(
    rules: list[dict[str, Any]],
    skill_id: str,
    manifest: dict[str, Any],
    *,
    allow_hardware_execution: bool = False,
    hardware_gate: str = "auto",
    spectrum_level: str | None = None,
    auto_schema: bool = False,
) -> list[dict[str, Any]]:
    """Append manifest-derived rules; tag each with bind metadata for audit."""
    merged = list(rules)
    for rule in manifest_to_rules(
        manifest,
        skill_id=skill_id,
        allow_hardware_execution=allow_hardware_execution,
        hardware_gate=hardware_gate,
        spectrum_level=spectrum_level,
        auto_schema=auto_schema,
    ):
        tagged = dict(rule)
        tagged["_bind"] = {"skill_id": skill_id, "source": "manifest"}
        merged.append(tagged)
    return merged
