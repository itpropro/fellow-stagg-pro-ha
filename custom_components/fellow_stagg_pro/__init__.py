"""Fellow Stagg Pro integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv

from .api import FellowStaggProApi
from .const import CONF_SCAN_INTERVAL, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN, PLATFORMS
from .coordinator import FellowStaggProDataUpdateCoordinator


@dataclass(slots=True)
class FellowStaggProRuntimeData:
    """Runtime data for a config entry."""

    api: FellowStaggProApi
    coordinator: FellowStaggProDataUpdateCoordinator


FellowStaggProConfigEntry: TypeAlias = ConfigEntry[FellowStaggProRuntimeData]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FellowStaggProConfigEntry) -> bool:
    """Set up Fellow Stagg Pro from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    api = FellowStaggProApi(async_get_clientsession(hass), host, port)
    coordinator = FellowStaggProDataUpdateCoordinator(hass, api, scan_interval)

    await coordinator.async_config_entry_first_refresh()

    runtime_data = FellowStaggProRuntimeData(api=api, coordinator=coordinator)
    hass.data[DOMAIN][entry.entry_id] = runtime_data
    if hasattr(entry, "runtime_data"):
        entry.runtime_data = runtime_data
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FellowStaggProConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: FellowStaggProConfigEntry) -> None:
    """Reload config entry after options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def get_runtime_data(
    hass: HomeAssistant, entry: FellowStaggProConfigEntry
) -> FellowStaggProRuntimeData:
    """Return runtime data for current Home Assistant version."""
    if hasattr(entry, "runtime_data") and entry.runtime_data is not None:
        return entry.runtime_data
    return hass.data[DOMAIN][entry.entry_id]
