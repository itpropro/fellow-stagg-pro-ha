"""Sensor entities for Fellow Stagg Pro."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FellowStaggProConfigEntry, get_runtime_data
from .const import (
    COORDINATOR_DATA_FWINFO,
    COORDINATOR_DATA_SETTINGS,
    COORDINATOR_DATA_STATE,
    DOMAIN,
    NAME,
)
from .coordinator import FellowStaggProDataUpdateCoordinator
from .temperature import celsius_to_fahrenheit


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FellowStaggProConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fellow Stagg Pro sensors."""
    coordinator = get_runtime_data(hass, entry).coordinator
    unique_root = entry.unique_id or entry.entry_id

    async_add_entities(
        [
            FellowStaggProTemperatureSensor(coordinator, unique_root, "current"),
            FellowStaggProTemperatureSensor(coordinator, unique_root, "target"),
            FellowStaggProValueSensor(
                coordinator,
                unique_root,
                key="mode",
                name="Mode",
                icon="mdi:coffee-maker-check-outline",
                value_fn=lambda data: data.get(COORDINATOR_DATA_STATE, {}).get("mode"),
            ),
            FellowStaggProValueSensor(
                coordinator,
                unique_root,
                key="clock",
                name="Clock",
                icon="mdi:clock-outline",
                value_fn=lambda data: data.get(COORDINATOR_DATA_STATE, {}).get("clock"),
            ),
            FellowStaggProValueSensor(
                coordinator,
                unique_root,
                key="firmware_version",
                name="Firmware Version",
                icon="mdi:chip",
                value_fn=lambda data: data.get(COORDINATOR_DATA_FWINFO, {}).get("version"),
            ),
            FellowStaggProValueSensor(
                coordinator,
                unique_root,
                key="ble_connected",
                name="BLE Connected",
                icon="mdi:bluetooth",
                value_fn=lambda data: data.get(COORDINATOR_DATA_STATE, {}).get("ble_connected"),
            ),
        ]
    )


class FellowStaggProBaseEntity(CoordinatorEntity[FellowStaggProDataUpdateCoordinator]):
    """Base coordinator entity for the integration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FellowStaggProDataUpdateCoordinator,
        unique_root: str,
        key: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = unique_root
        self._attr_unique_id = f"{unique_root}-{key}"
        self._attr_name = name

    @property
    def device_info(self) -> DeviceInfo:
        """Return parent device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=NAME,
            manufacturer="Fellow",
            model="Stagg EKG Pro",
            sw_version=self.coordinator.data.get(COORDINATOR_DATA_FWINFO, {}).get("version"),
        )

    def _state(self) -> dict[str, Any]:
        return self.coordinator.data.get(COORDINATOR_DATA_STATE, {})

    def _settings(self) -> dict[str, Any]:
        return self.coordinator.data.get(COORDINATOR_DATA_SETTINGS, {})

    def _kettle_units(self) -> int:
        state_units = self._state().get("units")
        if isinstance(state_units, int):
            return state_units
        settings_units = self._settings().get("units_int")
        if isinstance(settings_units, int):
            return settings_units
        return 1


class FellowStaggProTemperatureSensor(FellowStaggProBaseEntity, SensorEntity):
    """Temperature sensor entities."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _key_to_field = {
        "current": "current_temp_c",
        "target": "target_temp_c",
    }

    def __init__(
        self,
        coordinator: FellowStaggProDataUpdateCoordinator,
        unique_root: str,
        key: str,
    ) -> None:
        name = "Current Temperature" if key == "current" else "Target Temperature"
        super().__init__(coordinator, unique_root, f"sensor_{key}_temperature", name)
        self._key = key

    @property
    def native_unit_of_measurement(self) -> str:
        """Return native unit of measurement."""
        if self._kettle_units() == 1:
            return UnitOfTemperature.CELSIUS
        return UnitOfTemperature.FAHRENHEIT

    @property
    def native_value(self) -> float | None:
        """Return current sensor value."""
        value_c = self._state().get(self._key_to_field[self._key])
        if not isinstance(value_c, (float, int)):
            return None

        if self._kettle_units() == 1:
            return float(value_c)
        return round(celsius_to_fahrenheit(float(value_c)), 1)


class FellowStaggProValueSensor(FellowStaggProBaseEntity, SensorEntity):
    """Simple value sensor sourced from coordinator data."""

    def __init__(
        self,
        coordinator: FellowStaggProDataUpdateCoordinator,
        unique_root: str,
        key: str,
        name: str,
        value_fn: Callable[[dict[str, Any]], Any],
        icon: str,
    ) -> None:
        super().__init__(coordinator, unique_root, f"sensor_{key}", name)
        self._value_fn = value_fn
        self._attr_icon = icon

    @property
    def native_value(self) -> Any:
        """Return current sensor value."""
        return self._value_fn(self.coordinator.data)
