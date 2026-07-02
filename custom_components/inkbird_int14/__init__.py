from __future__ import annotations

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from .cloud import build_cloud_history_config_from_sources
from .const import (
    CONF_ADDRESS,
    CONF_MODEL,
    CONF_REQUEST_INIT_ON_CONNECT,
    CONF_TRANSPORT_MODE,
    DEFAULT_CLOUD_BASE_URL,
    DEFAULT_CLOUD_POLL_SECONDS,
    DOMAIN,
    TRANSPORT_MODE_AUTO,
)
from .lan import build_lan_config_from_sources
from .protocol import (
    build_calibration_command,
    build_display_light_command,
    build_pre_alarm_command,
    build_probe_pair_cancel_command,
    build_probe_pair_command,
    build_target_command,
    build_timer_command,
    build_timer_reset_command,
    build_unit_command,
)
from .runtime import Int14Runtime

PLATFORMS = ["sensor", "binary_sensor", "button", "select", "number"]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
SERVICE_SET_UNIT = "set_unit"
SERVICE_SET_DISPLAY_LIGHT = "set_display_light"
SERVICE_SET_TARGET = "set_target"
SERVICE_SET_PRE_ALARM = "set_pre_alarm"
SERVICE_SET_TIMER = "set_timer"
SERVICE_RESET_TIMER = "reset_timer"
SERVICE_SET_CALIBRATION = "set_calibration"
SERVICE_SET_UNIT_BLE = "set_unit_ble"
SERVICE_SET_DISPLAY_LIGHT_BLE = "set_display_light_ble"
SERVICE_SET_TARGET_BLE = "set_target_ble"
SERVICE_SET_PRE_ALARM_BLE = "set_pre_alarm_ble"
SERVICE_SET_TIMER_BLE = "set_timer_ble"
SERVICE_RESET_TIMER_BLE = "reset_timer_ble"
SERVICE_SET_CALIBRATION_BLE = "set_calibration_ble"
SERVICE_START_PROBE_PAIR_BLE = "start_probe_pair_ble"
SERVICE_CANCEL_PROBE_PAIR_BLE = "cancel_probe_pair_ble"


def _runtime_for_address(hass: HomeAssistant, address: str) -> Int14Runtime:
    wanted = address.upper()
    for runtime in hass.data.get(DOMAIN, {}).values():
        if runtime.address.upper() == wanted:
            return runtime
    raise HomeAssistantError(f"No Inkbird INT-14 runtime for address {wanted}")


def _runtime_for_optional_address(hass: HomeAssistant, address: str | None) -> Int14Runtime:
    if address:
        return _runtime_for_address(hass, address)
    runtimes = list(hass.data.get(DOMAIN, {}).values())
    if len(runtimes) == 1:
        return runtimes[0]
    raise HomeAssistantError("Address is required when multiple INT-14 runtimes are configured")


async def _write_runtime(awaitable, action: str) -> None:
    try:
        ok = await awaitable
    except Exception as exc:  # noqa: BLE001
        raise HomeAssistantError(f"INT-14 {action} failed: {exc}") from exc
    if not ok:
        raise HomeAssistantError(f"INT-14 {action} failed")


def _ensure_probe(runtime: Int14Runtime, probe: int) -> None:
    if probe < 1 or probe > runtime.probe_count:
        raise HomeAssistantError(f"Probe {probe} is outside the configured {runtime.profile.display_name} range")


