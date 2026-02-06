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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FellowStaggProConfigEntry, get_runtime_data
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
from .control import (
    OPERATION_HEATING,
    OPERATION_HOLDING,
    OPERATION_OFF,
    derive_operation_mode,
    derive_power_state,
    is_target_match,
    resolve_target_temperature_c,
)
from .coordinator import FellowStaggProDataUpdateCoordinator
from .guardrails import is_control_enabled, normalize_target_temperature_c
from .temperature import celsius_to_fahrenheit, fahrenheit_to_celsius


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FellowStaggProConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up water heater entity."""
    runtime_data = get_runtime_data(hass, entry)
    async_add_entities([FellowStaggProWaterHeater(runtime_data.coordinator, entry)])


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
        self._optimistic_target_c: float | None = None
        self._optimistic_refreshes_remaining = 0
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
        target_c = resolve_target_temperature_c(
            optimistic_target_c=self._optimistic_target_c,
            settings=self._settings(),
            state=self._state(),
        )
        if target_c is None:
            return None
        return self._from_celsius(target_c)

    @property
    def is_on(self) -> bool | None:
        """Return whether kettle appears to be active."""
        return derive_power_state(self._state())

    @property
    def current_operation(self) -> str | None:
        """Return mapped operation mode for Home Assistant UI state."""
        return derive_operation_mode(self._state())

    @property
    def operation_list(self) -> list[str]:
        """Return supported operation modes for state mapping."""
        return [OPERATION_OFF, OPERATION_HEATING, OPERATION_HOLDING]

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
            "target_write_pending": self._optimistic_target_c is not None,
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
                "Heat control is disabled. Enable it in integration options."
            )

        await self.coordinator.api.async_turn_on()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the kettle heating off."""
        if not self._heat_control_enabled():
            raise HomeAssistantError(
                "Heat control is disabled. Enable it in integration options."
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
        self._optimistic_target_c = target_c
        self._optimistic_refreshes_remaining = 6
        self.async_write_ha_state()
        await self.coordinator.api.async_set_target_temperature(target_c)
        await self.coordinator.async_request_refresh()

    def _handle_coordinator_update(self) -> None:
        """Handle refreshed coordinator data."""
        if self._optimistic_target_c is not None:
            settings_target_c = self._settings().get("settempr_c")
            if isinstance(settings_target_c, (float, int)) and is_target_match(
                self._optimistic_target_c, settings_target_c
            ):
                self._optimistic_target_c = None
                self._optimistic_refreshes_remaining = 0
            else:
                self._optimistic_refreshes_remaining = max(
                    0, self._optimistic_refreshes_remaining - 1
                )
                if self._optimistic_refreshes_remaining == 0:
                    self._optimistic_target_c = None
        super()._handle_coordinator_update()

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

    def _set_temperature_enabled(self) -> bool:
        return is_control_enabled(
            key=CONF_ENABLE_SET_TEMPERATURE,
            data=self._entry.data,
            options=self._entry.options,
            default=DEFAULT_ENABLE_SET_TEMPERATURE,
        )

    def _heat_control_enabled(self) -> bool:
        return is_control_enabled(
            key=CONF_ENABLE_HEAT_CONTROL,
            data=self._entry.data,
            options=self._entry.options,
            default=DEFAULT_ENABLE_HEAT_CONTROL,
        )
