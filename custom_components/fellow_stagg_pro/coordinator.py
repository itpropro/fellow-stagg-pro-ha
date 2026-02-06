"""Data coordinator for Fellow Stagg Pro."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FellowStaggProApi, FellowStaggProApiError
from .const import COORDINATOR_DATA_FWINFO, COORDINATOR_DATA_SETTINGS, COORDINATOR_DATA_STATE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class FellowStaggProDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate updates from kettle endpoints."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: FellowStaggProApi,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self._fwinfo_cache: dict[str, Any] | None = None
        self._refresh_count = 0

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from kettle."""
        try:
            state_task = self.api.async_get_state()
            settings_task = self.api.async_get_settings()
            state, settings = await asyncio.gather(state_task, settings_task)

            self._refresh_count += 1
            if self._fwinfo_cache is None or self._refresh_count % 60 == 0:
                self._fwinfo_cache = await self.api.async_get_fwinfo()

            return {
                COORDINATOR_DATA_STATE: state,
                COORDINATOR_DATA_SETTINGS: settings,
                COORDINATOR_DATA_FWINFO: self._fwinfo_cache or {},
            }
        except FellowStaggProApiError as err:
            raise UpdateFailed(str(err)) from err
