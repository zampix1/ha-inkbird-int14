"""Execute production BLE lifecycle methods with HA/radio boundary doubles.

These tests do not replace a real station/proxy wake-up test.
"""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import logging
import runpy
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "inkbird_int14"


def _runtime(monkeypatch, model="int12_bw"):
    spec = importlib.util.spec_from_file_location("reconnect_models", COMPONENT / "models.py")
    models = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, models)
    spec.loader.exec_module(models)
    bluetooth = ModuleType("homeassistant.components.bluetooth")
    bluetooth.async_ble_device_from_address = Mock(return_value=object())
    components = ModuleType("homeassistant.components")
    components.bluetooth = bluetooth
    for name, module in {
        "homeassistant": ModuleType("homeassistant"),
        "homeassistant.components": components,
        "homeassistant.components.bluetooth": bluetooth,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    namespace = runpy.run_path(str(COMPONENT / "const.py"))
    namespace.update(vars(models))
    namespace.update(
        asyncio=asyncio,
        time=time,
        logging=logging,
        BleakClient=Mock(),
        BLEDevice=Mock(return_value=object()),
        establish_connection=AsyncMock(),
    )
    tree = ast.parse((COMPONENT / "runtime.py").read_text(encoding="utf-8"))
    tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
    tree.body.insert(0, ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0))
    exec(compile(ast.fix_missing_locations(tree), str(COMPONENT / "runtime.py"), "exec"), namespace)
    runtime = namespace["Int14Runtime"](SimpleNamespace(), "AA:BB:CC:DD:EE:FF", "BLE only", model=model)
    return runtime, namespace, bluetooth


def _client():
    client = SimpleNamespace(is_connected=True)

    async def disconnect():
        client.is_connected = False

    client.disconnect = AsyncMock(side_effect=disconnect)
    return client


def test_int12_connect_refreshes_ha_device_and_limits_timeout_retries(monkeypatch):
    async def scenario():
        runtime, ns, bluetooth = _runtime(monkeypatch)
        devices = [object(), object()]
        bluetooth.async_ble_device_from_address.side_effect = devices
        ns["establish_connection"].side_effect = [TimeoutError("redacted backend failure"), _client()]
        with pytest.raises(TimeoutError):
            await runtime._connect()
        assert runtime.data["ble_connect_failure_count"] == 1
        assert runtime.data["ble_last_connect_error"] == "TimeoutError"
        await runtime._connect()
        assert runtime.data["ble_last_connect_error"] is None
        assert bluetooth.async_ble_device_from_address.call_count == 2
        for call, device in zip(ns["establish_connection"].await_args_list, devices, strict=True):
            assert call.args[1] is device
            assert call.kwargs["max_attempts"] == 1
            assert callable(call.kwargs["disconnected_callback"])

    asyncio.run(scenario())


def test_missing_scanner_device_waits_for_real_ha_discovery(monkeypatch):
    async def scenario():
        runtime, ns, bluetooth = _runtime(monkeypatch)
        bluetooth.async_ble_device_from_address.return_value = None
        with pytest.raises(RuntimeError, match="not visible"):
            await runtime._connect()
        ns["BLEDevice"].assert_not_called()
        ns["establish_connection"].assert_not_awaited()
        assert runtime.data["ble_last_connect_error"] == "device_not_seen"
        assert runtime.data["ble_connect_failure_count"] == 1

    asyncio.run(scenario())


def test_disconnect_callback_wakes_long_poll_and_old_session_is_isolated(monkeypatch):
    async def scenario():
        runtime, ns, _ = _runtime(monkeypatch)
        first, second = _client(), _client()
        ns["establish_connection"].side_effect = [first, second]
        await runtime._connect()
        old_callback = ns["establish_connection"].await_args.kwargs["disconnected_callback"]
        await runtime._connect()
        callback = ns["establish_connection"].await_args.kwargs["disconnected_callback"]
        first.is_connected = False
        old_callback(first)
        assert not runtime._ble_disconnected.is_set()
        callback(second)
        assert not runtime._ble_disconnected.is_set()
        runtime.ble_poll_seconds = 300
        runtime._read_values = AsyncMock()
        task = asyncio.create_task(runtime._listen(second))
        await asyncio.sleep(0)
        second.is_connected = False
        callback(second)
        await asyncio.wait_for(task, 0.5)
        runtime._read_values.assert_not_awaited()

    asyncio.run(scenario())


