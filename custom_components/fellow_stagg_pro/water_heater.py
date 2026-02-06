"""Water heater entity for Fellow Stagg Pro."""

from __future__ import annotations

from typing import Any

from homeassistant.components.water_heater import (
    ATTR_TEMPERATURE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.temperature import celsius_to_fahrenheit, fahrenheit_to_celsius

from . import FellowStaggProConfigEntry
from .const import (
    CONF_ENABLE_HEAT_CONTROL,
    CONF_ENABLE_SET_TEMPERATURE,
    COORDINATOR_DATA_FWINFO,
    COORDINATOR_DATA_SETTINGS,
    COORDINATOR_DATA_STATE,
    DEFAULT_ENABLE_HEAT_CONTROL,
    DEFAULT_ENABLE_SET_TEMPERATURE,
    DOMAIN,
    MAX_TARGET_TEMP_C,
    MIN_TARGET_TEMP_C,
    NAME,
    TARGET_TEMP_STEP_C,
)
from .coordinator import FellowStaggProDataUpdateCoordinator
from .guardrails import is_control_enabled, normalize_target_temperature_c


async def async_setup_entry(
    hass,
    entry: FellowStaggProConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up water heater entity."""
    async_add_entities([FellowStaggProWaterHeater(entry.runtime_data.coordinator, entry)])


class FellowStaggProWaterHeater(
    CoordinatorEntity[FellowStaggProDataUpdateCoordinator], WaterHeaterEntity
):
    """Represent the Fellow Stagg Pro kettle as a water heater."""

    _attr_has_entity_name = True
    _attr_name = "Kettle"
    _attr_min_temp = MIN_TARGET_TEMP_C
    _attr_max_temp = MAX_TARGET_TEMP_C
    _attr_target_temperature_step = TARGET_TEMP_STEP_C

    def __init__(
        self,
        coordinator: FellowStaggProDataUpdateCoordinator,
        entry: FellowStaggProConfigEntry,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}-water-heater"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.unique_id or self._entry.entry_id)},
            name=NAME,
            manufacturer="Fellow",
            model="Stagg EKG Pro",
            sw_version=self.coordinator.data.get(COORDINATOR_DATA_FWINFO, {}).get("version"),
        )

    @property
    def temperature_unit(self) -> str:
        """Return displayed temperature unit."""
        return (
            UnitOfTemperature.CELSIUS
            if self._kettle_units() == 1
            else UnitOfTemperature.FAHRENHEIT
        )

    @property
    def current_temperature(self) -> float | None:
        """Return current water temperature."""
        temp_c = self._state().get("current_temp_c")
        if temp_c is None:
            return None
        return self._from_celsius(temp_c)

    @property
    def target_temperature(self) -> float | None:
        """Return target temperature."""
        target_c = self._state().get("target_temp_c")
        if target_c is None:
            target_c = self._settings().get("settempr_c")
        if target_c is None:
            return None
        return self._from_celsius(target_c)

    @property
    def is_on(self) -> bool | None:
        """Return whether kettle appears to be active."""
        mode = str(self._state().get("mode") or "").lower()
        if mode:
            return "off" not in mode

        heat_flag = self._state().get("flags", {}).get("ho")
        if isinstance(heat_flag, int):
            return bool(heat_flag)

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        state = self._state()
        return {
            "mode": state.get("mode"),
            "screen": state.get("scrname"),
            "clock": state.get("clock"),
            "boil_temperature_c": state.get("boil_temp_c"),
            "ble_connected": state.get("ble_connected"),
            "flags": state.get("flags"),
            "controls_enabled": {
                "heat_control": self._heat_control_enabled(),
                "set_temperature": self._set_temperature_enabled(),
            },
        }

    @property
    def supported_features(self) -> WaterHeaterEntityFeature:
        """Return supported feature flags based on configured guardrails."""
        features = WaterHeaterEntityFeature(0)
        if self._heat_control_enabled():
            features |= WaterHeaterEntityFeature.ON_OFF
        if self._set_temperature_enabled():
            features |= WaterHeaterEntityFeature.TARGET_TEMPERATURE
        return features

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the kettle heating on."""
        if not self._heat_control_enabled():
            raise HomeAssistantError(
                "Heat control is disabled by guardrails. Enable it in integration options."
            )

        await self.coordinator.api.async_turn_on()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the kettle heating off."""
        if not self._heat_control_enabled():
            raise HomeAssistantError(
                "Heat control is disabled by guardrails. Enable it in integration options."
            )

        await self.coordinator.api.async_turn_off()
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        if not self._set_temperature_enabled():
            raise HomeAssistantError(
                "Set temperature is disabled by guardrails. Enable it in integration options."
            )

        target = kwargs.get(ATTR_TEMPERATURE)
        if target is None:
            return

        target_c = self._to_celsius(float(target))
        target_c = normalize_target_temperature_c(
            target_c,
            min_c=self._attr_min_temp,
            max_c=self._attr_max_temp,
            step_c=self._attr_target_temperature_step,
        )
        await self.coordinator.api.async_set_target_temperature(target_c)
        await self.coordinator.async_request_refresh()

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

    def _from_celsius(self, value_c: float) -> float:
        if self.temperature_unit == UnitOfTemperature.FAHRENHEIT:
            return round(celsius_to_fahrenheit(value_c), 1)
        return value_c

    def _to_celsius(self, value: float) -> float:
        if self.temperature_unit == UnitOfTemperature.FAHRENHEIT:
            return float(fahrenheit_to_celsius(value))
        return value

    def _heat_control_enabled(self) -> bool:
        return is_control_enabled(
            key=CONF_ENABLE_HEAT_CONTROL,
            data=self._entry.data,
            options=self._entry.options,
            default=DEFAULT_ENABLE_HEAT_CONTROL,
        )

    def _set_temperature_enabled(self) -> bool:
        return is_control_enabled(
            key=CONF_ENABLE_SET_TEMPERATURE,
            data=self._entry.data,
            options=self._entry.options,
            default=DEFAULT_ENABLE_SET_TEMPERATURE,
        )
