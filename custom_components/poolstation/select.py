"""Support for Poolstation relay select (off/auto/on)."""
from __future__ import annotations

from pypoolstation import Pool, Relay

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PoolstationDataUpdateCoordinator
from .const import COORDINATORS, DEVICES, DOMAIN
from .entity import PoolEntity

# API values returned by the Poolstation API for relay state
# Only "0" (off) and "1" (on) are well-defined.
# Any other value ("A", "2", "9", etc.) is treated as AUTO.
RELAY_MODE_OFF = "0"
RELAY_MODE_ON = "1"

# HA select option labels
OPTION_OFF = "off"
OPTION_AUTO = "auto"
OPTION_ON = "on"

RELAY_OPTIONS = [OPTION_OFF, OPTION_AUTO, OPTION_ON]

# Mapping from HA option → API value sent to the API
OPTION_TO_API = {
    OPTION_OFF: RELAY_MODE_OFF,
    OPTION_AUTO: "A",   # send "A" to the API when setting AUTO
    OPTION_ON: RELAY_MODE_ON,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the pool relay select entities."""
    pools = hass.data[DOMAIN][config_entry.entry_id][DEVICES]
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]
    entities = []
    for pool_id, pool in pools.items():
        coordinator = coordinators[pool_id]
        for relay in pool.relays:
            entities.append(PoolRelaySelect(pool, coordinator, relay))

    async_add_entities(entities)


class PoolRelaySelect(PoolEntity, SelectEntity):
    """Representation of a pool relay as a select entity (off/auto/on)."""

    _attr_options = RELAY_OPTIONS

    def __init__(
        self, pool: Pool, coordinator: PoolstationDataUpdateCoordinator, relay: Relay
    ) -> None:
        """Initialize the pool relay select."""
        super().__init__(pool, coordinator, f" Relay {relay.name} Mode")
        self.relay = relay
        self._attr_current_option = self._raw_to_option(relay.raw_state)

    @staticmethod
    def _raw_to_option(raw_state: str | None) -> str:
        """Convert raw API state to HA option.
        '0' → off, '1' → on, anything else → auto.
        """
        s = str(raw_state) if raw_state is not None else "0"
        if s == "1":
            return OPTION_ON
        if s == "0":
            return OPTION_OFF
        return OPTION_AUTO  # "A", "2", "9", or any unknown value

    @property
    def current_option(self) -> str:
        """Return the current selected option."""
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Change the relay mode."""
        api_value = OPTION_TO_API.get(option, RELAY_MODE_OFF)
        await self.relay.set_mode(api_value)
        self._attr_current_option = option
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_current_option = self._raw_to_option(self.relay.raw_state)
        self.async_write_ha_state()
