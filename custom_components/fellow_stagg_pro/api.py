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
        return parse_settings_payload(payload)

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

        raw_settempr = _encode_settempr_value(normalized_temp, settings)
        command = f"setsetting settempr {raw_settempr}"
        await self.async_send_command(command)

        last_settings_target: float | int | None = None
        for attempt in range(3):
            try:
                settings = await self.async_get_settings()
            except FellowStaggProApiError:
                settings = {}

            settings_target = settings.get("settempr_c")
            if isinstance(settings_target, (float, int)):
                last_settings_target = settings_target

            if isinstance(settings_target, (float, int)) and is_target_match(
                normalized_temp, settings_target
            ):
                return

            if attempt == 0:
                await self.async_send_command(command)

            if attempt < 2:
                await asyncio.sleep(0.2)

        if last_settings_target is None:
            raise FellowStaggProApiError(
                "Target temperature write could not be verified from settings"
            )

        raise FellowStaggProApiError(
            "Target temperature write mismatch: "
            f"requested={normalized_temp:.1f}C observed={float(last_settings_target):.1f}C"
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


def _encode_settempr_value(target_c: float, settings: dict[str, Any]) -> int:
    """Encode target temperature for `setsetting settempr` based on device format."""
    scale = str(settings.get("settempr_scale") or "").lower()

    if scale == "f":
        return int(round(celsius_to_fahrenheit(target_c)))

    return int(round(target_c * 2))
