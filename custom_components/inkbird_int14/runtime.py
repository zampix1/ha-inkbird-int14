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

from .auth import AUTH_CHALLENGE_REQUEST, auth_ack_ok, auth_challenge_from_frame, build_auth_response
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
from .models import (
    AUTH_MODE_GATT_POLL,
    AUTH_MODE_SCAN_ONLY,
    DEFAULT_MODEL,
    MODEL_INT11I_B,
    MODEL_INT12E_BW,
    MODEL_INT14S_BW,
    InkbirdIntModelProfile,
    model_profile,
)
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
    diagnostic_snapshot_query_chunks,
    init_command_chunks,
    parse_battery_payload,
    parse_cloud_dps,
    parse_int11i_battery_payload,
    parse_int11i_temperature_payload,
    parse_multisensor_temperature_payload,
    parse_notification,
    timer_epoch_values_plausible,
)

_LOGGER = logging.getLogger(__name__)

NOTIFY_UUIDS = {LIVE_UUID, WRITE_UUID, STATE_UUID, BATTERY_UUID}
READ_ON_CONNECT_UUIDS = (LIVE_UUID, WRITE_UUID, STATE_UUID, BATTERY_UUID)
SESSION_SECONDS = 20
RECONNECT_DELAY_SECONDS = 25
WRITE_RETRY_DELAY_SECONDS = 1.0
AUTH_TIMEOUT_SECONDS = 3.0
BATTERY_STALE_SECONDS = 6 * 60 * 60
BLE_DIAGNOSTIC_CAPTURE_SECONDS = 8
BLE_DIAGNOSTIC_AUTH_TIMEOUT_SECONDS = 5
BLE_DIAGNOSTIC_MAX_NOTIFICATIONS = 64
BLE_DIAGNOSTIC_HEX_LIMIT = 320


def _normalize_ble_name(value: object) -> str:
    return "".join(character for character in str(value or "").casefold() if character.isalnum())


