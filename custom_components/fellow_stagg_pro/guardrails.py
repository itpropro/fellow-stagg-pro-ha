"""Safety and control guardrails for Fellow Stagg Pro."""

from __future__ import annotations

import math
from typing import Any, Mapping


def is_control_enabled(
    *,
    key: str,
    data: Mapping[str, Any],
    options: Mapping[str, Any],
    default: bool,
) -> bool:
    """Return whether a risky control is enabled, preferring options over data."""
    if key in options:
        return _to_bool(options[key])
    if key in data:
        return _to_bool(data[key])
    return default


def normalize_target_temperature_c(
    temperature_c: float,
    *,
    min_c: float,
    max_c: float,
    step_c: float,
) -> float:
    """Validate and normalize a temperature to kettle-supported step size."""
    if step_c <= 0:
        raise ValueError("Temperature step must be greater than zero")
    if min_c > max_c:
        raise ValueError("Temperature bounds are invalid")

    if not math.isfinite(temperature_c):
        raise ValueError("Temperature must be a finite number")
    if temperature_c < min_c or temperature_c > max_c:
        raise ValueError(
            f"Temperature {temperature_c:.2f}C is outside allowed range {min_c:.1f}-{max_c:.1f}C"
        )

    steps = round((temperature_c - min_c) / step_c)
    normalized = min_c + steps * step_c

    if normalized < min_c:
        normalized = min_c
    if normalized > max_c:
        normalized = max_c

    return round(normalized, 3)


def _to_bool(value: Any) -> bool:
    """Convert common truthy/falsy forms to bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "enabled"}:
            return True
        if normalized in {"0", "false", "no", "off", "disabled"}:
            return False
    return bool(value)
