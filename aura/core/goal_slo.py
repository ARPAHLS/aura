"""Goal and schedule SLO config — declared intent vs observed behavior."""

from __future__ import annotations

import json
import re
from datetime import datetime, time, timedelta, timezone, tzinfo
from typing import Any, Callable

_STOP_WORDS = frozenset(
    {
        "only",
        "with",
        "from",
        "that",
        "this",
        "into",
        "daily",
        "must",
        "the",
        "and",
        "for",
    }
)


def goal_text_from_profile(profile: Any) -> str | None:
    variables = getattr(profile, "variables", None) or {}
    if not isinstance(variables, dict):
        return None
    goal = variables.get("goal")
    if goal is None:
        return None
    text = str(goal).strip()
    return text or None


def schedule_from_profile(profile: Any) -> str | None:
    variables = getattr(profile, "variables", None) or {}
    if not isinstance(variables, dict):
        return None
    schedule = variables.get("schedule")
    if schedule is None:
        return None
    text = str(schedule).strip()
    return text or None


def schedule_grace_minutes(profile: Any, config: dict[str, Any]) -> int:
    if "schedule_grace_minutes" in config:
        return max(0, int(config["schedule_grace_minutes"]))
    variables = getattr(profile, "variables", None) or {}
    if isinstance(variables, dict) and "schedule_grace_minutes" in variables:
        return max(0, int(variables["schedule_grace_minutes"]))
    return 15


def parse_daily_schedule(schedule: str) -> time:
    """Parse ``HH:MM`` or five-field cron ``M H * * *`` into a daily deadline time."""
    raw = schedule.strip()
    parts = raw.split()
    if len(parts) == 5:
        minute, hour = int(parts[0]), int(parts[1])
        return time(hour=hour, minute=minute)
    if re.fullmatch(r"\d{1,2}:\d{2}", raw):
        hour_str, minute_str = raw.split(":", 1)
        return time(hour=int(hour_str), minute=int(minute_str))
    raise ValueError(f"unsupported schedule format: {schedule!r}")


def resolve_goal_drift_config(profile: Any, entry: dict[str, Any]) -> dict[str, Any]:
    config = dict(entry.get("config") or {}) if isinstance(entry.get("config"), dict) else {}
    goal = config.get("goal")
    if goal is None:
        goal = goal_text_from_profile(profile)
    forbidden = list(config.get("forbidden_topics") or [])
    required = list(config.get("required_keywords") or [])
    required_explicit = "required_keywords" in config
    if not required and goal and config.get("derive_keywords", True):
        required = [
            w
            for w in re.findall(r"[a-z0-9]+", str(goal).lower())
            if len(w) > 3 and w not in _STOP_WORDS
        ][:3]
    kinds = config.get("event_kinds") or ["tool.intent"]
    return {
        "goal": goal,
        "forbidden_topics": [str(t) for t in forbidden],
        "required_keywords": [str(k) for k in required],
        "required_keywords_explicit": required_explicit,
        "event_kinds": [str(k) for k in kinds],
    }


def resolve_schedule_slo_config(profile: Any, entry: dict[str, Any]) -> dict[str, Any]:
    config = dict(entry.get("config") or {}) if isinstance(entry.get("config"), dict) else {}
    schedule = config.get("schedule") or schedule_from_profile(profile)
    if not schedule:
        raise ValueError("schedule_slo preset requires variables.schedule or config.schedule")
    deadline = parse_daily_schedule(str(schedule))
    required_spec = str(config.get("required_tool") or "sql/append")
    required_skill, required_tool = _parse_required_tool(required_spec)
    required_kind = str(config.get("required_kind") or "tool.result")
    now_fn = _resolve_now_fn(profile, config)
    return {
        "deadline": deadline,
        "grace_minutes": schedule_grace_minutes(profile, config),
        "required_tool": required_tool,
        "required_skill": required_skill,
        "required_kind": required_kind,
        "now_fn": now_fn,
    }


def _resolve_now_fn(profile: Any, config: dict[str, Any]) -> Callable[[], datetime] | None:
    if callable(config.get("now_fn")):
        return config["now_fn"]
    clock_iso = config.get("clock_iso")
    variables = getattr(profile, "variables", None) or {}
    if not clock_iso and isinstance(variables, dict):
        clock_iso = variables.get("_test_clock_iso") or variables.get("clock_iso")
    if not clock_iso:
        return None
    fixed = datetime.fromisoformat(str(clock_iso))
    if fixed.tzinfo is None:
        fixed = fixed.replace(tzinfo=timezone.utc)
    return lambda: fixed


def _parse_required_tool(spec: str) -> tuple[str | None, str]:
    if "/" in spec:
        skill, tool = spec.split("/", 1)
        return skill, tool
    return None, spec


def extract_searchable_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True).lower()


def detect_goal_drift(
    text: str,
    *,
    goal: str | None,
    forbidden_topics: list[str],
    required_keywords: list[str],
    require_all_keywords: bool = False,
) -> str | None:
    """Return drift reason when observed text diverges from declared goal."""
    for topic in forbidden_topics:
        needle = topic.lower()
        if needle and needle in text:
            return f"forbidden topic {topic!r} in tool payload"
    if required_keywords:
        if require_all_keywords:
            for keyword in required_keywords:
                needle = keyword.lower()
                if needle and needle not in text:
                    return f"missing required keyword {keyword!r} for goal {goal!r}"
        elif not any(keyword.lower() in text for keyword in required_keywords if keyword):
            return f"off-scope relative to goal {goal!r}"
    return None


def deadline_datetime(
    session_start: datetime,
    deadline: time,
    grace_minutes: int,
    *,
    now_fn: Callable[[], datetime] | None = None,
) -> datetime:
    """Latest acceptable completion instant on the session day (deadline + grace)."""
    tz: tzinfo | None = session_start.tzinfo
    base = datetime.combine(session_start.date(), deadline, tzinfo=tz)
    if base < session_start:
        base += timedelta(days=1)
    return base + timedelta(minutes=grace_minutes)


def is_past_deadline(
    session_start: datetime,
    deadline: time,
    grace_minutes: int,
    *,
    now_fn: Callable[[], datetime] | None = None,
) -> bool:
    now = now_fn() if now_fn else datetime.now(session_start.tzinfo)
    return now > deadline_datetime(session_start, deadline, grace_minutes, now_fn=now_fn)
