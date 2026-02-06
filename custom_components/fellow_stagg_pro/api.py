"""API client for Fellow Stagg Pro local CLI."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .guardrails import normalize_target_temperature_c
from .const import MAX_TARGET_TEMP_C, MIN_TARGET_TEMP_C, TARGET_TEMP_STEP_C
from .parser import (
    extract_ret_code,
    normalize_cli_payload,
    parse_fwinfo_payload,
    parse_settings_payload,
    parse_state_payload,
)


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
        """Turn heat on (experimental mapping)."""
        await self.async_send_command("heaton")

    async def async_turn_off(self) -> None:
        """Turn heat off (experimental mapping)."""
        await self.async_send_command("heatoff")

    async def async_set_target_temperature(self, temperature_c: float) -> None:
        """Set target temperature using observed settempr encoding."""
        normalized_temp = normalize_target_temperature_c(
            temperature_c,
            min_c=MIN_TARGET_TEMP_C,
            max_c=MAX_TARGET_TEMP_C,
            step_c=TARGET_TEMP_STEP_C,
        )
        raw_half_celsius = int(round(normalized_temp * 2))
        await self.async_send_command(f"setsetting settempr {raw_half_celsius}")
