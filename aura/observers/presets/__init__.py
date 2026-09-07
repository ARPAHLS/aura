"""Packaged observer presets (monitor, break, limit, goal_drift, schedule_slo, …)."""

from aura.observers.presets.break_observer import BreakObserver, create_break_observer
from aura.observers.presets.goal_drift import GoalDriftObserver, create_goal_drift_observer
from aura.observers.presets.limit import LimitObserver, create_limit_observer
from aura.observers.presets.monitor import MonitorObserver, create_monitor_observer
from aura.observers.presets.schedule_slo import ScheduleSLOObserver, create_schedule_slo_observer

__all__ = [
    "BreakObserver",
    "GoalDriftObserver",
    "LimitObserver",
    "MonitorObserver",
    "ScheduleSLOObserver",
    "create_break_observer",
    "create_goal_drift_observer",
    "create_limit_observer",
    "create_monitor_observer",
    "create_schedule_slo_observer",
]