def test_continuous_session_polls_without_twenty_second_cutoff(monkeypatch):
    async def scenario():
        runtime, ns, _ = _runtime(monkeypatch)
        client = _client()
        intervals = []
        calls = []

        async def wait_for(awaitable, timeout):
            if timeout == runtime.ble_poll_seconds:
                intervals.append(timeout)
                awaitable.close()
                raise TimeoutError
            return await awaitable

        async def read_values(actual, uuids):
            assert actual is client
            calls.append(uuids)
            if len(calls) == 4:
                client.is_connected = False

        runtime.ble_poll_seconds = 7
        runtime._read_values = read_values
        ns["asyncio"] = SimpleNamespace(wait_for=wait_for, TimeoutError=TimeoutError)
        await runtime._listen(client)
        assert intervals == [7, 7, 7, 7]
        assert calls == [(ns["LIVE_UUID"], ns["STATE_UUID"], ns["BATTERY_UUID"])] * 4
        client.disconnect.assert_not_awaited()

    asyncio.run(scenario())


def test_stalled_fallback_read_exits_session_for_recovery(monkeypatch):
    async def scenario():
        runtime, ns, _ = _runtime(monkeypatch)
        runtime.ble_poll_seconds = 0.001
        ns["INT12_READ_TIMEOUT_SECONDS"] = 0.01
        cancelled = asyncio.Event()

        async def stalled(*args):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        runtime._read_values = stalled
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(runtime._listen(_client()), 0.5)
        assert cancelled.is_set()

    asyncio.run(scenario())


def test_loop_recovers_after_failed_connect_without_snapshot(monkeypatch):
    async def scenario():
        runtime, ns, bluetooth = _runtime(monkeypatch)
        client = _client()
        ns["establish_connection"].side_effect = [TimeoutError, client]
        runtime._subscribe = AsyncMock()
        runtime._listen = AsyncMock()
        runtime._request_init_on_client = AsyncMock()
        waits = []

        async def retry(seconds):
            waits.append(seconds)
            if len(waits) == 2:
                raise asyncio.CancelledError

        runtime._sleep_or_mode_change = retry
        with pytest.raises(asyncio.CancelledError):
            await runtime._run()
        assert waits == [10, 5]
        assert bluetooth.async_ble_device_from_address.call_count == 2
        runtime._subscribe.assert_awaited_once_with(client)
        runtime._listen.assert_awaited_once_with(client)
        runtime._request_init_on_client.assert_not_awaited()
        client.disconnect.assert_awaited_once()
        assert runtime._client is None
        assert not runtime._connection_lock.locked()
        assert runtime.data["ble_connection_count"] == 1
        assert runtime.data["ble_connect_failure_count"] == 1

    asyncio.run(scenario())


def test_docked_missing_device_reappears_without_manual_snapshot(monkeypatch):
    async def scenario():
        runtime, ns, bluetooth = _runtime(monkeypatch)
        bluetooth.async_ble_device_from_address.side_effect = [None, None, object()]
        ns["establish_connection"].return_value = _client()
        runtime._subscribe = AsyncMock()
        runtime._listen = AsyncMock()
        waits = []

        async def retry(seconds):
            waits.append(seconds)
            if len(waits) == 3:
                raise asyncio.CancelledError

        runtime._sleep_or_mode_change = retry
        with pytest.raises(asyncio.CancelledError):
            await runtime._run()
        assert waits == [10, 10, 5]
        assert runtime.data["ble_connection_count"] == 1
        assert runtime.data["ble_connect_failure_count"] == 2
        ns["establish_connection"].assert_awaited_once()

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["connect", "subscribe", "listen", "backoff"])
def test_cancellation_stops_loop_and_releases_connection_lock(monkeypatch, stage):
    async def scenario():
        runtime, _, _ = _runtime(monkeypatch)
        client = _client()
        runtime._connect = AsyncMock(return_value=client)
        runtime._subscribe = AsyncMock()
        runtime._listen = AsyncMock()
        runtime._sleep_or_mode_change = AsyncMock()
        methods = {"connect": "_connect", "subscribe": "_subscribe", "listen": "_listen", "backoff": "_sleep_or_mode_change"}
        getattr(runtime, methods[stage]).side_effect = asyncio.CancelledError
        with pytest.raises(asyncio.CancelledError):
            await runtime._run()
        assert runtime._client is None
        assert not runtime._connection_lock.locked()
        assert runtime.data["ble_connected"] is False
        assert runtime._connect.await_count == 1
        assert client.disconnect.await_count == (0 if stage == "connect" else 1)

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["subscribe", "disconnect"])
def test_stalled_setup_or_cleanup_is_bounded_and_retries(monkeypatch, stage):
    async def scenario():
        runtime, ns, _ = _runtime(monkeypatch)
        client = _client()
        runtime._connect = AsyncMock(return_value=client)
        runtime._subscribe = AsyncMock()
        runtime._listen = AsyncMock()
        runtime._sleep_or_mode_change = AsyncMock(side_effect=asyncio.CancelledError)
        ns["INT12_SUBSCRIBE_TIMEOUT_SECONDS"] = 0.01
        ns["INT12_DISCONNECT_TIMEOUT_SECONDS"] = 0.01
        cancelled = asyncio.Event()

        async def stalled(*args):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        if stage == "subscribe":
            runtime._subscribe = stalled
        else:
            client.disconnect.side_effect = stalled
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(runtime._run(), 0.5)
        assert cancelled.is_set()
        assert runtime._client is None
        assert not runtime._connection_lock.locked()
        assert runtime.data["ble_connected"] is False
        runtime._sleep_or_mode_change.assert_awaited_once_with(10)

    asyncio.run(scenario())


