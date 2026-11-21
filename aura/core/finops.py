"""FinOps token-cost estimation and session telemetry aggregation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Approximate USD per 1M tokens: (input_per_1m, output_per_1m).
# Aligned with Skillware's MODEL_PRICING_PER_1M; extensible by hosts.
DEFAULT_MODEL_PRICING_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-7-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.15, 0.60),
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
}


def get_model_pricing_table(
    overrides: Mapping[str, tuple[float, float]] | None = None,
) -> dict[str, tuple[float, float]]:
    """Return merged pricing table: AURA defaults + Skillware pricing (if installed) + overrides."""
    table = dict(DEFAULT_MODEL_PRICING_PER_1M)
    try:
        from skillware.audit import MODEL_PRICING_PER_1M as _sw_pricing

        if isinstance(_sw_pricing, Mapping):
            for model, rates in _sw_pricing.items():
                if (
                    isinstance(rates, (tuple, list))
                    and len(rates) == 2
                    and isinstance(rates[0], (int, float))
                    and isinstance(rates[1], (int, float))
                ):
                    table.setdefault(str(model).strip().lower(), (float(rates[0]), float(rates[1])))
    except ImportError:
        pass
    if overrides:
        for model, rates in overrides.items():
            table[str(model).strip().lower()] = (float(rates[0]), float(rates[1]))
    return table


def estimate_cost_usd(
    model: str | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    pricing: Mapping[str, tuple[float, float]] | None = None,
) -> float | None:
    """Estimate USD cost for a model call when token counts and pricing are known."""
    if not model or prompt_tokens is None or completion_tokens is None:
        return None
    table = get_model_pricing_table(pricing)
    norm = model.strip().lower()
    rates = table.get(norm)
    if rates is None:
        for prefix, candidate in table.items():
            if norm.startswith(prefix):
                rates = candidate
                break
    if rates is None:
        return None
    in_rate, out_rate = rates
    cost = (int(prompt_tokens) * in_rate + int(completion_tokens) * out_rate) / 1_000_000.0
    return round(cost, 8)


def _event_field(event: Any, key: str) -> Any:
    if isinstance(event, Mapping):
        return event.get(key)
    return getattr(event, key, None)


def summarize_session_finops(events: list[Any]) -> dict[str, Any]:
    """
    Aggregate tokens, estimated USD cost, and tool latency across a spine event stream.

    Deduplicates bridged ``skill.dispatch`` and ``tool.result``/``tool.error`` events that share
    the same ``span_id`` so FinOps totals are never double-counted.
    """
    total_prompt = 0
    total_completion = 0
    total_cost = 0.0
    cost_by_model: dict[str, float] = {}
    cost_by_skill: dict[str, float] = {}
    latencies: list[float] = []

    # Collect span_ids already accounted for by outer egress tool.result / tool.error events
    egress_spans: set[str] = set()
    for evt in events:
        kind = _event_field(evt, "kind")
        if kind in {"tool.result", "tool.error"}:
            sid = _event_field(evt, "span_id")
            if sid:
                egress_spans.add(str(sid))

    seen_cost_spans: set[str] = set()

    for evt in events:
        kind = _event_field(evt, "kind") or ""
        payload = _event_field(evt, "payload") or {}
        telemetry = _event_field(evt, "telemetry") or {}
        span_id = _event_field(evt, "span_id")

        if kind == "skill.dispatch" and span_id and str(span_id) in egress_spans:
            # Outer tool.result/tool.error carries the authoritative merged telemetry for this span
            continue

        if kind not in {"tool.result", "tool.error", "skill.dispatch", "model.call", "turn.end"}:
            continue

        latency = telemetry.get("latency_ms")
        if latency is None and kind == "skill.dispatch":
            latency = payload.get("duration_ms")
        if isinstance(latency, (int, float)) and latency >= 0:
            latencies.append(float(latency))

        if span_id and str(span_id) in seen_cost_spans:
            continue

        model = telemetry.get("model") or payload.get("model")
        prompt_tokens = telemetry.get("prompt_tokens")
        if prompt_tokens is None:
            prompt_tokens = payload.get("prompt_tokens")
        completion_tokens = telemetry.get("completion_tokens")
        if completion_tokens is None:
            completion_tokens = payload.get("completion_tokens")
        cost = telemetry.get("estimated_cost_usd")
        if cost is None:
            cost = payload.get("estimated_cost_usd")
        if cost is None and model and prompt_tokens is not None and completion_tokens is not None:
            cost = estimate_cost_usd(str(model), int(prompt_tokens), int(completion_tokens))

        recorded_any = False
        if isinstance(prompt_tokens, int):
            total_prompt += prompt_tokens
            recorded_any = True
        if isinstance(completion_tokens, int):
            total_completion += completion_tokens
            recorded_any = True
        if isinstance(cost, (int, float)):
            cost_val = float(cost)
            total_cost += cost_val
            recorded_any = True
            if model:
                model_key = str(model)
                cost_by_model[model_key] = round(cost_by_model.get(model_key, 0.0) + cost_val, 8)
            skill_id = telemetry.get("skill_id") or payload.get("skill_id")
            if skill_id:
                skill_key = str(skill_id)
                cost_by_skill[skill_key] = round(cost_by_skill.get(skill_key, 0.0) + cost_val, 8)

        if recorded_any and span_id:
            seen_cost_spans.add(str(span_id))

    latency_summary: dict[str, Any] = {
        "count": len(latencies),
        "total_ms": round(sum(latencies), 3) if latencies else 0.0,
        "avg_ms": round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
        "max_ms": round(max(latencies), 3) if latencies else 0.0,
    }

    return {
        "prompt_tokens": total_prompt,
        "completion_tokens": total_completion,
        "total_tokens": total_prompt + total_completion,
        "estimated_cost_usd": round(total_cost, 8),
        "cost_by_model": cost_by_model,
        "cost_by_skill": cost_by_skill,
        "latency": latency_summary,
    }
