from __future__ import annotations

import time
from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_NAME, DOMAIN
from .models import TemperatureChannel

BATTERY_STALE_SECONDS = 6 * 60 * 60


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    base_name = entry.data[CONF_NAME]
    entities: list[SensorEntity] = []
    if runtime.profile.has_live_runtime_data:
        for probe_layout in runtime.profile.probe_layout:
            probe = probe_layout.index
            for channel in probe_layout.live_temperature_channels:
                entities.append(Int14TempSensor(runtime, base_name, probe, channel))
            if runtime.profile.write_support != "not_supported":
                entities.append(Int14TargetTempSensor(runtime, base_name, probe, "high"))
                entities.append(Int14TargetTempSensor(runtime, base_name, probe, "low"))
                entities.append(Int14DiagnosticValueSensor(runtime, base_name, probe, DIAGNOSTIC_DESCRIPTIONS["target_mode"]))
                entities.append(Int14DiagnosticValueSensor(runtime, base_name, probe, DIAGNOSTIC_DESCRIPTIONS["target_food_index"]))
                entities.append(Int14DiagnosticValueSensor(runtime, base_name, probe, DIAGNOSTIC_DESCRIPTIONS["target_degree_code"]))
            entities.append(Int14BatterySensor(runtime, base_name, probe))
            if runtime.profile.write_support != "not_supported":
                entities.append(Int14AdvanceValueSensor(runtime, base_name, probe))
                entities.append(Int14DiagnosticValueSensor(runtime, base_name, probe, DIAGNOSTIC_DESCRIPTIONS["timer_cd_mode"]))
                entities.append(Int14DiagnosticValueSensor(runtime, base_name, probe, DIAGNOSTIC_DESCRIPTIONS["timer_start_epoch_s"]))
                entities.append(Int14DiagnosticValueSensor(runtime, base_name, probe, DIAGNOSTIC_DESCRIPTIONS["timer_end_epoch_s"]))
                for channel in probe_layout.live_temperature_channels:
                    entities.append(Int14CalibrationSensor(runtime, base_name, probe, channel.data_key, channel.live_entity_name))
        if runtime.profile.supports_base_temperature:
            entities.append(Int14BaseTempSensor(runtime, base_name))
        entities.append(Int14BaseBatterySensor(runtime, base_name))
    for description in BASE_DIAGNOSTIC_DESCRIPTIONS:
        entities.append(Int14BaseDiagnosticValueSensor(runtime, base_name, description))
    async_add_entities(entities)


class Int14SensorBase(SensorEntity):
    _attr_has_entity_name = True

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
            "model": self.runtime.device_model,
        }

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class Int14TempSensor(Int14SensorBase):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, runtime, base_name: str, probe: int, channel: TemperatureChannel) -> None:
        super().__init__(runtime, base_name)
        self.probe = probe
        self.channel = channel
        self.data_key = channel.data_key
        entity_key = channel.live_entity_key
        self._attr_translation_key = f"probe_{probe}_{entity_key}_temperature"
        self._attr_unique_id = f"{runtime.address}_probe_{probe}_{entity_key}_temp"
        self._attr_name = f"Probe {probe} {channel.live_entity_name} Temperature"

    @property
    def native_value(self):
        value = self.runtime.data.get(f"probe_{self.probe}_{self.data_key}_f_tenths")
        if value in {None, 32766, 32767, 32768}:
            return None
        return value / 10


class Int14BatterySensor(Int14SensorBase):
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, runtime, base_name: str, probe: int) -> None:
        super().__init__(runtime, base_name)
        self.probe = probe
        self._attr_unique_id = f"{runtime.address}_probe_{probe}_battery"
        self._attr_name = f"Probe {probe} Battery"

    @property
    def available(self) -> bool:
        return not battery_is_stale(self.runtime.data) and self.native_value is not None

    @property
    def native_value(self):
        return self.runtime.data.get(f"probe_{self.probe}_battery")

    @property
    def extra_state_attributes(self):
        return {
            "report_suspect": bool(self.runtime.data.get(f"probe_{self.probe}_battery_report_suspect")),
            "report_quality": self.runtime.data.get("battery_report_quality"),
        }


