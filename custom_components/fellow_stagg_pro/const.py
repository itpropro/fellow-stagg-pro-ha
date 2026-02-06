"""Constants for Fellow Stagg Pro."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "fellow_stagg_pro"
NAME = "Fellow Stagg Pro"

CONF_SCAN_INTERVAL = "scan_interval"
CONF_ENABLE_HEAT_CONTROL = "enable_heat_control"
CONF_ENABLE_SET_TEMPERATURE = "enable_set_temperature"

DEFAULT_PORT = 80
DEFAULT_SCAN_INTERVAL = 15
DEFAULT_ENABLE_HEAT_CONTROL = False
DEFAULT_ENABLE_SET_TEMPERATURE = False
MIN_TARGET_TEMP_C = 40.0
MAX_TARGET_TEMP_C = 100.0
TARGET_TEMP_STEP_C = 0.5

PLATFORMS: list[Platform] = [Platform.WATER_HEATER, Platform.SENSOR]

COORDINATOR_DATA_STATE = "state"
COORDINATOR_DATA_SETTINGS = "settings"
COORDINATOR_DATA_FWINFO = "fwinfo"