class Int14Runtime:
    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        transport_mode: str = TRANSPORT_MODE_AUTO,
        cloud_history_config: CloudHistoryConfig | None = None,
        lan_config: TuyaLanConfig | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self.hass = hass
        self.address = address
        self.profile: InkbirdIntModelProfile = model_profile(model)
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
        self._auth_challenge_event = asyncio.Event()
        self._auth_ack_event = asyncio.Event()
        self._refresh_transport_state(notify=False)

    @property
    def probe_count(self) -> int:
        return self.profile.probe_count

    @property
    def physical_probe_count(self) -> int:
        return self.profile.physical_probe_count

    @property
    def temperature_channel_count(self) -> int:
        return self.profile.temperature_channel_count

    @property
    def device_model(self) -> str:
        return self.profile.display_name

    def set_model(self, model: str | None) -> None:
        self.profile = model_profile(model)
        self.data["model"] = self.profile.app_model
        self.data["model_profile"] = self.profile.key
        self.data["model_support_status"] = self.profile.support_status
        self.data["probe_count"] = self.profile.probe_count
        self.data["temperature_channel_count"] = self.profile.temperature_channel_count
        self.data["live_temperature_channel_count"] = self.profile.live_temperature_channel_count
        self.data["probe_layout_summary"] = self.profile.probe_layout_summary

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
                            await self._request_init_on_client(client)
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
        if not self.profile.supports_ble_snapshot:
            return False
        if self.transport_mode == TRANSPORT_MODE_BLE_ONLY:
            return True
        if self.transport_mode != TRANSPORT_MODE_AUTO:
            return False
        return not (self.profile.supports_lan and self.lan_config is not None and self.lan_config.is_complete)

    @property
    def lan_enabled(self) -> bool:
        return self.profile.supports_lan and self.transport_mode in {TRANSPORT_MODE_AUTO, TRANSPORT_MODE_WIFI_LAN_ONLY}

    @property
    def cloud_enabled(self) -> bool:
        return (
            self.profile.supports_cloud_history
            and self.cloud_history_config is not None
            and self.transport_mode in {TRANSPORT_MODE_AUTO, TRANSPORT_MODE_WIFI_CLOUD_ONLY}
        )

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
            device = BLEDevice(self.address, self.profile.app_model, {})
        return await establish_connection(BleakClient, device, self.profile.app_model, max_attempts=4, timeout=20.0)

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
        await self._request_auth(client)
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

    async def request_ble_diagnostics(self) -> None:
        """Inspect an eligible profile over GATT without sending Inkbird commands."""
        await self._request_ble_diagnostics(authenticated=False)

    async def request_authenticated_ble_diagnostics(self) -> None:
        """Capture reviewed BW traffic after volatile auth and snapshot requests."""
        if not self.profile.supports_authenticated_ble_diagnostics:
            self.data["ble_debug_status"] = "authenticated_not_available_for_profile"
            self.data["ble_debug_last_error"] = "Authenticated BLE diagnostics are not available for this profile"
            self._notify_listeners()
            return
        await self._request_ble_diagnostics(authenticated=True)

    async def _request_ble_diagnostics(self, *, authenticated: bool) -> None:
        if not self.profile.supports_ble_diagnostics:
            self.data["ble_debug_status"] = "not_available_for_profile"
            self.data["ble_debug_last_error"] = "BLE diagnostics are not available for this profile"
            self._notify_listeners()
            return
        if self.transport_mode not in {TRANSPORT_MODE_AUTO, TRANSPORT_MODE_BLE_ONLY}:
            self.data["ble_debug_status"] = "transport_mode_blocked"
            self.data["ble_debug_last_error"] = f"BLE diagnostics are disabled in transport mode {self.transport_mode}"
            self._notify_listeners()
            return

        async with self._connection_lock:
            await self._request_ble_diagnostics_locked(authenticated=authenticated)

    async def _request_ble_diagnostics_locked(self, *, authenticated: bool) -> None:
        client = None
        started_notify = []
        pending_tasks: list[asyncio.Task] = []
        auth_challenge_event = asyncio.Event()
        auth_ack_event = asyncio.Event()
        auth_response_scheduled = False
        self.data.update(
            {
                "ble_debug_last_run_epoch_s": int(time.time()),
                "ble_debug_status": "starting",
                "ble_debug_last_error": None,
                "ble_debug_last_error_type": None,
                "ble_debug_match_source": None,
                "ble_debug_scanner_match_count": 0,
                "ble_debug_active_scan_requested": False,
                "ble_debug_service_uuids": [],
                "ble_debug_characteristics": [],
                "ble_debug_read_values": [],
                "ble_debug_read_errors": [],
                "ble_debug_notifications": [],
                "ble_debug_notification_errors": [],
                "ble_debug_service_count": 0,
                "ble_debug_characteristic_count": 0,
                "ble_debug_read_value_count": 0,
                "ble_debug_notification_count": 0,
                "ble_debug_application_commands_sent": 0,
                "ble_debug_capture_mode": "authenticated_snapshot" if authenticated else "passive",
                "ble_debug_application_commands": [],
                "ble_debug_command_errors": [],
                "ble_debug_post_auth_read_values": [],
                "ble_debug_auth_challenge_received": False,
                "ble_debug_auth_ok": None,
            }
        )
        self._notify_listeners()

        try:
            device, match_source, match_count = self._resolve_ble_diagnostic_device()
            if device is None:
                from homeassistant.components import bluetooth

                request_active_scan = getattr(bluetooth, "async_request_active_scan", None)
                if request_active_scan is not None:
                    self.data["ble_debug_active_scan_requested"] = True
                    await request_active_scan(self.hass)
                    device, match_source, match_count = self._resolve_ble_diagnostic_device()
            self.data["ble_debug_match_source"] = match_source
            self.data["ble_debug_scanner_match_count"] = match_count
            if device is None:
                reachability_diagnostics = getattr(bluetooth, "async_address_reachability_diagnostics", None)
                reachability_intent = getattr(bluetooth, "BluetoothReachabilityIntent", None)
                if reachability_diagnostics is not None and reachability_intent is not None:
                    self.data["ble_debug_reachability"] = reachability_diagnostics(
                        self.hass,
                        self.address,
                        reachability_intent.CONNECTION,
                    )
                self.data["ble_debug_status"] = "scanner_not_seen" if match_count == 0 else "scanner_match_ambiguous"
                self.data["ble_debug_last_error"] = (
                    "Home Assistant has not seen a connectable advertisement for the configured address or model name"
                    if match_count == 0
                    else "More than one connectable advertisement matches this model name"
                )
                return

            client = await establish_connection(
                BleakClient,
                device,
                f"{self.profile.app_model} diagnostic",
                max_attempts=2,
                timeout=20.0,
            )
            self.data["ble_debug_status"] = "connected"

            service_uuids: list[str] = []
            characteristics: list[dict[str, Any]] = []
            read_values: list[dict[str, Any]] = []
            read_errors: list[dict[str, str]] = []
            notify_candidates = []
            for service in client.services:
                service_uuid = service.uuid.lower()
                service_uuids.append(service_uuid)
                for characteristic in service.characteristics:
                    properties = sorted(str(prop).lower() for prop in characteristic.properties)
                    characteristic_uuid = characteristic.uuid.lower()
                    characteristics.append(
                        {
                            "service_uuid": service_uuid,
                            "uuid": characteristic_uuid,
                            "properties": properties,
                        }
                    )
                    if "read" in properties:
                        try:
                            value = bytes(await client.read_gatt_char(characteristic))
                            read_values.append(self._ble_diagnostic_value(characteristic_uuid, value))
                        except Exception as exc:  # noqa: BLE001
                            read_errors.append({"uuid": characteristic_uuid, "error_type": type(exc).__name__})
                    if "notify" in properties or "indicate" in properties:
                        notify_candidates.append(characteristic)

            self.data["ble_debug_service_uuids"] = sorted(set(service_uuids))
            self.data["ble_debug_characteristics"] = characteristics
            self.data["ble_debug_read_values"] = read_values
            self.data["ble_debug_read_errors"] = read_errors
            self.data["ble_debug_service_count"] = len(set(service_uuids))
            self.data["ble_debug_characteristic_count"] = len(characteristics)
            self.data["ble_debug_read_value_count"] = len(read_values)

            def diagnostic_notification(sender: int | str, data: bytearray) -> None:
                nonlocal auth_response_scheduled
                self._ble_diagnostic_notification(sender, data)
                if not authenticated:
                    return
                raw = bytes(data)
                if (challenge := auth_challenge_from_frame(raw)) is not None:
                    self.data["ble_debug_auth_challenge_received"] = True
                    auth_challenge_event.set()
                    if not auth_response_scheduled:
                        auth_response_scheduled = True
                        response = build_auth_response(challenge)
                        pending_tasks.append(
                            self.hass.async_create_task(self._write_ble_diagnostic_command(client, response, "auth_response"))
                        )
                if (ok := auth_ack_ok(raw)) is not None:
                    self.data["ble_debug_auth_ok"] = ok
                    auth_ack_event.set()

            for characteristic in notify_candidates:
                try:
                    await client.start_notify(characteristic, diagnostic_notification)
                    started_notify.append(characteristic)
                except Exception as exc:  # noqa: BLE001
                    self.data["ble_debug_notification_errors"].append(
                        {"uuid": characteristic.uuid.lower(), "error_type": type(exc).__name__}
                    )

            if authenticated:
                await self._run_authenticated_ble_diagnostic(
                    client,
                    auth_challenge_event=auth_challenge_event,
                    auth_ack_event=auth_ack_event,
                )
                self.data["ble_debug_post_auth_read_values"] = await self._read_ble_diagnostic_values(
                    client,
                    characteristics,
                )
            if started_notify:
                await asyncio.sleep(BLE_DIAGNOSTIC_CAPTURE_SECONDS)
            self.data["ble_debug_notification_count"] = len(self.data["ble_debug_notifications"])
            if authenticated and self.data.get("ble_debug_auth_ok") is not True:
                self.data["ble_debug_status"] = "complete_auth_failed"
            else:
                self.data["ble_debug_status"] = "complete"
        except Exception as exc:  # noqa: BLE001
            self.data["ble_debug_status"] = "failed"
            self.data["ble_debug_last_error_type"] = type(exc).__name__
            self.data["ble_debug_last_error"] = str(exc)[:200]
            _LOGGER.warning("Inkbird BLE diagnostic failed: %s", exc)
        finally:
            if pending_tasks:
                await asyncio.gather(*pending_tasks, return_exceptions=True)
            if client is not None:
                for characteristic in started_notify:
                    try:
                        await client.stop_notify(characteristic)
                    except Exception as exc:  # noqa: BLE001
                        _LOGGER.debug("BLE diagnostic notification stop failed for %s: %s", characteristic.uuid, exc)
                try:
                    if client.is_connected:
                        await client.disconnect()
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.debug("BLE diagnostic disconnect failed: %s", exc)
            self._notify_listeners()

    async def _run_authenticated_ble_diagnostic(
        self,
        client: BleakClient,
        *,
        auth_challenge_event: asyncio.Event,
        auth_ack_event: asyncio.Event,
    ) -> None:
        if not await self._write_ble_diagnostic_command(client, AUTH_CHALLENGE_REQUEST, "auth_challenge_request"):
            self.data["ble_debug_last_error"] = "auth_challenge_request_failed"
            return
        try:
            await asyncio.wait_for(auth_challenge_event.wait(), timeout=BLE_DIAGNOSTIC_AUTH_TIMEOUT_SECONDS)
        except TimeoutError:
            self.data["ble_debug_last_error"] = "auth_challenge_timeout"
            return
        try:
            await asyncio.wait_for(auth_ack_event.wait(), timeout=BLE_DIAGNOSTIC_AUTH_TIMEOUT_SECONDS)
        except TimeoutError:
            self.data["ble_debug_last_error"] = "auth_ack_timeout"
            return
        if self.data.get("ble_debug_auth_ok") is not True:
            self.data["ble_debug_last_error"] = "auth_rejected"
            return
        for index, payload in enumerate(diagnostic_snapshot_query_chunks(), start=1):
            if not await self._write_ble_diagnostic_command(client, payload, f"snapshot_query_{index}"):
                self.data["ble_debug_last_error"] = f"snapshot_query_{index}_failed"
                return
            await asyncio.sleep(0.3)
        await asyncio.sleep(1)

    async def _write_ble_diagnostic_command(self, client: BleakClient, payload: bytes, label: str) -> bool:
        error_type = None
        try:
            await client.write_gatt_char(WRITE_UUID, payload, response=True)
        except Exception:  # noqa: BLE001
            try:
                await client.write_gatt_char(WRITE_UUID, payload, response=False)
            except Exception as exc:  # noqa: BLE001
                error_type = type(exc).__name__
        if error_type is not None:
            self.data.setdefault("ble_debug_command_errors", []).append({"label": label, "error_type": error_type})
            return False
        commands = self.data.setdefault("ble_debug_application_commands", [])
        commands.append({"label": label, "length": len(payload), "hex": payload.hex()[:BLE_DIAGNOSTIC_HEX_LIMIT]})
        self.data["ble_debug_application_commands_sent"] = len(commands)
        return True

    async def _read_ble_diagnostic_values(
        self,
        client: BleakClient,
        characteristics: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        values = []
        for characteristic in characteristics:
            if "read" not in characteristic["properties"]:
                continue
            uuid = characteristic["uuid"]
            try:
                value = bytes(await client.read_gatt_char(uuid))
            except Exception as exc:  # noqa: BLE001
                values.append({"uuid": uuid, "error_type": type(exc).__name__})
                continue
            values.append(self._ble_diagnostic_value(uuid, value))
        return values

    def _ble_diagnostic_value(self, uuid: str, value: bytes) -> dict[str, Any]:
        item: dict[str, Any] = {
            "uuid": uuid.lower(),
            "length": len(value),
            "hex": value.hex()[:BLE_DIAGNOSTIC_HEX_LIMIT],
        }
        if uuid.lower() == LIVE_UUID:
            candidate = parse_multisensor_temperature_payload(value, self.profile.physical_probe_count)
            if candidate is not None:
                item["multisensor_candidate"] = candidate
        return item

    def _resolve_ble_diagnostic_device(self):
        from homeassistant.components import bluetooth

        device = bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True)
        if device is not None:
            return device, "configured_address", 1

        expected_name = _normalize_ble_name(self.profile.app_model)
        matching_infos = []
        for info in bluetooth.async_discovered_service_info(self.hass, connectable=True):
            names = {
                _normalize_ble_name(getattr(info, "name", None)),
                _normalize_ble_name(getattr(info, "local_name", None)),
            }
            if expected_name and any(name == expected_name or name.startswith(expected_name) for name in names):
                matching_infos.append(info)

        if len(matching_infos) != 1:
            return None, "model_name", len(matching_infos)
        info = matching_infos[0]
        device = getattr(info, "device", None) or bluetooth.async_ble_device_from_address(
            self.hass,
            info.address,
            connectable=True,
        )
        return device, "unique_model_name", 1 if device is not None else 0

    def _ble_diagnostic_notification(self, sender: int | str, data: bytearray) -> None:
        notifications = self.data.setdefault("ble_debug_notifications", [])
        if len(notifications) >= BLE_DIAGNOSTIC_MAX_NOTIFICATIONS:
            return
        sender_uuid = getattr(sender, "uuid", None)
        raw = bytes(data)
        uuid = str(sender_uuid or sender).lower()[:120]
        notifications.append(self._ble_diagnostic_value(uuid, raw))
        self.data["ble_debug_notification_count"] = len(notifications)
        self._notify_listeners()

    async def _request_init_on_client(self, client: BleakClient) -> None:
        if not self.profile.supports_ble_snapshot:
            self.data["last_ble_error"] = f"BLE snapshot not implemented for {self.profile.display_name}"
            self._notify_listeners()
            return
        if self.profile.ble_auth_mode == AUTH_MODE_GATT_POLL:
            await self._read_initial_values(client)
            self.data["last_ble_error"] = None
            return
        await self._request_auth(client)
        command_chunks = diagnostic_snapshot_query_chunks() if self.profile.key == MODEL_INT14S_BW else init_command_chunks()
        for payload in command_chunks:
            if not await self._write_command(payload):
                break
            await asyncio.sleep(0.3)
        await asyncio.sleep(1)
        await self._read_initial_values(client)

    async def _request_auth(self, client: BleakClient) -> None:
        if self.profile.ble_auth_mode == AUTH_MODE_GATT_POLL:
            self.data["ble_auth_ok"] = True
            self.data["last_ble_auth_error"] = None
            self._notify_listeners()
            return
        if self.profile.ble_auth_mode == AUTH_MODE_SCAN_ONLY:
            self.data["ble_auth_ok"] = None
            self.data["last_ble_auth_error"] = "auth not implemented for scan-only model profile"
            self._notify_listeners()
            return
        if self._client is None:
            self._client = client
        self._auth_challenge_event.clear()
        self._auth_ack_event.clear()
        self.data["ble_auth_ok"] = False
        self.data["last_ble_auth_error"] = None
        if not await self._write_command(AUTH_CHALLENGE_REQUEST):
            self.data["last_ble_auth_error"] = "challenge_request_failed"
            return
        self.data["last_ble_auth_request_epoch_s"] = int(time.time())
        try:
            await asyncio.wait_for(self._auth_ack_event.wait(), timeout=AUTH_TIMEOUT_SECONDS)
        except TimeoutError:
            self.data["last_ble_auth_error"] = "auth_ack_timeout"

    async def _send_auth_response(self, response: bytes) -> None:
        if self._client is None or not self._client.is_connected:
            self.data["last_ble_auth_error"] = "not_connected"
            self._notify_listeners()
            return
        try:
            await self._client.write_gatt_char(WRITE_UUID, response, response=True)
        except Exception as response_exc:  # noqa: BLE001
            try:
                await self._client.write_gatt_char(WRITE_UUID, response, response=False)
            except Exception as command_exc:  # noqa: BLE001
                self.data["last_ble_auth_error"] = str(command_exc)[:200]
                _LOGGER.debug(
                    "INT14 auth response write failed: response=%s command=%s",
                    response_exc,
                    command_exc,
                )
                self._notify_listeners()
                return
        self.data["last_ble_auth_response_epoch_s"] = int(time.time())
        self.data["last_ble_auth_response_len"] = len(response)
        self.data["last_ble_auth_error"] = None
        self._notify_listeners()

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

    async def request_unit_write_validation(self, unit: str) -> None:
        """Run the narrow, reversible INT-14S unit write validation."""
        unit = unit.upper()
        if self.profile.key != MODEL_INT14S_BW:
            raise ValueError("Unit write validation is available only for INT-14S-BW")
        if unit not in {"C", "F"}:
            raise ValueError("unit must be C or F")
        if not self.ble_enabled:
            raise ValueError(f"INT14S BLE write validation is disabled in transport mode {self.transport_mode}")

        async with self._connection_lock:
            await self._request_unit_write_validation_locked(unit)

    async def _request_unit_write_validation_locked(self, unit: str) -> None:
        client = None
        self.data.update(
            {
                "ble_write_validation_active": True,
                "ble_write_validation_last_run_epoch_s": int(time.time()),
                "ble_write_validation_requested_unit": unit,
                "ble_write_validation_status": "starting",
                "ble_write_validation_error": None,
                "ble_write_validation_command_sent": False,
                "ble_write_validation_original_readback_unit": None,
                "ble_write_validation_readback_unit": None,
                "ble_write_validation_readback_matches": None,
                "ble_write_validation_notification_count": 0,
                "ble_write_validation_notifications": [],
            }
        )
        self._notify_listeners()
        try:
            client = await self._connect()
            self._client = client
            self._set_ble_connected(True)
            self.data["ble_write_validation_status"] = "connected"
            await self._subscribe(client)
            if self.data.get("ble_auth_ok") is not True:
                error = self.data.get("last_ble_auth_error") or "authentication_not_confirmed"
                raise RuntimeError(str(error))

            self.data["ble_write_validation_status"] = "authenticated"
            self.data["ble_write_validation_original_readback_unit"] = self.data.get("unit")
            if not await self._write_command(build_unit_command(unit)):
                raise RuntimeError("unit_command_write_failed")
            self.data["ble_write_validation_command_sent"] = True
            self.data["ble_write_validation_status"] = "command_sent"
            self._notify_listeners()

            await asyncio.sleep(0.5)
            for payload in diagnostic_snapshot_query_chunks():
                if not await self._write_command(payload):
                    raise RuntimeError("post_write_snapshot_query_failed")
                await asyncio.sleep(0.3)
            await asyncio.sleep(1)
            await self._read_initial_values(client)

            readback_unit = self.data.get("unit")
            self.data["ble_write_validation_readback_unit"] = readback_unit
            self.data["ble_write_validation_readback_matches"] = readback_unit == unit if readback_unit is not None else None
            self.data["ble_write_validation_status"] = "confirmed_by_readback" if readback_unit == unit else "awaiting_visual_confirmation"
        except Exception as exc:  # noqa: BLE001
            self.data["ble_write_validation_status"] = "failed"
            self.data["ble_write_validation_error"] = str(exc)[:200]
            raise
        finally:
            self.data["ble_write_validation_active"] = False
            if client is not None:
                try:
                    if client.is_connected:
                        await client.disconnect()
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.debug("INT14S unit validation disconnect failed: %s", exc)
            if self._client is client:
                self._client = None
            self._set_ble_connected(False)
            self._notify_listeners()

    async def write_ble_command(self, payload: bytes, *, request_readback: bool = True) -> bool:
        if self.profile.write_support == "not_supported":
            raise ValueError(f"INT14 writes are not implemented for {self.profile.display_name}")
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
        if self.profile.write_support == "not_supported":
            raise ValueError(f"INT14 writes are not implemented for {self.profile.display_name}")
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
        self._ensure_probe(probe)
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
        self._ensure_probe(probe)
        ble_payload = build_calibration_command(probe=probe, channel=channel, c_value=c_value)
        dp_value = build_calibration_dp_value(probe=probe, channel=channel, c_value=c_value)
        return await self.write_dps_or_ble({"110": dp_value}, ble_payload)

    async def write_pre_alarm(self, probe: int, advance_values: list[int]) -> bool:
        self._ensure_probe(probe)
        ble_payload = build_pre_alarm_command(probe, advance_values)
        dp_value = build_pre_alarm_dp_value(probe, advance_values)
        return await self.write_dps_or_ble({"116": dp_value}, ble_payload)

    async def write_timer(self, *, probe: int, start_epoch_s: int, end_epoch_s: int, count_down: bool = True) -> bool:
        self._ensure_probe(probe)
        ble_payload = build_timer_command(probe, start_epoch_s, end_epoch_s, count_down=count_down)
        dp_value = build_timer_dp_value(probe, start_epoch_s, end_epoch_s, count_down=count_down)
        ok = await self.write_dps_or_ble({str(125 + probe): dp_value}, ble_payload)
        if ok:
            self.data[f"probe_{probe}_timer_switch"] = True
            self._notify_listeners()
        return ok

    async def reset_timer(self, probe: int) -> bool:
        self._ensure_probe(probe)
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
        raw = bytes(data)
        sender_text = str(getattr(sender, "uuid", None) or sender).lower()
        if self.data.get("ble_write_validation_active"):
            notifications = self.data.setdefault("ble_write_validation_notifications", [])
            if len(notifications) < BLE_DIAGNOSTIC_MAX_NOTIFICATIONS:
                notifications.append(self._ble_diagnostic_value(sender_text, raw))
                self.data["ble_write_validation_notification_count"] = len(notifications)
        if challenge := auth_challenge_from_frame(raw):
            response = build_auth_response(challenge)
            self.data["last_ble_auth_challenge_epoch_s"] = int(time.time())
            self.data["last_ble_auth_challenge_len"] = len(challenge)
            self.data["last_ble_auth_response_len"] = len(response)
            self._auth_challenge_event.set()
            self.hass.async_create_task(self._send_auth_response(response))
        if (ok := auth_ack_ok(raw)) is not None:
            self.data["ble_auth_ok"] = ok
            self.data["last_ble_auth_ack_epoch_s"] = int(time.time())
            self.data["last_ble_auth_ack_hex"] = raw.hex()
            if ok:
                self.data["last_ble_auth_error"] = None
            self._auth_ack_event.set()
        parsed = parse_notification(bytes(data))
        if self.profile.key in {MODEL_INT12E_BW, MODEL_INT14S_BW} and "ff01" in sender_text:
            current = parse_multisensor_temperature_payload(raw, self.profile.physical_probe_count)
            if current:
                parsed["frames"].append(
                    {
                        "name": "multisensor_current_temp_candidate",
                        "transport": f"raw_ff01_{self.profile.key}",
                        **current,
                    }
                )
        elif self.profile.key == MODEL_INT12E_BW and "2a19" in sender_text:
            battery = parse_battery_payload(raw, self.profile.physical_probe_count)
            if battery:
                parsed["frames"].append(
                    {
                        "name": "battery_candidate",
                        "transport": "raw_2a19_int12e",
                        "raw_hex": raw.hex(),
                        **battery,
                    }
                )
        elif self.profile.key == MODEL_INT11I_B and "ff01" in sender_text:
            current = parse_int11i_temperature_payload(raw)
            if current:
                parsed["frames"].append({"name": "current_temp_candidate", "transport": "raw_ff01_int11i", **current})
        elif self.profile.key == MODEL_INT11I_B and "2a19" in sender_text:
            battery = parse_int11i_battery_payload(raw)
            if battery:
                parsed["frames"].append({"name": "battery_candidate", "transport": "raw_2a19_int11i", "raw_hex": raw.hex(), **battery})
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
                if idx > self.probe_count:
                    continue
                self.data[f"probe_{idx}_internal_f_tenths"] = probe["internal_f_tenths"]
                self.data[f"probe_{idx}_ambient_f_tenths"] = probe["ambient_f_tenths"]
        elif frame.get("name") == "multisensor_current_temp_candidate":
            self.data["last_transport"] = frame.get("transport")
            if not live_allowed:
                return
            self.data["base_temp_f_tenths"] = frame.get("base_temp_f_tenths")
            for probe in frame["probes"]:
                idx = probe["probe"]
                if idx > self.probe_count:
                    continue
                self.data[f"probe_{idx}_internal_f_tenths"] = probe["internal_f_tenths"]
                self.data[f"probe_{idx}_internal_raw_f_hundredths"] = probe["internal_f_hundredths"]
                for food_index, value in enumerate(probe["food_f_tenths"], start=1):
                    self.data[f"probe_{idx}_food_{food_index}_f_tenths"] = value
                self.data[f"probe_{idx}_ambient_f_tenths"] = probe["ambient_f_tenths"]
                self.data[f"probe_{idx}_multisensor_status"] = probe["status"]
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
                if idx > self.probe_count:
                    continue
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
                if idx > self.probe_count:
                    continue
                for key, value in probe.items():
                    if key != "probe":
                        self.data[f"probe_{idx}_{key}"] = value
            if self.data.get("last_battery_update_epoch_s") is not None:
                self._classify_battery_report()
        elif frame.get("name") == "target_candidate":
            self.data["last_transport"] = frame.get("transport")
            idx = frame.get("probe")
            if idx is not None and idx <= self.probe_count:
                self.data[f"probe_{idx}_target_high_f_tenths"] = frame.get("target_high_f_tenths")
                self.data[f"probe_{idx}_target_low_f_tenths"] = frame.get("target_low_f_tenths")
                self.data[f"probe_{idx}_target_mode"] = frame.get("mode_name")
                self.data[f"probe_{idx}_target_food_index"] = frame.get("food_index")
                self.data[f"probe_{idx}_target_degree_code"] = frame.get("degree_code")
        elif frame.get("name") == "pre_alarm_candidate":
            self.data["last_transport"] = frame.get("transport")
            for idx, value in enumerate(frame.get("advance_values", []), start=1):
                if idx > self.probe_count:
                    continue
                self.data[f"probe_{idx}_advance_value"] = value
        elif frame.get("name") == "timer_candidate":
            self.data["last_transport"] = frame.get("transport")
            idx = frame.get("probe")
            if idx is not None and idx <= self.probe_count:
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
                if idx > self.probe_count:
                    continue
                self.data[f"probe_{idx}_internal_calibration_c"] = value.get("c_value")
                self.data[f"probe_{idx}_internal_calibration_raw_f_tenths"] = value.get("raw_f_tenths")
            for idx, value in frame.get("ambient", {}).items():
                if idx > self.probe_count:
                    continue
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
        probes = range(1, self.probe_count + 1)
        probe_values = [value for value in (self.data.get(f"probe_{idx}_battery") for idx in probes) if value is not None]
        expected_100_len = 1 + self.probe_count
        raw_all_100 = raw_hex.startswith("64" * expected_100_len)
        probe_100_plateau = len(probe_values) >= self.probe_count and all(value == 100 for value in probe_values)

        base_charging = self.data.get("base_charging") is True
        all_probe_charging = all(self.data.get(f"probe_{idx}_charging") is True for idx in range(1, self.probe_count + 1))
        base_suspect = raw_all_100 and not base_charging
        probe_suspects = {}
        for idx in range(1, self.probe_count + 1):
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
            "model": self.profile.app_model,
            "model_profile": self.profile.key,
            "model_support_status": self.profile.support_status,
            "probe_count": self.profile.probe_count,
            "temperature_channel_count": self.profile.temperature_channel_count,
            "live_temperature_channel_count": self.profile.live_temperature_channel_count,
            "probe_layout_summary": self.profile.probe_layout_summary,
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
        if not self.profile.has_live_runtime_data:
            return "profile_cataloged_only"
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

    def _ensure_probe(self, probe: int) -> None:
        if probe < 1 or probe > self.probe_count:
            raise ValueError(f"physical probe must be 1..{self.probe_count} for {self.profile.display_name}")

    def _notify_listeners(self) -> None:
        for callback in list(self._listeners):
            callback()
