"""Parse Fellow Stagg Pro CLI payloads into structured data."""

from __future__ import annotations

import re
from typing import Any


def normalize_cli_payload(payload: str) -> str:
    """Normalize text by stripping HTML and line ending noise."""
    cleaned = re.sub(r"<[^>]+>", "\n", payload)
    return cleaned.replace("\r", "")


def extract_ret_code(payload: str) -> int | None:
    """Extract command return code from payload."""
    match = re.search(r"\bret\s+(-?\d+)\b", payload)
    if not match:
        return None
    return int(match.group(1))


def parse_state_payload(payload: str) -> dict[str, Any]:
    """Parse runtime state payload from `state` command."""
    mode = extract_line_value(payload, "mode")
    units_value = extract_line_value(payload, "units")
    return {
        "scrname": extract_line_value(payload, "scrname"),
        "mode": mode,
        "current_temp_c": parse_temperature(extract_line_value(payload, "tempr")),
        "target_temp_c": parse_temperature(extract_line_value(payload, "temprT")),
        "boil_temp_c": parse_temperature(extract_line_value(payload, "temprB")),
        "clock": extract_line_value(payload, "clock"),
        "ble_connected": parse_int(extract_line_value(payload, "ble conn")),
        "units": parse_int(units_value),
        "flags": parse_state_flags(extract_line_value(payload, "ketl")),
    }


def parse_settings_payload(payload: str) -> dict[str, Any]:
    """Parse persistent settings payload from `prtsettings` command."""
    settings: dict[str, Any] = {}

    for raw_line in payload.splitlines():
        line = raw_line.strip().strip("'")
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        settings[key.strip().replace(" ", "_")] = value.strip()

    settempr_value = settings.get("settempr")
    if isinstance(settempr_value, str):
        raw_match = re.match(r"\s*(-?[0-9]+)\s+([^\s(]+)", settempr_value)
        if raw_match:
            settings["settempr_raw"] = int(raw_match.group(1))
            settings["settempr_scale"] = raw_match.group(2).lower()

        celsius_match = re.search(r"\((-?[0-9]+(?:\.[0-9]+)?)\s*C", settempr_value)
        if celsius_match:
            settings["settempr_c"] = float(celsius_match.group(1))

    units = settings.get("units")
    if isinstance(units, str):
        settings["units_int"] = parse_int(units)

    return settings


def parse_fwinfo_payload(payload: str) -> dict[str, Any]:
    """Parse firmware metadata payload from `fwinfo` command."""
    return {
        "version": extract_colon_value(payload, "Current version"),
        "boot_partition": extract_colon_value(payload, "Current boot partition"),
        "running_partition": extract_colon_value(payload, "Current running partition"),
        "last_invalid_partition": extract_colon_value(
            payload, "Current last invalid partition"
        ),
    }


def extract_line_value(payload: str, key: str) -> str | None:
    """Extract a `key=value` value from payload."""
    match = re.search(rf"(?m)^\s*{re.escape(key)}=([^\n]+)$", payload)
    if not match:
        return None
    return match.group(1).strip()


def extract_colon_value(payload: str, key: str) -> str | None:
    """Extract a `key: value` value from payload."""
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*([^\n]*)$", payload)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def parse_temperature(value: str | None) -> float | None:
    """Parse first floating point value from text."""
    if value is None:
        return None
    match = re.search(r"-?[0-9]+(?:\.[0-9]+)?", value)
    if not match:
        return None
    return float(match.group(0))


def parse_int(value: str | None) -> int | None:
    """Parse first integer value from text."""
    if value is None:
        return None
    match = re.search(r"-?[0-9]+", value)
    if not match:
        return None
    return int(match.group(0))


def parse_state_flags(value: str | None) -> dict[str, int]:
    """Parse compact `ketl=` flags like `ho 0 wd 1 ...`."""
    if not value:
        return {}

    parts = value.split()
    flags: dict[str, int] = {}
    for index in range(0, len(parts) - 1, 2):
        flag = parts[index]
        flag_value = parse_int(parts[index + 1])
        if flag_value is None:
            continue
        flags[flag] = flag_value
    return flags
