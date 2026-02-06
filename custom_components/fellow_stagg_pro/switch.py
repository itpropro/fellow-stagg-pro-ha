"""Switch entity for explicit kettle power control."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FellowStaggProConfigEntry, get_runtime_data
from .const import (
    CONF_ENABLE_HEAT_CONTROL,
    COORDINATOR_DATA_FWINFO,
    COORDINATOR_DATA_STATE,
    DEFAULT_ENABLE_HEAT_CONTROL,
    DOMAIN,
    NAME,
)
from .control import derive_power_state
from .coordinator import FellowStaggProDataUpdateCoordinator
from .guardrails import is_control_enabled


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FellowStaggProConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up power switch entity."""
    coordinator = get_runtime_data(hass, entry).coordinator
    async_add_entities([FellowStaggProPowerSwitch(coordinator, entry)])


class FellowStaggProPowerSwitch(
    CoordinatorEntity[FellowStaggProDataUpdateCoordinator], SwitchEntity
):
    """Expose kettle heat power as a dedicated switch."""

    _attr_has_entity_name = True
    _attr_name = "Power"
    _attr_icon = "mdi:kettle-steam"
    _optimistic_max_updates = 4

    def __init__(
        self,
        coordinator: FellowStaggProDataUpdateCoordinator,
        entry: FellowStaggProConfigEntry,
    ) -> None:
        """Initialize power switch."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}-power-switch"
        self._optimistic_is_on: bool | None = None
        self._optimistic_updates_remaining = 0

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
    def is_on(self) -> bool:
        """Return current on/off state."""
        if self._optimistic_is_on is not None:
            return self._optimistic_is_on

        return bool(derive_power_state(self._state()))

    async def async_turn_on(self, **kwargs) -> None:
        """Turn kettle heating on."""
        if not self._heat_control_enabled():
            raise HomeAssistantError(
                "Heat control is disabled. Enable it in integration options."
            )

        self._set_optimistic_state(True)
        try:
            await self.coordinator.api.async_turn_on()
        except Exception:
            self._clear_optimistic_state()
            raise

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn kettle heating off."""
        if not self._heat_control_enabled():
            raise HomeAssistantError(
                "Heat control is disabled. Enable it in integration options."
            )

        self._set_optimistic_state(False)
        try:
            await self.coordinator.api.async_turn_off()
        except Exception:
            self._clear_optimistic_state()
            raise

        await self.coordinator.async_request_refresh()

    def _handle_coordinator_update(self) -> None:
        """Reconcile optimistic state with polled telemetry."""
        derived_state = derive_power_state(self._state())

        if self._optimistic_is_on is not None:
            if derived_state is self._optimistic_is_on:
                self._clear_optimistic_state()
            else:
                self._optimistic_updates_remaining -= 1
                if self._optimistic_updates_remaining <= 0:
                    self._clear_optimistic_state()

        super()._handle_coordinator_update()

    def _state(self) -> dict:
        return self.coordinator.data.get(COORDINATOR_DATA_STATE, {})

    def _heat_control_enabled(self) -> bool:
        return is_control_enabled(
            key=CONF_ENABLE_HEAT_CONTROL,
            data=self._entry.data,
            options=self._entry.options,
            default=DEFAULT_ENABLE_HEAT_CONTROL,
        )

    def _set_optimistic_state(self, value: bool) -> None:
        self._optimistic_is_on = value
        self._optimistic_updates_remaining = self._optimistic_max_updates
        self.async_write_ha_state()

    def _clear_optimistic_state(self) -> None:
        self._optimistic_is_on = None
        self._optimistic_updates_remaining = 0
