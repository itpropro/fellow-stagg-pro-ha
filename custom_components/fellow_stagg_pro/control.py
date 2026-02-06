"""Control behavior helpers for target temperature handling."""

from __future__ import annotations

from typing import Any

TARGET_MATCH_TOLERANCE_C = 0.30
OPERATION_OFF = "off"
OPERATION_HEATING = "electric"
OPERATION_HOLDING = "eco"


def is_target_match(target_a_c: float | int | None, target_b_c: float | int | None) -> bool:
    """Return True when both target values match within tolerance."""
    if target_a_c is None or target_b_c is None:
        return False
    return abs(float(target_a_c) - float(target_b_c)) <= TARGET_MATCH_TOLERANCE_C


def resolve_target_temperature_c(
    *,
    optimistic_target_c: float | None,
    settings: dict[str, Any],
    state: dict[str, Any],
) -> float | None:
    """Resolve the most reliable target source in priority order."""
    if optimistic_target_c is not None:
        return optimistic_target_c

    settings_target_c = settings.get("settempr_c")
    if isinstance(settings_target_c, (float, int)):
        return float(settings_target_c)

    state_target_c = state.get("target_temp_c")
    if isinstance(state_target_c, (float, int)):
        return float(state_target_c)

    return None


def derive_power_state(state: dict[str, Any]) -> bool | None:
    """Derive on/off state from parsed kettle state payload."""
    mode = str(state.get("mode") or "").strip().lower()
    if mode:
        return "off" not in mode

    heat_flag = state.get("flags", {}).get("ho")
    if isinstance(heat_flag, int):
        return bool(heat_flag)

    return None


def derive_operation_mode(state: dict[str, Any]) -> str | None:
    """Map kettle state to Home Assistant operation mode values."""
    mode = str(state.get("mode") or "").strip().lower()

    if "off" in mode:
        return OPERATION_OFF
    if "hold" in mode:
        return OPERATION_HOLDING

    derived_power = derive_power_state(state)
    if derived_power is False:
        return OPERATION_OFF
    if derived_power is True:
        return OPERATION_HEATING

    return None


def should_send_power_toggle(observed_on: bool | None, expected_on: bool) -> bool:
    """Return True when a button-2 power toggle should be sent."""
    if observed_on is None:
        return True
    return observed_on != expected_on