class Int14TargetTempSensor(Int14SensorBase):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, runtime, base_name: str, probe: int, kind: str) -> None:
        super().__init__(runtime, base_name)
        self.probe = probe
        self.kind = kind
        self._attr_unique_id = f"{runtime.address}_probe_{probe}_target_{kind}_temp"
        self._attr_name = f"Probe {probe} Target {kind.title()} Temperature"

    @property
    def native_value(self):
        mode = self.runtime.data.get(f"probe_{self.probe}_target_mode")
        if self.kind == "high" and mode not in {"high", "range"}:
            return None
        if self.kind == "low" and mode not in {"low", "range"}:
            return None
        value = self.runtime.data.get(f"probe_{self.probe}_target_{self.kind}_f_tenths")
        if value in {None, 32766, 32767, 32768}:
            return None
        return value / 10


class Int14AdvanceValueSensor(Int14SensorBase):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, runtime, base_name: str, probe: int) -> None:
        super().__init__(runtime, base_name)
        self.probe = probe
        self._attr_unique_id = f"{runtime.address}_probe_{probe}_advance_value"
        self._attr_name = f"Probe {probe} Advance Value"

    @property
    def native_value(self):
        return self.runtime.data.get(f"probe_{self.probe}_advance_value")


@dataclass(frozen=True)
class DiagnosticDescription:
    key: str
    name: str
    native_unit: str | None = None
    state_class: SensorStateClass | None = None
    transform: str | None = None
    enabled_default: bool = False


