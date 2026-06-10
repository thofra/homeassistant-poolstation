"""Support for Poolstation switches."""
from __future__ import annotations

from typing import Any

from pypoolstation import Pool, Relay

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PoolstationDataUpdateCoordinator
from .const import COORDINATORS, DEVICES, DOMAIN
from .entity import PoolEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the pool relays."""
    pools = hass.data[DOMAIN][config_entry.entry_id][DEVICES]
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]
    entities = []
    for pool_id, pool in pools.items():
        coordinator = coordinators[pool_id]
        for relay in pool.relays:
            entities.append(PoolRelaySwitch(pool, coordinator, relay))

    async_add_entities(entities)


class PoolRelaySwitch(PoolEntity, SwitchEntity):
    """Representation of a pool relay switch.

    Note: Use the companion PoolRelaySelect entity for full off/auto/on control.
    This switch maps AUTO and ON both to 'on', and OFF to 'off'.
    Turning this switch OFF sets the relay to OFF mode.
    Turning this switch ON sets the relay to ON mode (not AUTO).
    """

    def __init__(
        self, pool: Pool, coordinator: PoolstationDataUpdateCoordinator, relay: Relay
    ) -> None:
        """Initialize the pool relay switch."""
        super().__init__(pool, coordinator, f" Relay {relay.name}")
        self.relay = relay
        # FIX: treat AUTO ("A") and ON ("1") both as on=True
        self._attr_is_on = self._raw_to_bool(relay.raw_state)

    @staticmethod
    def _raw_to_bool(raw_state: str | None) -> bool:
        """Convert raw API state to bool. AUTO and ON are both considered 'on'."""
        return str(raw_state) in ("1", "A") if raw_state is not None else False

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes including the actual relay mode."""
        return {
            "mode": self.relay.raw_state,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the relay on (sets to ON mode, not AUTO)."""
        await self.relay.set_mode("1")
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the relay off."""
        await self.relay.set_mode("0")
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # FIX: AUTO mode ("A") is now correctly treated as on=True
        self._attr_is_on = self._raw_to_bool(self.relay.raw_state)
        self.async_write_ha_state()
