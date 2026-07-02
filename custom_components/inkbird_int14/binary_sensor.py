from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_NAME, DOMAIN


@dataclass(frozen=True)
class StateDescription:
    key: str
    name: str
    device_class: str | None = None
    transform: Callable[[Any], bool | None] | None = None
    enabled_default: bool = False


PROBE_STATES = [
    StateDescription("connect", "Connected", "connectivity", enabled_default=True),
    StateDescription("charging", "Charging", "battery_charging", enabled_default=True),
    StateDescription("paired", "Paired", enabled_default=True),
    StateDescription("pair_request", "Pair Request"),
    StateDescription("internal_low_alarm", "Internal Low Alarm", "problem"),
    StateDescription("internal_high_alarm", "Internal High Alarm", "problem"),
    StateDescription("internal_over_high_alarm", "Internal Over High Alarm", "problem"),
    StateDescription("internal_over_low_alarm", "Internal Over Low Alarm", "problem"),
    StateDescription("advance_alarm", "Advance Alarm", "problem"),
    StateDescription("ambient_over_high_alarm", "Ambient Over High Alarm", "problem"),
    StateDescription("ambient_over_low_alarm", "Ambient Over Low Alarm", "problem"),
    StateDescription("battery_alarm", "Battery Alarm", "problem", enabled_default=True),
    StateDescription("battery_report_suspect", "Battery Report Suspect", "problem"),
    StateDescription("timer_alarm", "Timer Alarm", "problem", enabled_default=True),
    StateDescription("timer_switch", "Timer Enabled", enabled_default=True),
]

BASE_STATES = [
    StateDescription("ble_enabled", "BLE Transport Enabled", enabled_default=True),
    StateDescription("ble_connected", "BLE Connected", "connectivity", enabled_default=True),
    StateDescription("cloud_enabled", "Cloud History Enabled", enabled_default=True),
    StateDescription("cloud_available", "Cloud History Data Available", "connectivity"),
    StateDescription("battery_data_stale", "Battery Data Stale", "problem", enabled_default=True),
    StateDescription("battery_report_suspect", "Battery Report Suspect", "problem"),
    StateDescription("base_battery_report_suspect", "Base Battery Report Suspect", "problem"),
    StateDescription("probe_battery_report_suspect", "Probe Battery Report Suspect", "problem"),
    StateDescription("sound_enabled", "Sound Enabled", enabled_default=True),
    StateDescription("dev_mute", "Muted", enabled_default=True),
    StateDescription("base_charging", "Base Charging", "battery_charging", enabled_default=True),
    StateDescription("wifi_switch", "Wi-Fi Enabled", enabled_default=True),
    StateDescription("wifi_state", "Wi-Fi Connected", "connectivity", lambda value: None if value is None else bool(value), True),
    StateDescription("verify", "Verified"),
    StateDescription("device_over_high_temp_alarm", "Device Over High Temperature Alarm", "problem"),
    StateDescription("device_over_low_temp_alarm", "Device Over Low Temperature Alarm", "problem"),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    base_name = entry.data[CONF_NAME]
    entities: list[BinarySensorEntity] = []
    for probe in range(1, runtime.probe_count + 1):
        for description in PROBE_STATES:
            entities.append(Int14ProbeStateBinarySensor(runtime, base_name, probe, description))
    for description in BASE_STATES:
        entities.append(Int14BaseStateBinarySensor(runtime, base_name, description))
    async_add_entities(entities)


class Int14BinarySensorBase(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime, base_name: str, description: StateDescription) -> None:
        self.runtime = runtime
        self._base_name = base_name
        self.description = description
        self._attr_device_class = description.device_class
        self._attr_entity_registry_enabled_default = description.enabled_default
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
            "model": self.runtime.device_model,
        }

    def _state_from_data(self, key: str) -> bool | None:
        value = self.runtime.data.get(key)
        if self.description.transform is not None:
            return self.description.transform(value)
        if value is None:
            return None
        return bool(value)

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class Int14ProbeStateBinarySensor(Int14BinarySensorBase):
    def __init__(self, runtime, base_name: str, probe: int, description: StateDescription) -> None:
        super().__init__(runtime, base_name, description)
        self.probe = probe
        self._attr_unique_id = f"{runtime.address}_probe_{probe}_{description.key}"
        self._attr_name = f"Probe {probe} {description.name}"

    @property
    def is_on(self):
        return self._state_from_data(f"probe_{self.probe}_{self.description.key}")


class Int14BaseStateBinarySensor(Int14BinarySensorBase):
    def __init__(self, runtime, base_name: str, description: StateDescription) -> None:
        super().__init__(runtime, base_name, description)
        self._attr_unique_id = f"{runtime.address}_{description.key}"
        self._attr_name = description.name

    @property
    def is_on(self):
        return self._state_from_data(self.description.key)
