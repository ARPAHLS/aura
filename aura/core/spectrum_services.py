"""Spectrum services[] — runtime field-service activation at session open."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from aura.core.spectrum_enforcement import effective_spectrum

if TYPE_CHECKING:
    from aura.core.session import Session

# Maps spectrum.services entry → observer preset factory key (audit is spine-only).
SERVICE_PRESET: dict[str, str] = {
    "monitor": "monitor",
    "break": "break",
    "limit": "limit",
    "goal_drift": "goal_drift",
    "goal-drift": "goal_drift",
    "schedule_slo": "schedule_slo",
    "schedule-slo": "schedule_slo",
}

DEFAULT_SERVICE_CONFIG: dict[str, dict[str, Any]] = {
    "monitor": {},
    "break": {"max_identical_intents": 5},
    "limit": {
        "max_tool_calls_per_minute": 30,
        "max_tokens_per_step": 8000,
        "warn_ratio": 0.8,
    },
    "goal_drift": {},
    "schedule_slo": {},
}

# When profile.spectrum exists but ``services`` omitted — level-aware activation defaults.
LEVEL_DEFAULT_WIRE: dict[str, list[str]] = {
    "low": [],
    "mid": [],
    "high": ["monitor"],
    "full": ["monitor", "break"],
}


def profile_has_spectrum_block(profile: Any) -> bool:
    return isinstance(getattr(profile, "spectrum", None), dict)


def services_declared_in_profile(profile: Any) -> bool:
    spec = profile.spectrum
    return isinstance(spec, dict) and "services" in spec


def resolve_services_to_wire(profile: Any) -> list[str]:
    """
    Services that should attach runtime modules for this session.

    Returns empty when profile has no explicit ``spectrum`` block (backward compatible).
    ``audit`` is always implicit on the spine and never returned here.
    """
    if not profile_has_spectrum_block(profile):
        return []

    spectrum = effective_spectrum(profile)
    if services_declared_in_profile(profile):
        raw = profile.spectrum.get("services")
        names = [str(s).strip().lower() for s in (raw or []) if str(s).strip()]
    else:
        names = list(LEVEL_DEFAULT_WIRE.get(spectrum.level.lower(), []))

    wired: list[str] = []
    for name in names:
        if name == "audit":
            continue
        if name not in wired:
            wired.append(name)
    return wired


def service_config(profile: Any, service: str) -> dict[str, Any]:
    spec = profile.spectrum if isinstance(profile.spectrum, dict) else {}
    block = spec.get("service_config")
    overrides: dict[str, Any] = {}
    if isinstance(block, dict):
        raw = block.get(service)
        if isinstance(raw, dict):
            overrides = dict(raw)
    defaults = dict(DEFAULT_SERVICE_CONFIG.get(service, {}))
    defaults.update(overrides)
    return defaults


def strict_unknown_services(profile: Any) -> bool:
    spec = profile.spectrum if isinstance(profile.spectrum, dict) else {}
    return bool(spec.get("strict_services"))


def observer_preset_names(profile: Any) -> set[str]:
    names: set[str] = set()
    for entry in profile.observers or []:
        if isinstance(entry, dict) and entry.get("preset"):
            names.add(str(entry["preset"]).lower())
    return names


def build_service_observer_entry(profile: Any, service: str) -> dict[str, Any]:
    preset = SERVICE_PRESET.get(service, service)
    return {
        "preset": preset,
        "id": f"spectrum-{service}",
        "config": service_config(profile, service),
        "_spectrum_service": service,
    }


def _attached_spectrum_services(session: Session) -> set[str]:
    attached: set[str] = set()
    prefix = "spectrum-"
    for obs in session._observers:
        obs_id = str(getattr(obs, "observer_id", "") or "")
        if obs_id.startswith(prefix):
            attached.add(obs_id[len(prefix) :])
    return attached


def attach_spectrum_services(session: Session) -> dict[str, Any]:
    """
    Wire spectrum.services to observer presets after explicit profile.observers[].

    Returns activation summary for session.open payload.
    """
    profile = session.profile
    summary: dict[str, Any] = {
        "audit": "implicit",
        "activated": [],
        "skipped_explicit": [],
        "unknown": [],
        "declared": [],
    }

    if not profile_has_spectrum_block(profile):
        summary["note"] = "no spectrum block — service wiring skipped"
        return summary

    spectrum = effective_spectrum(profile)
    summary["declared"] = list(spectrum.services)
    explicit = observer_preset_names(profile)
    already = _attached_spectrum_services(session)
    strict = strict_unknown_services(profile)

    for service in resolve_services_to_wire(profile):
        preset = SERVICE_PRESET.get(service)
        if preset is None:
            summary["unknown"].append(service)
            _emit_service_notice(
                session,
                "unknown_spectrum_service",
                {"service": service, "strict": strict},
                alert=strict,
            )
            continue
        if service in already:
            continue
        if preset in explicit:
            summary["skipped_explicit"].append(service)
            continue
        entry = build_service_observer_entry(profile, service)
        observer = _create_preset_observer(session, preset, entry)
        if observer is not None:
            session._observers.append(observer)
            summary["activated"].append(service)

    if "audit" in [str(s).lower() for s in spectrum.services]:
        summary["audit"] = "declared_implicit"

    return summary


def _create_preset_observer(session: Session, preset: str, entry: dict[str, Any]) -> Any | None:
    if preset == "monitor":
        from aura.observers.presets.monitor import create_monitor_observer

        return create_monitor_observer(session, entry)
    if preset == "break":
        from aura.observers.presets.break_observer import create_break_observer

        return create_break_observer(session, entry)
    if preset == "limit":
        from aura.observers.presets.limit import create_limit_observer

        return create_limit_observer(session, entry)
    if preset == "goal_drift":
        from aura.observers.presets.goal_drift import create_goal_drift_observer

        return create_goal_drift_observer(session, entry)
    if preset == "schedule_slo":
        from aura.observers.presets.schedule_slo import create_schedule_slo_observer

        return create_schedule_slo_observer(session, entry)
    return None


def _emit_service_notice(
    session: Session,
    notice_type: str,
    detail: dict[str, Any],
    *,
    alert: bool = False,
) -> None:
    spine = session.spine
    if spine is None:
        return
    payload = {"type": notice_type, **detail, "source": "spectrum.services"}
    kind = "observer.alert" if alert else "observer.note"
    spine.append(kind, payload, agent_ids=session.agent_ids_trailer())


def merge_spectrum_update(existing: dict[str, Any] | None, patch: dict[str, Any]) -> dict[str, Any]:
    """Merge CLI/profile spectrum patches without dropping level or services."""
    base = dict(existing or {})
    merged = {**base, **patch}
    if "service_config" in base and "service_config" in patch:
        bc = base.get("service_config")
        pc = patch.get("service_config")
        if isinstance(bc, dict) and isinstance(pc, dict):
            svc_merged = {**bc}
            for key, val in pc.items():
                if isinstance(svc_merged.get(key), dict) and isinstance(val, dict):
                    svc_merged[key] = {**svc_merged[key], **val}
                else:
                    svc_merged[key] = val
            merged["service_config"] = svc_merged
    return merged