DIAGNOSTIC_DESCRIPTIONS = {
    "target_mode": DiagnosticDescription("target_mode", "Target Mode"),
    "target_food_index": DiagnosticDescription(
        "target_food_index",
        "Target Food Index",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "target_degree_code": DiagnosticDescription("target_degree_code", "Target Degree Code"),
    "timer_cd_mode": DiagnosticDescription("timer_cd_mode", "Timer Mode", transform="timer_mode"),
    "timer_start_epoch_s": DiagnosticDescription(
        "timer_start_epoch_s",
        "Timer Start Epoch",
        native_unit="s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "timer_end_epoch_s": DiagnosticDescription(
        "timer_end_epoch_s",
        "Timer End Epoch",
        native_unit="s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
}

BASE_DIAGNOSTIC_DESCRIPTIONS = [
    DiagnosticDescription("transport_mode", "Transport Mode State", enabled_default=True),
    DiagnosticDescription("model", "Configured Model", enabled_default=True),
    DiagnosticDescription("model_profile", "Configured Model Profile"),
    DiagnosticDescription("model_support_status", "Model Support Status", enabled_default=True),
    DiagnosticDescription("probe_count", "Physical Probe Count", state_class=SensorStateClass.MEASUREMENT, enabled_default=True),
    DiagnosticDescription(
        "temperature_channel_count",
        "Expected Temperature Channel Count",
        state_class=SensorStateClass.MEASUREMENT,
        enabled_default=True,
    ),
    DiagnosticDescription(
        "live_temperature_channel_count",
        "Mapped Live Temperature Channel Count",
        state_class=SensorStateClass.MEASUREMENT,
        enabled_default=True,
    ),
    DiagnosticDescription("probe_layout_summary", "Probe Layout", enabled_default=True),
    DiagnosticDescription("active_transport", "Active Transport", enabled_default=True),
    DiagnosticDescription("local_lan_configured", "Local LAN Configured", enabled_default=True),
    DiagnosticDescription("local_lan_enabled", "Local LAN Enabled", enabled_default=True),
    DiagnosticDescription("local_lan_available", "Local LAN Available", enabled_default=True),
    DiagnosticDescription(
        "local_lan_last_poll_epoch_s",
        "Local LAN Last Poll Epoch",
        native_unit="s",
        state_class=SensorStateClass.MEASUREMENT,
        enabled_default=True,
    ),
    DiagnosticDescription("local_lan_status_ok", "Local LAN Status OK", enabled_default=True),
    DiagnosticDescription("local_lan_update_ok", "Local LAN Update OK", enabled_default=True),
    DiagnosticDescription("local_lan_dp_count", "Local LAN DP Count", state_class=SensorStateClass.MEASUREMENT),
    DiagnosticDescription("local_lan_dp_keys", "Local LAN DP Keys"),
    DiagnosticDescription("local_lan_last_error", "Local LAN Last Error"),
    DiagnosticDescription("local_lan_last_err", "Local LAN Last Error Code"),
    DiagnosticDescription(
        "last_lan_update_epoch_s",
        "Last LAN Update Epoch",
        native_unit="s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticDescription("last_lan_dp_keys", "Last LAN DP Keys"),
    DiagnosticDescription(
        "last_lan_write_epoch_s",
        "Last LAN Write Epoch",
        native_unit="s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticDescription("last_lan_write_dps", "Last LAN Write DPS"),
    DiagnosticDescription("last_lan_write_ok", "Last LAN Write OK"),
    DiagnosticDescription("last_lan_write_error", "Last LAN Write Error"),
    DiagnosticDescription("last_lan_write_err", "Last LAN Write Error Code"),
    DiagnosticDescription("direct_cloud_history_enabled", "Cloud History Enabled"),
    DiagnosticDescription("direct_cloud_history_available", "Cloud History Available"),
    DiagnosticDescription(
        "direct_cloud_last_poll_epoch_s",
        "Direct Cloud Last Poll Epoch",
        native_unit="s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticDescription("direct_cloud_status", "Direct Cloud Status"),
    DiagnosticDescription("direct_cloud_history_count", "Direct Cloud History Count", state_class=SensorStateClass.MEASUREMENT),
    DiagnosticDescription("direct_cloud_last_dateline", "Direct Cloud Last Dateline"),
    DiagnosticDescription("direct_cloud_last_error", "Direct Cloud Last Error"),
    DiagnosticDescription("last_transport", "Last Parsed Transport"),
    DiagnosticDescription(
        "last_ble_update_epoch_s",
        "Last BLE Update Epoch",
        native_unit="s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticDescription(
        "last_ble_write_epoch_s",
        "Last BLE Write Epoch",
        native_unit="s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticDescription("last_ble_write_hex", "Last BLE Write Hex"),
    DiagnosticDescription("last_ble_write_ok", "Last BLE Write OK"),
    DiagnosticDescription("last_ble_error", "Last BLE Error"),
    DiagnosticDescription("ble_auth_ok", "BLE Auth OK", enabled_default=True),
    DiagnosticDescription("last_ble_auth_error", "Last BLE Auth Error", enabled_default=True),
    DiagnosticDescription(
        "last_ble_auth_request_epoch_s",
        "Last BLE Auth Request Epoch",
        native_unit="s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticDescription(
        "last_ble_auth_challenge_epoch_s",
        "Last BLE Auth Challenge Epoch",
        native_unit="s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticDescription(
        "last_ble_auth_response_epoch_s",
        "Last BLE Auth Response Epoch",
        native_unit="s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticDescription(
        "last_ble_auth_ack_epoch_s",
        "Last BLE Auth Ack Epoch",
        native_unit="s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticDescription("last_ble_auth_challenge_len", "Last BLE Auth Challenge Length", state_class=SensorStateClass.MEASUREMENT),
    DiagnosticDescription("last_ble_auth_response_len", "Last BLE Auth Response Length", state_class=SensorStateClass.MEASUREMENT),
    DiagnosticDescription("last_ble_auth_ack_hex", "Last BLE Auth Ack"),
    DiagnosticDescription(
        "last_cloud_update_epoch_s",
        "Last Cloud Update Epoch",
        native_unit="s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticDescription("last_cloud_dp_keys", "Last Cloud DP Keys"),
    DiagnosticDescription("unit", "Temperature Unit", enabled_default=True),
    DiagnosticDescription("display_light", "Display Light", state_class=SensorStateClass.MEASUREMENT, enabled_default=True),
    DiagnosticDescription(
        "last_battery_update_epoch_s",
        "Last Battery Update Epoch",
        native_unit="s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticDescription(
        "battery_age_seconds",
        "Battery Data Age",
        native_unit="s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticDescription("last_battery_transport", "Last Battery Transport"),
    DiagnosticDescription("battery_report_quality", "Battery Report Quality", enabled_default=True),
    DiagnosticDescription("last_battery_len", "Last Battery Length", state_class=SensorStateClass.MEASUREMENT),
    DiagnosticDescription("last_battery_prefix", "Last Battery Raw Prefix"),
    DiagnosticDescription("last_sender", "Last BLE Sender"),
    DiagnosticDescription("last_raw_len", "Last Raw Length", state_class=SensorStateClass.MEASUREMENT),
    DiagnosticDescription("last_raw_prefix", "Last Raw Prefix"),
    DiagnosticDescription("last_ff02_len", "Last FF02 Length", state_class=SensorStateClass.MEASUREMENT),
    DiagnosticDescription("last_ff02_prefix", "Last FF02 Prefix"),
]


class Int14DiagnosticValueSensor(Int14SensorBase):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime, base_name: str, probe: int, description: DiagnosticDescription) -> None:
        super().__init__(runtime, base_name)
        self.probe = probe
        self.description = description
        self._attr_unique_id = f"{runtime.address}_probe_{probe}_{description.key}"
        self._attr_name = f"Probe {probe} {description.name}"
        self._attr_native_unit_of_measurement = description.native_unit
        self._attr_state_class = description.state_class
        self._attr_entity_registry_enabled_default = description.enabled_default

    @property
    def native_value(self):
        if self.description.key in {"timer_cd_mode", "timer_start_epoch_s", "timer_end_epoch_s"}:
            if self.runtime.data.get(f"probe_{self.probe}_timer_switch") is False:
                return None
        value = self.runtime.data.get(f"probe_{self.probe}_{self.description.key}")
        if self.description.transform == "timer_mode":
            if value is None:
                return None
            return "countdown" if value else "countup"
        return value


class Int14BaseDiagnosticValueSensor(Int14SensorBase):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime, base_name: str, description: DiagnosticDescription) -> None:
        super().__init__(runtime, base_name)
        self.description = description
        self._attr_unique_id = f"{runtime.address}_{description.key}"
        self._attr_name = description.name
        self._attr_native_unit_of_measurement = description.native_unit
        self._attr_state_class = description.state_class
        self._attr_entity_registry_enabled_default = description.enabled_default

    @property
    def native_value(self):
        return self.runtime.data.get(self.description.key)


class Int14CalibrationSensor(Int14SensorBase):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, runtime, base_name: str, probe: int, kind: str, channel_name: str | None = None) -> None:
        super().__init__(runtime, base_name)
        self.probe = probe
        self.kind = kind
        self._attr_unique_id = f"{runtime.address}_probe_{probe}_{kind}_calibration"
        self._attr_name = f"Probe {probe} {channel_name or kind.title()} Calibration"

    @property
    def native_value(self):
        value = self.runtime.data.get(f"probe_{self.probe}_{self.kind}_calibration_c")
        if value is None:
            return None
        return round(value, 2)


class Int14BaseTempSensor(Int14SensorBase):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_name = "Base Temperature"

    def __init__(self, runtime, base_name: str) -> None:
        super().__init__(runtime, base_name)
        self._attr_unique_id = f"{runtime.address}_base_temp"

    @property
    def native_value(self):
        value = self.runtime.data.get("base_temp_f_tenths")
        if value in {None, 32766, 32767, 32768}:
            return None
        return value / 10


class Int14BaseBatterySensor(Int14SensorBase):
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_name = "Base Battery"

    def __init__(self, runtime, base_name: str) -> None:
        super().__init__(runtime, base_name)
        self._attr_unique_id = f"{runtime.address}_base_battery"

    @property
    def available(self) -> bool:
        return not battery_is_stale(self.runtime.data) and self.native_value is not None

    @property
    def native_value(self):
        return self.runtime.data.get("base_power")

    @property
    def extra_state_attributes(self):
        return {
            "report_suspect": bool(self.runtime.data.get("base_battery_report_suspect")),
            "report_quality": self.runtime.data.get("battery_report_quality"),
        }


def battery_is_stale(data: dict) -> bool:
    if bool(data.get("battery_data_stale")):
        return True
    last = data.get("last_battery_update_epoch_s")
    if last is None:
        return True
    return int(time.time()) - int(last) > BATTERY_STALE_SECONDS
