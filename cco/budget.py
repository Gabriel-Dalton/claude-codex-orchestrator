"""Usage-window state and pace, with the worst known window governing."""

import time
from .providers.base import number

DEFAULTS = {"tight_remaining_percent": 30, "critical_remaining_percent": 10,
            "max_age_seconds": 3600}


def thresholds(config=None):
    result = dict(DEFAULTS, **(config or {}))
    if any(number(result[k]) is None for k in DEFAULTS):
        raise ValueError("Budget thresholds must be finite numbers")
    if not 0 <= result["critical_remaining_percent"] <= result["tight_remaining_percent"] <= 100:
        raise ValueError("Budget remaining thresholds must be ordered between 0 and 100")
    if result["max_age_seconds"] <= 0:
        raise ValueError("Budget max_age_seconds must be positive")
    return result


def evaluate(usage, config=None, now=None):
    cfg = thresholds(config)
    now = time.time() if now is None else now
    age = max(0, now - usage.observed_at) if usage.observed_at is not None else None
    stale = age is None or age > cfg["max_age_seconds"]
    rows = []
    for window in usage.windows:
        reset = window.resets_at
        expected = window.expected_percent
        if expected is None and reset is not None and window.window_minutes and window.window_minutes > 0:
            expected = min(100, max(0, 100 * (1 - (reset - now) / (window.window_minutes * 60))))
        used = window.used_percent
        valid = used is not None and 0 <= used <= 100
        ahead = window.ahead_of_pace
        if ahead is None and expected is not None and valid:
            ahead = used > expected
        projected = window.projected_exhaustion_at
        state = "unknown"
        if not stale and valid and (reset is None or reset > now):
            if usage.limit_reached:
                state = "exhausted"
            elif 100 - used < cfg["critical_remaining_percent"] or (
                    projected is not None and reset is not None and projected < reset):
                state = "critical"
            elif 100 - used < cfg["tight_remaining_percent"] or ahead is True:
                state = "tight"
            elif ahead is False:
                state = "ok"
        rows.append({"name": window.name, "used_percent": used, "window_minutes": window.window_minutes,
                     "resets_at": reset, "reset_in_seconds": max(0, reset - now) if reset is not None else None,
                     "expected_percent": expected, "ahead_of_pace": ahead,
                     "pace_delta_percent": used - expected if valid and expected is not None else None,
                     "projected_exhaustion_at": projected, "state": state})
    states = [row["state"] for row in rows]
    if stale:
        state = "unknown"
    elif usage.limit_reached:
        state = "exhausted"
    elif usage.unlimited:
        state = "ok"
    else:
        state = next((s for s in ("critical", "tight", "unknown", "ok") if s in states), "unknown")
    return {"state": state, "age_seconds": age, "windows": rows, "unlimited": usage.unlimited,
            "limit_reached": usage.limit_reached, "plan_type": usage.plan_type}