async def _write_ble(hass: HomeAssistant, call: ServiceCall, payload: bytes) -> None:
    runtime = _runtime_for_address(hass, call.data[CONF_ADDRESS])
    try:
        ok = await runtime.write_ble_command(
            payload,
            request_readback=call.data.get("request_readback", True),
        )
    except Exception as exc:  # noqa: BLE001
        runtime.data["last_ble_error"] = str(exc)[:200]
        runtime.data["last_ble_write_hex"] = payload.hex()
        runtime.data["last_ble_write_ok"] = False
        runtime._notify_listeners()
        raise HomeAssistantError(f"INT-14 BLE write failed: {exc}") from exc
    if not ok:
        runtime.data["last_ble_error"] = "write returned false"
        runtime.data["last_ble_write_ok"] = False
        runtime._notify_listeners()
        raise HomeAssistantError("INT-14 BLE write failed")


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})

    async def handle_set_unit_ble(call: ServiceCall) -> None:
        await _write_ble(hass, call, build_unit_command(call.data["unit"]))

    async def handle_set_display_light_ble(call: ServiceCall) -> None:
        await _write_ble(hass, call, build_display_light_command(call.data["value"]))

    async def handle_set_unit(call: ServiceCall) -> None:
        runtime = _runtime_for_optional_address(hass, call.data.get(CONF_ADDRESS))
        await _write_runtime(runtime.write_unit(call.data["unit"]), "unit write")

    async def handle_set_display_light(call: ServiceCall) -> None:
        runtime = _runtime_for_optional_address(hass, call.data.get(CONF_ADDRESS))
        await _write_runtime(runtime.write_display_light(call.data["value"]), "display light write")

    async def handle_set_target(call: ServiceCall) -> None:
        runtime = _runtime_for_optional_address(hass, call.data.get(CONF_ADDRESS))
        _ensure_probe(runtime, call.data["probe"])
        await _write_runtime(
            runtime.write_target(
                probe=call.data["probe"],
                mode=call.data["mode"],
                high_tenths=call.data.get("high_tenths", 0),
                low_tenths=call.data.get("low_tenths", 0),
                degree_index=call.data.get("degree_index", 0),
                food_index=call.data.get("food_index", -1),
            ),
            "target write",
        )

    async def handle_set_pre_alarm(call: ServiceCall) -> None:
        runtime = _runtime_for_optional_address(hass, call.data.get(CONF_ADDRESS))
        _ensure_probe(runtime, call.data["probe"])
        await _write_runtime(
            runtime.write_pre_alarm(call.data["probe"], list(call.data["advance_values"])),
            "pre-alarm write",
        )

    async def handle_set_timer(call: ServiceCall) -> None:
        runtime = _runtime_for_optional_address(hass, call.data.get(CONF_ADDRESS))
        _ensure_probe(runtime, call.data["probe"])
        await _write_runtime(
            runtime.write_timer(
                probe=call.data["probe"],
                start_epoch_s=call.data["start_epoch_s"],
                end_epoch_s=call.data["end_epoch_s"],
                count_down=call.data.get("count_down", True),
            ),
            "timer write",
        )

    async def handle_reset_timer(call: ServiceCall) -> None:
        runtime = _runtime_for_optional_address(hass, call.data.get(CONF_ADDRESS))
        _ensure_probe(runtime, call.data["probe"])
        await _write_runtime(runtime.reset_timer(call.data["probe"]), "timer reset")

    async def handle_set_calibration(call: ServiceCall) -> None:
        runtime = _runtime_for_optional_address(hass, call.data.get(CONF_ADDRESS))
        _ensure_probe(runtime, call.data["probe"])
        await _write_runtime(
            runtime.write_calibration(
                probe=call.data["probe"],
                channel=call.data["channel"],
                c_value=call.data["c_value"],
            ),
            "calibration write",
        )

    async def handle_set_target_ble(call: ServiceCall) -> None:
        runtime = _runtime_for_address(hass, call.data[CONF_ADDRESS])
        _ensure_probe(runtime, call.data["probe"])
        await _write_ble(
            hass,
            call,
            build_target_command(
                probe=call.data["probe"],
                mode=call.data["mode"],
                high_tenths=call.data.get("high_tenths", 0),
                low_tenths=call.data.get("low_tenths", 0),
                degree_index=call.data.get("degree_index", 0),
                food_index=call.data.get("food_index", -1),
            ),
        )

    async def handle_set_pre_alarm_ble(call: ServiceCall) -> None:
        runtime = _runtime_for_address(hass, call.data[CONF_ADDRESS])
        _ensure_probe(runtime, call.data["probe"])
        await _write_ble(hass, call, build_pre_alarm_command(call.data["probe"], list(call.data["advance_values"])))

    async def handle_set_timer_ble(call: ServiceCall) -> None:
        runtime = _runtime_for_address(hass, call.data[CONF_ADDRESS])
        _ensure_probe(runtime, call.data["probe"])
        await _write_ble(
            hass,
            call,
            build_timer_command(
                call.data["probe"],
                call.data["start_epoch_s"],
                call.data["end_epoch_s"],
                count_down=call.data.get("count_down", True),
            ),
        )

    async def handle_reset_timer_ble(call: ServiceCall) -> None:
        runtime = _runtime_for_address(hass, call.data[CONF_ADDRESS])
        _ensure_probe(runtime, call.data["probe"])
        await _write_ble(hass, call, build_timer_reset_command(call.data["probe"]))

    async def handle_set_calibration_ble(call: ServiceCall) -> None:
        runtime = _runtime_for_address(hass, call.data[CONF_ADDRESS])
        _ensure_probe(runtime, call.data["probe"])
        await _write_ble(
            hass,
            call,
            build_calibration_command(
                probe=call.data["probe"],
                channel=call.data["channel"],
                c_value=call.data["c_value"],
            ),
        )

    async def handle_start_probe_pair_ble(call: ServiceCall) -> None:
        runtime = _runtime_for_address(hass, call.data[CONF_ADDRESS])
        _ensure_probe(runtime, call.data["probe"])
        await _write_ble(
            hass,
            call,
            build_probe_pair_command(
                call.data["probe"],
                rssi_threshold=call.data.get("rssi_threshold", -80),
            ),
        )

    async def handle_cancel_probe_pair_ble(call: ServiceCall) -> None:
        await _write_ble(
            hass,
            call,
            build_probe_pair_cancel_command(rssi_threshold=call.data.get("rssi_threshold", -80)),
        )

    common_ble_schema = {
        vol.Required(CONF_ADDRESS): str,
        vol.Optional("request_readback", default=True): bool,
    }
    common_write_schema = {
        vol.Optional(CONF_ADDRESS): str,
    }
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_UNIT,
        handle_set_unit,
        schema=vol.Schema({**common_write_schema, vol.Required("unit"): vol.In(("C", "F", "c", "f"))}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DISPLAY_LIGHT,
        handle_set_display_light,
        schema=vol.Schema({**common_write_schema, vol.Required("value"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255))}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_TARGET,
        handle_set_target,
        schema=vol.Schema(
            {
                **common_write_schema,
                vol.Required("probe"): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
                vol.Required("mode"): vol.In(("01", "10", "11")),
                vol.Optional("high_tenths", default=0): vol.Coerce(int),
                vol.Optional("low_tenths", default=0): vol.Coerce(int),
                vol.Optional("degree_index", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),
                vol.Optional("food_index", default=-1): vol.All(vol.Coerce(int), vol.Range(min=-1, max=255)),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PRE_ALARM,
        handle_set_pre_alarm,
        schema=vol.Schema(
            {
                **common_write_schema,
                vol.Required("probe"): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
                vol.Required("advance_values"): [vol.All(vol.Coerce(int), vol.Range(min=0, max=255))],
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_TIMER,
        handle_set_timer,
        schema=vol.Schema(
            {
                **common_write_schema,
                vol.Required("probe"): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
                vol.Required("start_epoch_s"): vol.Coerce(int),
                vol.Required("end_epoch_s"): vol.Coerce(int),
                vol.Optional("count_down", default=True): bool,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_TIMER,
        handle_reset_timer,
        schema=vol.Schema({**common_write_schema, vol.Required("probe"): vol.All(vol.Coerce(int), vol.Range(min=1, max=4))}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CALIBRATION,
        handle_set_calibration,
        schema=vol.Schema(
            {
                **common_write_schema,
                vol.Required("probe"): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
                vol.Required("channel"): vol.In(("internal", "ambient")),
                vol.Required("c_value"): vol.Coerce(float),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_UNIT_BLE,
        handle_set_unit_ble,
        schema=vol.Schema({**common_ble_schema, vol.Required("unit"): vol.In(("C", "F", "c", "f"))}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DISPLAY_LIGHT_BLE,
        handle_set_display_light_ble,
        schema=vol.Schema({**common_ble_schema, vol.Required("value"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255))}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_TARGET_BLE,
        handle_set_target_ble,
        schema=vol.Schema(
            {
                **common_ble_schema,
                vol.Required("probe"): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
                vol.Required("mode"): vol.In(("01", "10", "11")),
                vol.Optional("high_tenths", default=0): vol.Coerce(int),
                vol.Optional("low_tenths", default=0): vol.Coerce(int),
                vol.Optional("degree_index", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),
                vol.Optional("food_index", default=-1): vol.All(vol.Coerce(int), vol.Range(min=-1, max=255)),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PRE_ALARM_BLE,
        handle_set_pre_alarm_ble,
        schema=vol.Schema(
            {
                **common_ble_schema,
                vol.Required("probe"): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
                vol.Required("advance_values"): [vol.All(vol.Coerce(int), vol.Range(min=0, max=255))],
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_TIMER_BLE,
        handle_set_timer_ble,
        schema=vol.Schema(
            {
                **common_ble_schema,
                vol.Required("probe"): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
                vol.Required("start_epoch_s"): vol.Coerce(int),
                vol.Required("end_epoch_s"): vol.Coerce(int),
                vol.Optional("count_down", default=True): bool,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_TIMER_BLE,
        handle_reset_timer_ble,
        schema=vol.Schema({**common_ble_schema, vol.Required("probe"): vol.All(vol.Coerce(int), vol.Range(min=1, max=4))}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CALIBRATION_BLE,
        handle_set_calibration_ble,
        schema=vol.Schema(
            {
                **common_ble_schema,
                vol.Required("probe"): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
                vol.Required("channel"): vol.In(("internal", "ambient")),
                vol.Required("c_value"): vol.Coerce(float),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_PROBE_PAIR_BLE,
        handle_start_probe_pair_ble,
        schema=vol.Schema(
            {
                **common_ble_schema,
                vol.Required("probe"): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
                vol.Optional("rssi_threshold", default=-80): vol.All(vol.Coerce(int), vol.Range(min=-128, max=127)),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_PROBE_PAIR_BLE,
        handle_cancel_probe_pair_ble,
        schema=vol.Schema(
            {
                **common_ble_schema,
                vol.Optional("rssi_threshold", default=-80): vol.All(vol.Coerce(int), vol.Range(min=-128, max=127)),
            }
        ),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    transport_mode = entry.options.get(
        CONF_TRANSPORT_MODE,
        entry.data.get(CONF_TRANSPORT_MODE, TRANSPORT_MODE_AUTO),
    )
    cloud_history_config = build_cloud_history_config_from_sources(
        entry_data=entry.data,
        entry_options=entry.options,
        default_base_url=DEFAULT_CLOUD_BASE_URL,
        default_poll_seconds=DEFAULT_CLOUD_POLL_SECONDS,
    )
    lan_config = build_lan_config_from_sources(entry.data, entry.options)
    runtime = Int14Runtime(hass, entry.data[CONF_ADDRESS], transport_mode, cloud_history_config, lan_config)
    runtime.set_model(entry.options.get(CONF_MODEL, entry.data.get(CONF_MODEL)))
    runtime.request_init_on_connect = entry.options.get(
        CONF_REQUEST_INIT_ON_CONNECT,
        entry.data.get(CONF_REQUEST_INIT_ON_CONNECT, True),
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    runtime.start()
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    runtime = hass.data[DOMAIN].pop(entry.entry_id)
    await runtime.stop()
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await async_unload_entry(hass, entry)
    if not unload_ok:
        return False
    return await async_setup_entry(hass, entry)