def test_transport_change_stops_active_wait_without_another_read(monkeypatch):
    async def scenario():
        runtime, ns, _ = _runtime(monkeypatch)
        client = _client()
        ns["establish_connection"].return_value = client
        await runtime._connect()
        callback = ns["establish_connection"].await_args.kwargs["disconnected_callback"]

        async def disconnect():
            client.is_connected = False
            callback(client)

        client.disconnect.side_effect = disconnect
        runtime._client = client
        runtime.ble_poll_seconds = 300
        runtime._read_values = AsyncMock()
        task = asyncio.create_task(runtime._listen(client))
        await asyncio.sleep(0)
        await runtime.set_transport_mode(ns["TRANSPORT_MODE_WIFI_LAN_ONLY"])
        await asyncio.wait_for(task, 0.5)
        runtime._read_values.assert_not_awaited()
        assert not runtime.ble_enabled

    asyncio.run(scenario())


def test_transport_disabled_during_connect_only_runs_bounded_cleanup(monkeypatch):
    async def scenario():
        runtime, ns, _ = _runtime(monkeypatch)
        client = _client()

        async def connect():
            runtime.transport_mode = ns["TRANSPORT_MODE_WIFI_LAN_ONLY"]
            return client

        runtime._connect = AsyncMock(side_effect=connect)
        runtime._subscribe = AsyncMock()
        runtime._sleep_or_mode_change = AsyncMock(side_effect=asyncio.CancelledError)
        with pytest.raises(asyncio.CancelledError):
            await runtime._run()
        runtime._subscribe.assert_not_awaited()
        client.disconnect.assert_awaited_once()
        assert not runtime._connection_lock.locked()
        assert runtime._client is None

    asyncio.run(scenario())


def test_connection_metrics_are_transition_based_and_private_error_free(monkeypatch):
    runtime, ns, _ = _runtime(monkeypatch)
    ns["time"] = SimpleNamespace(time=Mock(side_effect=[100, 127]))
    runtime._refresh_transport_state = Mock()
    runtime._set_ble_connected(True)
    runtime._set_ble_connected(True)
    runtime._set_ble_connected(False)
    runtime._set_ble_connected(False)
    assert runtime.data["ble_connection_count"] == 1
    assert runtime.data["ble_last_connected_epoch_s"] == 100
    assert runtime.data["ble_last_disconnected_epoch_s"] == 127
    assert runtime.data["ble_last_session_seconds"] == 27


@pytest.mark.parametrize("model, delay", [("int14_bw", 25), ("int14s_bw", 25), ("int12e_bw", 5)])
def test_other_models_keep_existing_connect_policy(monkeypatch, model, delay):
    async def scenario():
        runtime, ns, _ = _runtime(monkeypatch, model)
        await runtime._connect()
        assert runtime._ble_reconnect_delay_seconds == delay
        assert ns["establish_connection"].await_args.kwargs == {"max_attempts": 4, "timeout": 20.0}
        assert "ble_last_connect_attempt_epoch_s" not in runtime.data

    asyncio.run(scenario())


def test_int14_still_has_a_timed_session_and_int12e_keeps_existing_reads(monkeypatch):
    async def scenario():
        runtime, ns, _ = _runtime(monkeypatch, "int14_bw")
        clock = Mock(side_effect=[0, 0, 10, 20])
        sleeper = AsyncMock()
        ns["asyncio"] = SimpleNamespace(get_running_loop=lambda: SimpleNamespace(time=clock), sleep=sleeper)
        await runtime._listen(_client())
        assert [call.args[0] for call in sleeper.await_args_list] == [1, 1]

        runtime, ns, _ = _runtime(monkeypatch, "int12e_bw")
        client = _client()

        async def read(*args):
            client.is_connected = False

        runtime._read_values = AsyncMock(side_effect=read)
        ns["asyncio"] = SimpleNamespace(sleep=AsyncMock())
        await runtime._listen(client)
        runtime._read_values.assert_awaited_once_with(client, (ns["LIVE_UUID"], ns["BATTERY_UUID"]))

    asyncio.run(scenario())
