from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_NAME, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    entities = []
    if runtime.profile.supports_ble_snapshot:
        entities.append(Int14RequestInitButton(runtime, entry.data[CONF_NAME]))
    if runtime.profile.supports_ble_diagnostics:
        entities.append(Int14BleDiagnosticsButton(runtime, entry.data[CONF_NAME]))
    async_add_entities(entities)


class Int14RequestInitButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Request Snapshot"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime, base_name: str) -> None:
        self.runtime = runtime
        self._base_name = base_name
        self._attr_unique_id = f"{runtime.address}_request_snapshot"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.runtime.address.upper())},
            "name": self._base_name,
            "manufacturer": "Inkbird",
            "model": self.runtime.device_model,
        }

    async def async_press(self) -> None:
        await self.runtime.request_init()


class Int14BleDiagnosticsButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Capture BLE Diagnostics"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime, base_name: str) -> None:
        self.runtime = runtime
        self._base_name = base_name
        self._attr_unique_id = f"{runtime.address}_capture_ble_diagnostics"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.runtime.address.upper())},
            "name": self._base_name,
            "manufacturer": "Inkbird",
            "model": self.runtime.device_model,
        }

    async def async_press(self) -> None:
        await self.runtime.request_ble_diagnostics()
