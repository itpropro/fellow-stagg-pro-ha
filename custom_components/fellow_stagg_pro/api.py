"""API client for Fellow Stagg Pro local CLI."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .guardrails import normalize_target_temperature_c
from .const import MAX_TARGET_TEMP_C, MIN_TARGET_TEMP_C, TARGET_TEMP_STEP_C
from .control import derive_power_state, is_target_match, should_send_power_toggle
from .parser import (
    extract_ret_code,
    normalize_cli_payload,
    parse_fwinfo_payload,
    parse_settings_payload,
    parse_state_payload,
)
from .temperature import celsius_to_fahrenheit


class FellowStaggProApiError(Exception):
    """API error for Fellow Stagg Pro."""


class FellowStaggProApi:
    """Simple API client for the kettle CLI endpoint."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        request_timeout: float = 10.0,
    ) -> None:
        self._session = session
        self._host = host
        self._port = port
        self._request_timeout = request_timeout
        self._settempr_scale_hint: str | None = None

    @property
    def host(self) -> str:
        """Return configured host."""
        return self._host

    async def async_send_command(self, command: str) -> str:
        """Send CLI command and return normalized text output."""
        url = f"http://{self._host}:{self._port}/cli"

        try:
            async with self._session.get(
                url,
                params={"cmd": command},
                timeout=aiohttp.ClientTimeout(total=self._request_timeout),
            ) as response:
                response.raise_for_status()
                payload = await response.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise FellowStaggProApiError(f"Command '{command}' failed: {err}") from err

        normalized = normalize_cli_payload(payload)
        ret_code = extract_ret_code(normalized)
        if ret_code is not None and ret_code != 0:
            raise FellowStaggProApiError(
                f"Command '{command}' returned non-zero ret code: {ret_code}"
            )

        return normalized

    async def async_get_state(self) -> dict[str, Any]:
        """Fetch and parse runtime state."""
        payload = await self.async_send_command("state")
        return parse_state_payload(payload)

    async def async_get_settings(self) -> dict[str, Any]:
        """Fetch and parse settings dump."""
        payload = await self.async_send_command("prtsettings")
        settings = parse_settings_payload(payload)
        scale = str(settings.get("settempr_scale") or "").lower()
        if scale in {"f", "2c"}:
            self._settempr_scale_hint = scale
        return settings

    async def async_get_fwinfo(self) -> dict[str, Any]:
        """Fetch and parse firmware info."""
        payload = await self.async_send_command("fwinfo")
        return parse_fwinfo_payload(payload)

    async def async_turn_on(self) -> None:
        """Turn kettle heating on."""
        await self._async_set_power(expected_on=True)

    async def async_turn_off(self) -> None:
        """Turn kettle heating off."""
        await self._async_set_power(expected_on=False)

    async def async_set_target_temperature(self, temperature_c: float) -> None:
        """Set target temperature using observed settempr encoding."""
        normalized_temp = normalize_target_temperature_c(
            temperature_c,
            min_c=MIN_TARGET_TEMP_C,
            max_c=MAX_TARGET_TEMP_C,
            step_c=TARGET_TEMP_STEP_C,
        )

        try:
            settings = await self.async_get_settings()
        except FellowStaggProApiError:
            settings = {}
        candidate_scales = _settempr_candidate_scales(settings, self._settempr_scale_hint)
        seen_raw: set[int] = set()
        last_settings_target: float | int | None = None
        last_state_target: float | int | None = None

        for scale in candidate_scales:
            raw_settempr = _encode_settempr_value(normalized_temp, scale)
            if raw_settempr in seen_raw:
                continue
            seen_raw.add(raw_settempr)

            command = f"setsetting settempr {raw_settempr}"
            await self.async_send_command(command)

            for attempt in range(4):
                try:
                    settings = await self.async_get_settings()
                except FellowStaggProApiError:
                    settings = {}

                try:
                    state = await self.async_get_state()
                except FellowStaggProApiError:
                    state = {}

                settings_target = settings.get("settempr_c")
                state_target = state.get("target_temp_c")

                if isinstance(settings_target, (float, int)):
                    last_settings_target = settings_target
                if isinstance(state_target, (float, int)):
                    last_state_target = state_target

                if _is_target_verified(
                    normalized_temp,
                    settings_target,
                    state_target,
                ):
                    self._settempr_scale_hint = scale
                    return

                if attempt == 1:
                    await self.async_send_command(command)

                if attempt < 3:
                    await asyncio.sleep(0.25)

        raise FellowStaggProApiError(
            "Target temperature write mismatch: "
            f"requested={normalized_temp:.1f}C "
            f"settings={_format_optional_temp(last_settings_target)} "
            f"state={_format_optional_temp(last_state_target)}"
        )

    async def _async_set_power(self, expected_on: bool) -> None:
        """Set power state using button-2 state machine toggle."""
        for attempt in range(12):
            try:
                state = await self.async_get_state()
            except FellowStaggProApiError:
                state = {}

            observed_state = derive_power_state(state)
            if observed_state == expected_on:
                return

            if should_send_power_toggle(observed_state, expected_on) and attempt in {
                0,
                4,
                8,
            }:
                await self.async_send_command("2")

            if attempt < 11:
                await asyncio.sleep(0.5)


def _encode_settempr_value(target_c: float, scale: str) -> int:
    """Encode target temperature for `setsetting settempr` based on scale."""
    if scale == "f":
        return int(round(celsius_to_fahrenheit(target_c)))

    return int(round(target_c * 2))


def _settempr_candidate_scales(settings: dict[str, Any], hint: str | None) -> list[str]:
    """Return ordered candidate settempr scales to try."""
    settings_scale = str(settings.get("settempr_scale") or "").lower()
    ordered = [settings_scale, str(hint or "").lower(), "f", "2c"]
    candidates: list[str] = []
    for scale in ordered:
        if scale not in {"f", "2c"}:
            continue
        if scale in candidates:
            continue
        candidates.append(scale)
    return candidates or ["f", "2c"]


def _is_target_verified(
    requested_target_c: float,
    settings_target_c: float | int | None,
    state_target_c: float | int | None,
) -> bool:
    """Return whether write is confirmed by settings/state readback."""
    return any(
        isinstance(candidate, (float, int)) and is_target_match(requested_target_c, candidate)
        for candidate in (settings_target_c, state_target_c)
    )


def _format_optional_temp(value: float | int | None) -> str:
    """Format optional temperature for error details."""
    if not isinstance(value, (float, int)):
        return "unknown"
    return f"{float(value):.1f}C"
