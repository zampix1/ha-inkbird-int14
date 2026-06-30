from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .cloud import CloudHistoryConfig, fetch_history_dps
from .const import (
    BATTERY_UUID,
    LIVE_UUID,
    STATE_UUID,
    TRANSPORT_MODE_AUTO,
    TRANSPORT_MODE_BLE_ONLY,
    TRANSPORT_MODE_WIFI_CLOUD_ONLY,
    TRANSPORT_MODE_WIFI_LAN_ONLY,
    TRANSPORT_MODES,
    WRITE_UUID,
)
from .lan import TuyaLanConfig, fetch_lan_dps, set_lan_dps
from .protocol import (
    build_calibration_command,
    build_calibration_dp_value,
    build_display_light_command,
    build_pre_alarm_command,
    build_pre_alarm_dp_value,
    build_target_command,
    build_target_dp_value,
    build_timer_command,
    build_timer_dp_value,
    build_timer_reset_command,
    build_timer_reset_dp_value,
    build_unit_command,
    init_command_chunks,
    parse_cloud_dps,
    parse_notification,
    timer_epoch_values_plausible,
)

_LOGGER = logging.getLogger(__name__)

NOTIFY_UUIDS = {LIVE_UUID, WRITE_UUID, STATE_UUID, BATTERY_UUID}
READ_ON_CONNECT_UUIDS = (LIVE_UUID, WRITE_UUID, STATE_UUID, BATTERY_UUID)
SESSION_SECONDS = 20
RECONNECT_DELAY_SECONDS = 25
WRITE_RETRY_DELAY_SECONDS = 1.0
VERIFY_REQUEST = bytes.fromhex("01fd")
BATTERY_STALE_SECONDS = 6 * 60 * 60


