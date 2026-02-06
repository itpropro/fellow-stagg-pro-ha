"""Config flow for Fellow Stagg Pro."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FellowStaggProApi, FellowStaggProApiError
from .const import (
    CONF_ENABLE_HEAT_CONTROL,
    CONF_ENABLE_SET_TEMPERATURE,
    CONF_SCAN_INTERVAL,
    DEFAULT_ENABLE_HEAT_CONTROL,
    DEFAULT_ENABLE_SET_TEMPERATURE,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NAME,
)


def _user_schema(
    host: str = "",
    port: int = DEFAULT_PORT,
    scan_interval: int = DEFAULT_SCAN_INTERVAL,
    enable_heat_control: bool = DEFAULT_ENABLE_HEAT_CONTROL,
    enable_set_temperature: bool = DEFAULT_ENABLE_SET_TEMPERATURE,
) -> vol.Schema:
    """Return user step schema."""
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_PORT, default=port): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Required(CONF_SCAN_INTERVAL, default=scan_interval): vol.All(
                vol.Coerce(int), vol.Range(min=5, max=300)
            ),
            vol.Required(CONF_ENABLE_HEAT_CONTROL, default=enable_heat_control): bool,
            vol.Required(
                CONF_ENABLE_SET_TEMPERATURE,
                default=enable_set_temperature,
            ): bool,
        }
    )


class FellowStaggProConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fellow Stagg Pro."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> FellowStaggProOptionsFlow:
        """Return options flow handler."""
        return FellowStaggProOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            scan_interval = user_input[CONF_SCAN_INTERVAL]
            enable_heat_control = user_input[CONF_ENABLE_HEAT_CONTROL]
            enable_set_temperature = user_input[CONF_ENABLE_SET_TEMPERATURE]

            await self.async_set_unique_id(host.lower())
            self._abort_if_unique_id_configured()

            if await _can_connect(self.hass, host, port):
                return self.async_create_entry(
                    title=f"{NAME} ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_SCAN_INTERVAL: scan_interval,
                        CONF_ENABLE_HEAT_CONTROL: enable_heat_control,
                        CONF_ENABLE_SET_TEMPERATURE: enable_set_temperature,
                    },
                )

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(),
            errors=errors,
        )


class FellowStaggProOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Fellow Stagg Pro."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_scan_interval = self._config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self._config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        current_enable_heat_control = self._config_entry.options.get(
            CONF_ENABLE_HEAT_CONTROL,
            self._config_entry.data.get(
                CONF_ENABLE_HEAT_CONTROL,
                DEFAULT_ENABLE_HEAT_CONTROL,
            ),
        )
        current_enable_set_temperature = self._config_entry.options.get(
            CONF_ENABLE_SET_TEMPERATURE,
            self._config_entry.data.get(
                CONF_ENABLE_SET_TEMPERATURE,
                DEFAULT_ENABLE_SET_TEMPERATURE,
            ),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=current_scan_interval,
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
                    vol.Required(
                        CONF_ENABLE_HEAT_CONTROL,
                        default=current_enable_heat_control,
                    ): bool,
                    vol.Required(
                        CONF_ENABLE_SET_TEMPERATURE,
                        default=current_enable_set_temperature,
                    ): bool,
                }
            ),
        )


async def _can_connect(hass: HomeAssistant, host: str, port: int) -> bool:
    """Return True if the kettle endpoint is reachable."""
    api = FellowStaggProApi(async_get_clientsession(hass), host, port)
    try:
        await api.async_get_state()
    except FellowStaggProApiError:
        return False

    return True
