from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_NAME, DOMAIN, TRANSPORT_MODES


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([Int14TransportModeSelect(runtime, entry)])


class Int14TransportModeSelect(SelectEntity):
    _attr_has_entity_name = True
    _attr_name = "Transport Mode"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(TRANSPORT_MODES)

    def __init__(self, runtime, entry: ConfigEntry) -> None:
        self.runtime = runtime
        self.entry = entry
        self._base_name = entry.data[CONF_NAME]
        self._attr_unique_id = f"{runtime.address}_transport_mode"
        self._remove_listener = None

    async def async_added_to_hass(self) -> None:
        self._remove_listener = self.runtime.add_listener(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener is not None:
            self._remove_listener()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.runtime.address.upper())},
            "name": self._base_name,
            "manufacturer": "Inkbird",
            "model": "INT-14-BW",
        }

    @property
    def current_option(self) -> str:
        return self.runtime.transport_mode

    async def async_select_option(self, option: str) -> None:
        await self.runtime.set_transport_mode(option)
        self.async_write_ha_state()

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
