from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_NAME, DOMAIN

DEGREE_CODE_TO_INDEX = {
    "01": 1,
    "03": 2,
    "05": 3,
    "07": 4,
    "0a": 5,
}
DEFAULT_PRE_ALARM_VALUES = (18, 18, 72, 18)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    base_name = entry.data[CONF_NAME]
    entities: list[NumberEntity] = [Int14DisplayLightNumber(runtime, base_name)]
    for probe in range(1, 5):
        entities.append(Int14TargetHighNumber(runtime, base_name, probe))
        entities.append(Int14CalibrationNumber(runtime, base_name, probe, "internal"))
        entities.append(Int14CalibrationNumber(runtime, base_name, probe, "ambient"))
        entities.append(Int14PreAlarmNumber(runtime, base_name, probe))
    async_add_entities(entities)


class Int14NumberBase(NumberEntity):
    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX

    def __init__(self, runtime, base_name: str) -> None:
        self.runtime = runtime
        self._base_name = base_name
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

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class Int14DisplayLightNumber(Int14NumberBase):
    _attr_name = "Display Light Command"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, runtime, base_name: str) -> None:
        super().__init__(runtime, base_name)
        self._attr_unique_id = f"{runtime.address}_display_light_command"

    @property
    def native_value(self):
        return self.runtime.data.get("display_light")

    async def async_set_native_value(self, value: float) -> None:
        await self.runtime.write_display_light(round(value))


class Int14TargetHighNumber(Int14NumberBase):
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_native_min_value = 32
    _attr_native_max_value = 572
    _attr_native_step = 1

    def __init__(self, runtime, base_name: str, probe: int) -> None:
        super().__init__(runtime, base_name)
        self.probe = probe
        self._attr_unique_id = f"{runtime.address}_probe_{probe}_target_high_command"
        self._attr_name = f"Probe {probe} Target High Command"

    @property
    def native_value(self):
        value = self.runtime.data.get(f"probe_{self.probe}_target_high_f_tenths")
        if value in {None, 32766, 32767, 32768}:
            return None
        return value / 10

    async def async_set_native_value(self, value: float) -> None:
        degree_code = self.runtime.data.get(f"probe_{self.probe}_target_degree_code")
        degree_index = DEGREE_CODE_TO_INDEX.get(str(degree_code).lower(), 0)
        food_index = self.runtime.data.get(f"probe_{self.probe}_target_food_index")
        if food_index is None:
            food_index = -1
        await self.runtime.write_target_high(
            probe=self.probe,
            high_tenths=round(value * 10),
            degree_index=degree_index,
            food_index=int(food_index),
        )


class Int14CalibrationNumber(Int14NumberBase):
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = -10
    _attr_native_max_value = 10
    _attr_native_step = 0.1
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, runtime, base_name: str, probe: int, channel: str) -> None:
        super().__init__(runtime, base_name)
        self.probe = probe
        self.channel = channel
        self._attr_unique_id = f"{runtime.address}_probe_{probe}_{channel}_calibration_command"
        self._attr_name = f"Probe {probe} {channel.title()} Calibration Command"

    @property
    def native_value(self):
        return self.runtime.data.get(f"probe_{self.probe}_{self.channel}_calibration_c")

    async def async_set_native_value(self, value: float) -> None:
        await self.runtime.write_calibration(
            probe=self.probe,
            channel=self.channel,
            c_value=value,
        )


class Int14PreAlarmNumber(Int14NumberBase):
    _attr_name = None
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1

    def __init__(self, runtime, base_name: str, probe: int) -> None:
        super().__init__(runtime, base_name)
        self.probe = probe
        self._attr_unique_id = f"{runtime.address}_probe_{probe}_advance_command"
        self._attr_name = f"Probe {probe} Advance Command"

    @property
    def native_value(self):
        return self.runtime.data.get(f"probe_{self.probe}_advance_value")

    async def async_set_native_value(self, value: float) -> None:
        values = []
        for index in range(1, 5):
            current = self.runtime.data.get(f"probe_{index}_advance_value")
            fallback = DEFAULT_PRE_ALARM_VALUES[index - 1]
            values.append(round(value) if index == self.probe else int(current if current is not None else fallback))
        await self.runtime.write_pre_alarm(self.probe, values)