class Int14Runtime:
    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        transport_mode: str = TRANSPORT_MODE_AUTO,
        cloud_history_config: CloudHistoryConfig | None = None,
        lan_config: TuyaLanConfig | None = None,
    ) -> None:
        self.hass = hass
        self.address = address
        self.transport_mode = transport_mode if transport_mode in TRANSPORT_MODES else TRANSPORT_MODE_AUTO
        self.cloud_history_config = cloud_history_config
        self.lan_config = lan_config
        self.data: dict[str, Any] = {}
        self.request_init_on_connect = False
        self._listeners: list[Callable[[], None]] = []
        self._task: asyncio.Task | None = None
        self._cloud_task: asyncio.Task | None = None
        self._lan_task: asyncio.Task | None = None
        self._client: BleakClient | None = None
        self._connection_lock = asyncio.Lock()
        self._mode_changed = asyncio.Event()
        self._refresh_transport_state(notify=False)

    def add_listener(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(callback)

        def remove() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return remove

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())
        if self._cloud_task is None and self.cloud_history_config is not None:
            self._cloud_task = asyncio.create_task(self._run_cloud_history())
        if self._lan_task is None and self.lan_config is not None:
            self._lan_task = asyncio.create_task(self._run_lan())

    async def set_transport_mode(self, transport_mode: str) -> None:
        if transport_mode not in TRANSPORT_MODES:
            raise ValueError(f"Unsupported INT14 transport mode: {transport_mode}")
        if transport_mode == self.transport_mode:
            return
        self.transport_mode = transport_mode
        self._mode_changed.set()
        self._refresh_transport_state()
        if not self.ble_enabled and self._client is not None and self._client.is_connected:
            await self._client.disconnect()

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._cloud_task is not None:
            self._cloud_task.cancel()
            try:
                await self._cloud_task
            except asyncio.CancelledError:
                pass
            self._cloud_task = None
        if self._lan_task is not None:
            self._lan_task.cancel()
            try:
                await self._lan_task
            except asyncio.CancelledError:
                pass
            self._lan_task = None
        if self._client is not None and self._client.is_connected:
            await self._client.disconnect()
        self._client = None
        self._set_ble_connected(False)

    async def _run_cloud_history(self) -> None:
        config = self.cloud_history_config
        if config is None:
            return
        if not config.is_complete:
            self.data["direct_cloud_history_available"] = False
            self.data["direct_cloud_last_error"] = "missing configuration"
            self._notify_listeners()
            return
        session = async_get_clientsession(self.hass)
        while True:
            try:
                if self.cloud_enabled:
                    dps, summary = await fetch_history_dps(session, config)
                    self.data["direct_cloud_last_poll_epoch_s"] = int(time.time())
                    self.data["direct_cloud_history_count"] = summary.get("history_count")
                    self.data["direct_cloud_last_dateline"] = summary.get("dateline")
                    self.data["direct_cloud_status"] = summary.get("status")
                    self.data["direct_cloud_last_error"] = None
                    self.data["direct_cloud_history_available"] = bool(dps)
                    if dps:
                        self.apply_cloud_dps(dps)
                    else:
                        self._notify_listeners()
                await asyncio.sleep(max(30, int(config.poll_seconds)))
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self.data["direct_cloud_history_available"] = False
                self.data["direct_cloud_last_error"] = str(exc)[:200]
                _LOGGER.warning("INT14 direct cloud history poll failed: %s", exc)
                self._notify_listeners()
                await asyncio.sleep(max(30, int(config.poll_seconds)))

    async def _run_lan(self) -> None:
        config = self.lan_config
        if config is None:
            return
        if not config.is_complete:
            self.data["local_lan_available"] = False
            self.data["local_lan_last_error"] = "missing configuration"
            self._notify_listeners()
            return
        while True:
            try:
                if self.lan_enabled:
                    dps, summary = await self.hass.async_add_executor_job(fetch_lan_dps, config)
                    self.data["local_lan_last_poll_epoch_s"] = int(time.time())
                    self.data["local_lan_status_ok"] = summary.get("status_ok")
                    self.data["local_lan_update_ok"] = summary.get("update_ok")
                    self.data["local_lan_last_error"] = summary.get("status_error") or summary.get("update_error")
                    self.data["local_lan_last_err"] = summary.get("status_err") or summary.get("update_err")
                    self.data["local_lan_dp_count"] = summary.get("dps_count")
                    self.data["local_lan_dp_keys"] = ",".join(summary.get("dps_keys") or [])
                    self.data["local_lan_available"] = bool(dps)
                    if dps:
                        self.apply_lan_dps(dps)
                        if self.transport_mode == TRANSPORT_MODE_AUTO and self._client is not None and self._client.is_connected:
                            await self._client.disconnect()
                            self._client = None
                            self._set_ble_connected(False)
                    else:
                        self._notify_listeners()
                await asyncio.sleep(max(5, int(config.poll_seconds)))
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self.data["local_lan_available"] = False
                self.data["local_lan_last_error"] = str(exc)[:200]
                _LOGGER.warning("INT14 Tuya LAN poll failed: %s", exc)
                self._notify_listeners()
                await asyncio.sleep(max(10, int(config.poll_seconds)))

    async def _run(self) -> None:
        while True:
            try:
                if not self.ble_enabled:
                    self._set_ble_connected(False)
                    await self._sleep_or_mode_change(RECONNECT_DELAY_SECONDS)
                    continue
                async with self._connection_lock:
                    client = await self._connect()
                    try:
                        if not self.ble_enabled:
                            await client.disconnect()
                            continue
                        self._client = client
                        self._set_ble_connected(True)
                        await self._subscribe(client)
                        if self.request_init_on_connect:
                            await self.request_init()
                        await self._listen(client)
                    finally:
                        if client.is_connected:
                            await client.disconnect()
                        if self._client is client:
                            self._client = None
                        self._set_ble_connected(False)
                await self._sleep_or_mode_change(RECONNECT_DELAY_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                _LOGGER.warning("INT14 BLE loop failed: %s", exc)
                self._set_ble_connected(False)
                await self._sleep_or_mode_change(30)

    @property
    def ble_enabled(self) -> bool:
        if self.transport_mode == TRANSPORT_MODE_BLE_ONLY:
            return True
        if self.transport_mode != TRANSPORT_MODE_AUTO:
            return False
        return not (self.lan_config is not None and self.lan_config.is_complete)

    @property
    def lan_enabled(self) -> bool:
        return self.transport_mode in {TRANSPORT_MODE_AUTO, TRANSPORT_MODE_WIFI_LAN_ONLY}

    @property
    def cloud_enabled(self) -> bool:
        return self.cloud_history_config is not None and self.transport_mode in {
            TRANSPORT_MODE_AUTO,
            TRANSPORT_MODE_WIFI_CLOUD_ONLY,
        }

    async def _sleep_or_mode_change(self, seconds: int) -> None:
        try:
            await asyncio.wait_for(self._mode_changed.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass
        self._mode_changed.clear()

    async def _connect(self) -> BleakClient:
        from homeassistant.components import bluetooth

        device = bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True)
        if device is None:
            device = BLEDevice(self.address, "INT-14-BW", {})
        return await establish_connection(BleakClient, device, "INT-14-BW", max_attempts=4, timeout=20.0)

    async def _listen(self, client: BleakClient) -> None:
        deadline = asyncio.get_running_loop().time() + SESSION_SECONDS
        while client.is_connected and self.ble_enabled and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(1)

    async def _subscribe(self, client: BleakClient) -> None:
        for service in client.services:
            if not service.uuid.lower().startswith("0000ff00"):
                continue
            for char in service.characteristics:
                char_uuid = char.uuid.lower()
                if char_uuid not in NOTIFY_UUIDS:
                    continue
                props = set(char.properties)
                if "notify" not in props and "indicate" not in props:
                    continue
                try:
                    await client.start_notify(char, self._notification)
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.debug("INT14 notify skipped for %s: %s", char.uuid, exc)

        await self._read_initial_values(client)

    async def _read_initial_values(self, client: BleakClient) -> None:
        for uuid in READ_ON_CONNECT_UUIDS:
            try:
                value = await client.read_gatt_char(uuid)
            except Exception as exc:  # noqa: BLE001
                _LOGGER.debug("INT14 initial read skipped for %s: %s", uuid, exc)
                continue
            if value:
                self._notification(uuid, bytearray(value))

    async def request_init(self) -> None:
        async with self._connection_lock:
            if self._client is not None and self._client.is_connected:
                await self._request_init_on_client(self._client)
                return
            if self.transport_mode not in {TRANSPORT_MODE_AUTO, TRANSPORT_MODE_BLE_ONLY}:
                self.data["last_ble_error"] = f"snapshot disabled in transport mode {self.transport_mode}"
                self._notify_listeners()
                return
            await self._request_init_with_fresh_connection()

    async def _request_init_on_client(self, client: BleakClient) -> None:
        for payload in (VERIFY_REQUEST, *init_command_chunks()):
            if not await self._write_command(payload):
                break
            await asyncio.sleep(0.3)
        await asyncio.sleep(1)
        await self._read_initial_values(client)

    async def _request_init_with_fresh_connection(self) -> None:
        client = None
        try:
            client = await self._connect()
            self._client = client
            self._set_ble_connected(True)
            await self._subscribe(client)
            await self._request_init_on_client(client)
            self.data["last_ble_error"] = None
        except Exception as exc:  # noqa: BLE001
            self.data["last_ble_error"] = str(exc)[:200]
            _LOGGER.warning("INT14 ad-hoc BLE snapshot failed: %s", exc)
        finally:
            if client is not None:
                try:
                    if client.is_connected:
                        await client.disconnect()
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.debug("INT14 ad-hoc BLE snapshot disconnect failed: %s", exc)
            if self._client is client:
                self._client = None
            self._set_ble_connected(False)
            self._notify_listeners()

    async def write_ble_command(self, payload: bytes, *, request_readback: bool = True) -> bool:
        if not self.ble_enabled:
            raise ValueError(f"INT14 BLE writes are disabled in transport mode {self.transport_mode}")
        async with self._connection_lock:
            ok = False
            if self._client is not None and self._client.is_connected:
                ok = await self._write_with_readback(payload, request_readback=request_readback)
                if not ok:
                    try:
                        await self._client.disconnect()
                    except Exception as exc:  # noqa: BLE001
                        _LOGGER.debug("INT14 stale client disconnect failed after write error: %s", exc)
                    self._client = None
                    self._set_ble_connected(False)

            if not ok:
                ok = await self._write_with_fresh_connection(payload, request_readback=request_readback)

            self.data["last_ble_write_hex"] = payload.hex()
            self.data["last_ble_write_epoch_s"] = int(time.time())
            self.data["last_ble_write_ok"] = ok
            self._notify_listeners()
            return ok

    async def write_dps_or_ble(self, dps: dict[str, Any], ble_payload: bytes, *, request_readback: bool = True) -> bool:
        if self.lan_enabled and self.lan_config is not None and self.lan_config.is_complete:
            try:
                result = await self.hass.async_add_executor_job(set_lan_dps, self.lan_config, dps)
                ok = bool(result.get("ok"))
                self.data["last_lan_write_epoch_s"] = int(time.time())
                self.data["last_lan_write_dps"] = ",".join(sorted(str(key) for key in dps.keys()))
                self.data["last_lan_write_ok"] = ok
                self.data["last_lan_write_error"] = result.get("error")
                self.data["last_lan_write_err"] = result.get("err")
                if ok:
                    self.apply_lan_dps(dps)
                    if request_readback:
                        readback, summary = await self.hass.async_add_executor_job(fetch_lan_dps, self.lan_config)
                        self.data["local_lan_dp_count"] = summary.get("dps_count")
                        self.data["local_lan_dp_keys"] = ",".join(summary.get("dps_keys") or [])
                        if readback:
                            self.apply_lan_dps(readback)
                    self._notify_listeners()
                    return True
                self._notify_listeners()
            except Exception as exc:  # noqa: BLE001
                self.data["last_lan_write_epoch_s"] = int(time.time())
                self.data["last_lan_write_dps"] = ",".join(sorted(str(key) for key in dps.keys()))
                self.data["last_lan_write_ok"] = False
                self.data["last_lan_write_error"] = str(exc)[:200]
                _LOGGER.warning("INT14 Tuya LAN write failed: %s", exc)
                self._notify_listeners()
                if not self.ble_enabled:
                    raise
        if self.ble_enabled:
            return await self.write_ble_command(ble_payload, request_readback=request_readback)
        raise ValueError(f"INT14 writes are disabled in transport mode {self.transport_mode}")

    async def write_display_light(self, value: int) -> bool:
        return await self.write_dps_or_ble({"104": int(value)}, build_display_light_command(int(value)))

    async def write_unit(self, unit: str) -> bool:
        value = unit.upper()
        if value not in {"C", "F"}:
            raise ValueError("unit must be C or F")
        return await self.write_dps_or_ble({"101": value}, build_unit_command(value))

    async def write_target(
        self,
        *,
        probe: int,
        mode: str,
        high_tenths: int = 0,
        low_tenths: int = 0,
        degree_index: int = 0,
        food_index: int = -1,
    ) -> bool:
        ble_payload = build_target_command(
            probe=probe,
            mode=mode,
            high_tenths=high_tenths,
            low_tenths=low_tenths,
            degree_index=degree_index,
            food_index=food_index,
        )
        dp_id = str(121 + probe)
        dp_value = build_target_dp_value(
            probe=probe,
            mode=mode,
            high_tenths=high_tenths,
            low_tenths=low_tenths,
            degree_index=degree_index,
            food_index=food_index,
        )
        return await self.write_dps_or_ble({dp_id: dp_value}, ble_payload)

    async def write_target_high(self, *, probe: int, high_tenths: int, degree_index: int = 0, food_index: int = -1) -> bool:
        return await self.write_target(
            probe=probe,
            mode="10",
            high_tenths=high_tenths,
            low_tenths=0,
            degree_index=degree_index,
            food_index=food_index,
        )

    async def write_calibration(self, *, probe: int, channel: str, c_value: float) -> bool:
        ble_payload = build_calibration_command(probe=probe, channel=channel, c_value=c_value)
        dp_value = build_calibration_dp_value(probe=probe, channel=channel, c_value=c_value)
        return await self.write_dps_or_ble({"110": dp_value}, ble_payload)

    async def write_pre_alarm(self, probe: int, advance_values: list[int]) -> bool:
        ble_payload = build_pre_alarm_command(probe, advance_values)
        dp_value = build_pre_alarm_dp_value(probe, advance_values)
        return await self.write_dps_or_ble({"116": dp_value}, ble_payload)

    async def write_timer(self, *, probe: int, start_epoch_s: int, end_epoch_s: int, count_down: bool = True) -> bool:
        ble_payload = build_timer_command(probe, start_epoch_s, end_epoch_s, count_down=count_down)
        dp_value = build_timer_dp_value(probe, start_epoch_s, end_epoch_s, count_down=count_down)
        ok = await self.write_dps_or_ble({str(125 + probe): dp_value}, ble_payload)
        if ok:
            self.data[f"probe_{probe}_timer_switch"] = True
            self._notify_listeners()
        return ok

    async def reset_timer(self, probe: int) -> bool:
        ble_payload = build_timer_reset_command(probe)
        dp_value = build_timer_reset_dp_value(probe)
        ok = await self.write_dps_or_ble({str(125 + probe): dp_value}, ble_payload)
        if ok:
            self.data[f"probe_{probe}_timer_cd_mode"] = None
            self.data[f"probe_{probe}_timer_start_epoch_s"] = None
            self.data[f"probe_{probe}_timer_end_epoch_s"] = None
            self.data[f"probe_{probe}_timer_switch"] = False
            self._notify_listeners()
        return ok

    async def _write_with_fresh_connection(self, payload: bytes, *, request_readback: bool) -> bool:
        for attempt in range(2):
            client = None
            try:
                client = await self._connect()
                self._client = client
                self._set_ble_connected(True)
                await self._subscribe(client)
                ok = await self._write_with_readback(payload, request_readback=request_readback)
                self.data["last_ble_write_hex"] = payload.hex()
                self.data["last_ble_write_epoch_s"] = int(time.time())
                self.data["last_ble_write_ok"] = ok
                self._notify_listeners()
                if ok:
                    return True
            except Exception as exc:  # noqa: BLE001
                self.data["last_ble_error"] = str(exc)[:200]
                _LOGGER.debug("INT14 fresh BLE write attempt %s failed: %s", attempt + 1, exc)
            finally:
                if client is not None and client.is_connected:
                    await client.disconnect()
                if client is not None and self._client is client:
                    self._client = None
                self._set_ble_connected(False)
            if attempt == 0:
                await asyncio.sleep(WRITE_RETRY_DELAY_SECONDS)
        return False

    async def _write_with_readback(self, payload: bytes, *, request_readback: bool) -> bool:
        ok = await self._write_command(payload)
        if not ok:
            await asyncio.sleep(WRITE_RETRY_DELAY_SECONDS)
            ok = await self._write_command(payload)
        if ok and request_readback and self._client is not None:
            await asyncio.sleep(1)
            await self._read_initial_values(self._client)
        return ok

    async def _write_command(self, payload: bytes) -> bool:
        if self._client is None:
            return False
        try:
            await self._client.write_gatt_char(WRITE_UUID, payload, response=True)
            return True
        except Exception as response_exc:  # noqa: BLE001
            try:
                await self._client.write_gatt_char(WRITE_UUID, payload, response=False)
                return True
            except Exception as command_exc:  # noqa: BLE001
                _LOGGER.debug(
                    "INT14 init chunk write skipped: response=%s command=%s",
                    response_exc,
                    command_exc,
                )
                return False

    def apply_cloud_dps(self, dps: dict[str, Any]) -> None:
        parsed = parse_cloud_dps(dps)
        self.data["last_cloud_update_epoch_s"] = int(time.time())
        self.data["last_cloud_dp_keys"] = ",".join(parsed.get("dp_keys", []))
        self.data["cloud_available"] = True
        live_allowed = self.transport_mode == TRANSPORT_MODE_WIFI_CLOUD_ONLY or not self.data.get("ble_connected")
        for frame in parsed["frames"]:
            self._apply_frame(frame, live_allowed=live_allowed)
        self._refresh_transport_state(notify=False)
        self._notify_listeners()

    def apply_lan_dps(self, dps: dict[str, Any]) -> None:
        parsed = parse_cloud_dps(dps)
        self.data["last_lan_update_epoch_s"] = int(time.time())
        self.data["last_lan_dp_keys"] = ",".join(parsed.get("dp_keys", []))
        self.data["local_lan_available"] = True
        live_allowed = self.transport_mode == TRANSPORT_MODE_WIFI_LAN_ONLY or not self.data.get("ble_connected")
        for frame in parsed["frames"]:
            transport = frame.get("transport")
            if isinstance(transport, str) and transport.startswith("cloud_"):
                frame = {**frame, "transport": "lan_" + transport.removeprefix("cloud_")}
            self._apply_frame(frame, live_allowed=live_allowed)
        self._refresh_transport_state(notify=False)
        self._notify_listeners()

    def _notification(self, sender: int | str, data: bytearray) -> None:
        self.data["last_ble_update_epoch_s"] = int(time.time())
        self._record_raw(sender, data)
        parsed = parse_notification(bytes(data))
        self.data["last_raw_hex"] = parsed["raw_hex"]
        for frame in parsed["frames"]:
            self._apply_frame(frame, live_allowed=True)
        self._refresh_transport_state(notify=False)
        self._notify_listeners()

    def _apply_frame(self, frame: dict[str, Any], *, live_allowed: bool) -> None:
        if frame.get("name") == "current_temp_candidate":
            self.data["last_transport"] = frame.get("transport")
            if not live_allowed:
                return
            self.data["base_temp_f_tenths"] = frame.get("base_temp_f_tenths")
            for probe in frame["probes"]:
                idx = probe["probe"]
                self.data[f"probe_{idx}_internal_f_tenths"] = probe["internal_f_tenths"]
                self.data[f"probe_{idx}_ambient_f_tenths"] = probe["ambient_f_tenths"]
        elif frame.get("name") == "battery_candidate":
            self.data["last_transport"] = frame.get("transport")
            self.data["last_battery_transport"] = frame.get("transport")
            self.data["last_battery_update_epoch_s"] = int(time.time())
            self.data["battery_data_stale"] = False
            if frame.get("raw_hex") is not None:
                self.data["last_battery_prefix"] = str(frame["raw_hex"])[:40]
                self.data["last_battery_len"] = len(str(frame["raw_hex"])) // 2
            self.data["base_power"] = frame["base_power"]
            for idx, value in frame["probe_battery"].items():
                self.data[f"probe_{idx}_battery"] = value
            self._classify_battery_report()
        elif frame.get("name") == "state_candidate":
            self.data["last_transport"] = frame.get("transport")
            self.data["base_charging"] = frame.get("base_charging")
            self.data["wifi_switch"] = frame.get("wifi_switch")
            self.data["wifi_state"] = frame.get("wifi_state")
            self.data["verify"] = frame.get("verify")
            self.data["device_over_high_temp_alarm"] = frame.get("device_over_high_temp_alarm")
            self.data["device_over_low_temp_alarm"] = frame.get("device_over_low_temp_alarm")
            for probe in frame["probes"]:
                idx = probe["probe"]
                for key, value in probe.items():
                    if key != "probe":
                        self.data[f"probe_{idx}_{key}"] = value
            if self.data.get("last_battery_update_epoch_s") is not None:
                self._classify_battery_report()
        elif frame.get("name") == "target_candidate":
            self.data["last_transport"] = frame.get("transport")
            idx = frame.get("probe")
            if idx is not None:
                self.data[f"probe_{idx}_target_high_f_tenths"] = frame.get("target_high_f_tenths")
                self.data[f"probe_{idx}_target_low_f_tenths"] = frame.get("target_low_f_tenths")
                self.data[f"probe_{idx}_target_mode"] = frame.get("mode_name")
                self.data[f"probe_{idx}_target_food_index"] = frame.get("food_index")
                self.data[f"probe_{idx}_target_degree_code"] = frame.get("degree_code")
        elif frame.get("name") == "pre_alarm_candidate":
            self.data["last_transport"] = frame.get("transport")
            for idx, value in enumerate(frame.get("advance_values", []), start=1):
                self.data[f"probe_{idx}_advance_value"] = value
        elif frame.get("name") == "timer_candidate":
            self.data["last_transport"] = frame.get("transport")
            idx = frame.get("probe")
            if idx is not None:
                if not timer_epoch_values_plausible(
                    frame.get("start_epoch_s"),
                    frame.get("end_epoch_s"),
                    now_epoch_s=int(time.time()),
                ):
                    self.data["last_timer_rejected_epoch_s"] = int(time.time())
                    self.data["last_timer_rejected_transport"] = frame.get("transport")
                    return
                self.data[f"probe_{idx}_timer_cd_mode"] = frame.get("cd_mode")
                self.data[f"probe_{idx}_timer_start_epoch_s"] = frame.get("start_epoch_s")
                self.data[f"probe_{idx}_timer_end_epoch_s"] = frame.get("end_epoch_s")
        elif frame.get("name") == "calibration_candidate":
            self.data["last_transport"] = frame.get("transport")
            for idx, value in frame.get("internal", {}).items():
                self.data[f"probe_{idx}_internal_calibration_c"] = value.get("c_value")
                self.data[f"probe_{idx}_internal_calibration_raw_f_tenths"] = value.get("raw_f_tenths")
            for idx, value in frame.get("ambient", {}).items():
                self.data[f"probe_{idx}_ambient_calibration_c"] = value.get("c_value")
                self.data[f"probe_{idx}_ambient_calibration_raw_f_tenths"] = value.get("raw_f_tenths")
        elif frame.get("name") == "unit_candidate":
            self.data["last_transport"] = frame.get("transport")
            self.data["unit"] = frame.get("unit")
            self.data["is_f"] = frame.get("is_f")
        elif frame.get("name") == "display_light_candidate":
            self.data["last_transport"] = frame.get("transport")
            self.data["display_light"] = frame.get("display_light")
        elif frame.get("name") == "sound_candidate":
            self.data["last_transport"] = frame.get("transport")
            self.data["sound_enabled"] = frame.get("sound_enabled")
            self.data["dev_mute"] = frame.get("dev_mute")

    def _record_raw(self, sender: int | str, data: bytearray) -> None:
        raw_hex = bytes(data).hex()
        sender_uuid = getattr(sender, "uuid", None)
        sender_text = str(sender_uuid or sender).lower()
        self.data["last_sender"] = sender_text[:120]
        self.data["last_raw_len"] = len(data)
        self.data["last_raw_prefix"] = raw_hex[:160]
        if "ff02" in sender_text:
            self.data["last_ff02_len"] = len(data)
            self.data["last_ff02_prefix"] = raw_hex[:160]
        elif "ff01" in sender_text or len(data) == 18:
            self.data["last_ff01_len"] = len(data)
            self.data["last_ff01_prefix"] = raw_hex[:80]
        elif "ff03" in sender_text or len(data) == 11:
            self.data["last_ff03_len"] = len(data)
            self.data["last_ff03_prefix"] = raw_hex[:80]
        elif "2a19" in sender_text or len(data) == 5:
            self.data["last_battery_len"] = len(data)
            self.data["last_battery_prefix"] = raw_hex[:40]

    def _classify_battery_report(self) -> None:
        raw_hex = str(self.data.get("last_battery_prefix") or "").lower()
        probe_values = [value for value in (self.data.get(f"probe_{idx}_battery") for idx in range(1, 5)) if value is not None]
        raw_all_100 = raw_hex.startswith("6464646464")
        probe_100_plateau = len(probe_values) >= 4 and all(value == 100 for value in probe_values)

        base_charging = self.data.get("base_charging") is True
        all_probe_charging = all(self.data.get(f"probe_{idx}_charging") is True for idx in range(1, 5))
        base_suspect = raw_all_100 and not base_charging
        probe_suspects = {}
        for idx in range(1, 5):
            value = self.data.get(f"probe_{idx}_battery")
            charging = self.data.get(f"probe_{idx}_charging") is True
            suspect = (raw_all_100 or (probe_100_plateau and value == 100)) and not charging
            probe_suspects[idx] = suspect
            self.data[f"probe_{idx}_battery_report_suspect"] = suspect
        probe_suspect = any(probe_suspects.values())
        if raw_all_100:
            if base_charging and all_probe_charging:
                quality = "reported_all_100_charging"
            elif probe_suspect and base_suspect:
                quality = "suspect_all_100_raw"
            elif probe_suspect:
                quality = "mixed_all_100_some_probes_not_charging"
            elif all_probe_charging:
                quality = "suspect_base_all_100_not_charging"
            elif base_charging:
                quality = "suspect_probe_all_100_not_charging"
            else:
                quality = "suspect_all_100_raw"
        elif probe_100_plateau:
            quality = "reported_probe_100_charging" if all_probe_charging else "suspect_probe_100_plateau"
        else:
            quality = "fresh"

        self.data["base_battery_report_suspect"] = base_suspect
        self.data["probe_battery_report_suspect"] = probe_suspect
        self.data["battery_report_suspect"] = base_suspect or probe_suspect
        self.data["battery_report_quality"] = quality

    def _set_ble_connected(self, connected: bool) -> None:
        self.data["ble_connected"] = connected
        self._refresh_transport_state()

    def _refresh_transport_state(self, notify: bool = True) -> None:
        last_battery = self.data.get("last_battery_update_epoch_s")
        if last_battery is None:
            battery_data_stale = True
            battery_age = None
        else:
            battery_age = max(0, int(time.time()) - int(last_battery))
            battery_data_stale = battery_age > BATTERY_STALE_SECONDS
        updates = {
            "transport_mode": self.transport_mode,
            "ble_enabled": self.ble_enabled,
            "local_lan_enabled": self.lan_config is not None and self.lan_enabled,
            "cloud_enabled": self.cloud_enabled,
            "local_lan_configured": self.lan_config is not None,
            "direct_cloud_history_enabled": self.cloud_history_config is not None,
            "ble_connected": bool(self.data.get("ble_connected")),
            "battery_data_stale": battery_data_stale,
            "battery_age_seconds": battery_age,
        }
        if battery_data_stale:
            updates["battery_report_quality"] = "stale"
        updates["active_transport"] = self._active_transport(updates["ble_connected"])
        changed = any(self.data.get(key) != value for key, value in updates.items())
        self.data.update(updates)
        if notify and changed:
            self._notify_listeners()

    def _active_transport(self, ble_connected: bool) -> str:
        if self.transport_mode == TRANSPORT_MODE_WIFI_LAN_ONLY:
            return "wifi_lan_selected" if self.data.get("local_lan_available") else "wifi_lan_pending"
        if self.transport_mode == TRANSPORT_MODE_AUTO and self.data.get("local_lan_available"):
            return "wifi_lan_available"
        if ble_connected:
            return "ble"
        wifi_online = bool(self.data.get("wifi_state"))
        if self.transport_mode == TRANSPORT_MODE_BLE_ONLY:
            return "ble_waiting"
        if self.transport_mode == TRANSPORT_MODE_WIFI_CLOUD_ONLY:
            return "wifi_cloud_selected" if wifi_online else "wifi_cloud_pending"
        if wifi_online:
            return "wifi_cloud_available"
        return "ble_waiting"

    def _notify_listeners(self) -> None:
        for callback in list(self._listeners):
            callback()
