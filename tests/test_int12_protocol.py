"""INT-12-BW issue #7 captures and characteristic-routing regressions."""

from __future__ import annotations

import ast
import importlib.util
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "inkbird_int14"
LIVE_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"
STATE_UUID = "0000ff03-0000-1000-8000-00805f9b34fb"
BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"


def _load_module(filename):
    name = f"int12_test_{filename}"
    spec = importlib.util.spec_from_file_location(name, COMPONENT / f"{filename}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def protocol():
    return _load_module("protocol")


@pytest.mark.parametrize(
    ("hex_value", "p1", "ambient", "p2", "base"),
    [
        ("d200d20018d200180203", 210, 210, 210, 770),
        ("d200d20019dc00190603", 210, 210, 220, 774),
        ("fe7ffe7f190e011ffc02", 32766, 32766, 270, 764),
        ("fe7ffe7f1a04011efc02", 32766, 32766, 260, 764),
        ("fe7ffe7f1b0e011ffc02", 32766, 32766, 270, 764),
        ("fe7ffe7f1b180120fb02", 32766, 32766, 280, 763),
    ],
)
def test_issue7_ff01_captures(protocol, hex_value, p1, ambient, p2, base):
    parsed = protocol.parse_int12_temperature_payload(bytes.fromhex(hex_value))

    def converted(value):
        return value if value in protocol.SENTINELS else protocol.c_tenths_to_f_tenths(value)

    assert parsed["probes"] == [
        {"probe": 1, "internal_f_tenths": converted(p1), "ambient_f_tenths": converted(ambient)},
        {"probe": 2, "internal_f_tenths": converted(p2), "ambient_f_tenths": None},
    ]
    assert parsed["base_temp_f_tenths"] == base


@pytest.mark.parametrize("value", [32766, 32767, -32768, -32766, -32767, -100, 0, 850])
def test_signed_probe_temperatures_and_absence_sentinels(protocol, value):
    field = value.to_bytes(2, "little", signed=True)
    raw = field * 2 + b"\x18" + field + b"\x19" + bytes.fromhex("0203")
    parsed = protocol.parse_int12_temperature_payload(raw)
    expected = abs(value) if abs(value) in protocol.SENTINELS else protocol.c_tenths_to_f_tenths(value)
    assert parsed["probes"][0]["internal_f_tenths"] == expected
    assert parsed["probes"][0]["ambient_f_tenths"] == expected
    assert parsed["probes"][1]["internal_f_tenths"] == expected


def test_unmapped_bytes_are_not_published_as_temperatures(protocol):
    raw = bytearray.fromhex("d200d20018d200180203")
    before = protocol.parse_int12_temperature_payload(raw)
    raw[4], raw[7] = 0x7F, 0xFF
    assert protocol.parse_int12_temperature_payload(raw) == before


@pytest.mark.parametrize("base", [1310, 32766, 32767, 32768, 65535])
def test_invalid_base_temperature_is_unavailable(protocol, base):
    raw = bytes.fromhex("d200d20018d20018") + base.to_bytes(2, "little")
    parsed = protocol.parse_int12_temperature_payload(raw)
    assert parsed["base_temp_f_tenths"] is None
    assert parsed["base_temp_raw"] == base


@pytest.mark.parametrize("size", [0, 3, 5, 7, 9, 11, 18, 28, 54, 512])
def test_only_ten_byte_ff01_values_are_accepted(protocol, size):
    assert protocol.parse_int12_temperature_payload(bytes(size)) is None
    assert protocol.parse_int12_ble_notification(bytes(size), LIVE_UUID)["frames"] == []


def test_three_byte_battery_order_and_sentinel(protocol):
    result = protocol.parse_int12_ble_notification(bytes.fromhex("506464"), BATTERY_UUID)
    assert result["frames"][0]["base_power"] == 80
    assert result["frames"][0]["probe_battery"] == {1: 100, 2: 100}
    result = protocol.parse_int12_ble_notification(bytes.fromhex("7f0400"), BATTERY_UUID)
    assert result["frames"][0]["base_power"] is None
    assert result["frames"][0]["probe_battery"] == {1: 4, 2: 0}
    for raw in (b"", b"\x50\x64", bytes.fromhex("5064646464")):
        assert protocol.parse_int12_ble_notification(raw, BATTERY_UUID)["frames"] == []


@pytest.mark.parametrize("hex_value", ["01100110520400", "01100110d20400", "01100110520500", "03100110520400", "03100110520500"])
def test_seven_byte_state_never_becomes_a_battery(protocol, hex_value):
    frames = protocol.parse_int12_ble_notification(bytes.fromhex(hex_value), STATE_UUID)["frames"]
    assert len(frames) == 1
    assert frames[0]["name"] == "state_candidate"
    assert frames[0]["probes"][0]["charging"] == hex_value.startswith("03")
    assert frames[0]["probes"][1]["charging"] is False
    assert "base_power" not in frames[0]


@pytest.mark.parametrize(
    ("hex_value", "names"),
    [
        ("02044301aa", ["unit_candidate"]),
        ("02044302065002fc0001aa", ["unit_candidate", "display_light_candidate", "auth_ack"]),
        ("0204430206500b1500000000000000000000", ["unit_candidate", "display_light_candidate"]),
    ],
)
def test_framed_settings_are_not_classified_by_total_length(protocol, hex_value, names):
    # These lengths match the old battery/state/temperature heuristics.
    raw = bytes.fromhex(hex_value)
    assert len(raw) in {5, 11, 18}
    frames = protocol.parse_int12_ble_notification(raw, WRITE_UUID)["frames"]
    assert [item["name"] for item in frames] == names
    assert frames[0]["unit"] == "C"
    if "display_light_candidate" in names:
        assert frames[1]["display_light"] == 80


def test_issue7_settings_and_timers_still_decode(protocol):
    settings = bytes.fromhex("05200000000002044309020110c4040000010209020210c40400000a02")
    frames = protocol.parse_int12_ble_notification(settings, WRITE_UUID)["frames"]
    assert [item["name"] for item in frames] == ["unit_candidate", "target_candidate", "target_candidate"]
    assert [(item["probe"], item["target_high_f_tenths"]) for item in frames[1:]] == [(1, 1220), (2, 1220)]
    timers = bytes.fromhex("0a260100000000000000000a26020000000000000000022604022608")
    frames = protocol.parse_int12_ble_notification(timers, WRITE_UUID)["frames"]
    assert [item["probe"] for item in frames] == [1, 2]


@pytest.mark.parametrize(
    "raw",
    [
        bytes(512),
        bytes.fromhex("03fe040203fe04020206500a0aff0000000000000000030c11024c15"),
        bytes.fromhex("02044300"),  # A trailing invalid frame must not become a raw opcode.
        bytes.fromhex("050350646464"),  # FF02 is not a raw battery source on this model.
        bytes.fromhex("0303fe04"),
    ],
)
def test_unknown_or_malformed_ff02_cannot_set_battery(protocol, raw):
    assert protocol.parse_int12_ble_notification(raw, WRITE_UUID)["frames"] == []


def test_other_characteristics_do_not_feed_live_parsers(protocol):
    assert protocol.parse_int12_ble_notification(bytes.fromhex("506464"), WRITE_UUID)["frames"] == []
    assert protocol.parse_int12_ble_notification(bytes.fromhex("d200d20018d200180203"), "unknown")["frames"] == []


def _runtime_for_replay(profile_key):
    """Execute production routing/application methods with only HA callbacks stubbed."""
    protocol = _load_module("protocol")
    auth = _load_module("auth")
    models = _load_module("models")
    tree = ast.parse((COMPONENT / "runtime.py").read_text(encoding="utf-8"))
    runtime = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Int14Runtime")
    methods = {"_notification", "_apply_frame", "_record_raw", "_classify_battery_report"}
    runtime.body = [node for node in runtime.body if isinstance(node, ast.FunctionDef) and node.name in methods]
    module = ast.Module(
        body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), runtime], type_ignores=[]
    )
    namespace = {**vars(protocol), **vars(auth), **vars(models), "time": time}
    exec(compile(ast.fix_missing_locations(module), str(COMPONENT / "runtime.py"), "exec"), namespace)
    instance = namespace["Int14Runtime"]()
    instance.profile = models.model_profile(profile_key)
    instance.probe_count = instance.profile.probe_count
    instance.data = {}
    instance._refresh_transport_state = Mock()
    instance._notify_listeners = Mock()
    instance._auth_ack_event = Mock()
    return instance


def test_runtime_preserves_real_battery_across_state_and_settings_replies():
    runtime = _runtime_for_replay("int12_bw")
    runtime._notification(BATTERY_UUID, bytearray.fromhex("506464"))
    runtime._notification(SimpleNamespace(uuid=LIVE_UUID.upper()), bytearray.fromhex("fe7ffe7f190e011ffc02"))
    runtime._notification(SimpleNamespace(uuid=STATE_UUID), bytearray.fromhex("03100110520400"))
    runtime._notification(WRITE_UUID, bytearray.fromhex("03fe040203fe04020206500a0aff0000000000000000030c11024c15"))
    runtime._notification(WRITE_UUID, bytearray(512))
    assert runtime.data["base_power"] == 80
    assert runtime.data["probe_1_battery"] == runtime.data["probe_2_battery"] == 100
    assert runtime.data["probe_1_charging"] is True
    assert runtime.data["probe_2_charging"] is False
    assert runtime.data["probe_1_internal_f_tenths"] == 32766
    assert runtime.data["probe_2_internal_f_tenths"] == 806
    assert runtime.data["probe_2_ambient_f_tenths"] is None
    assert runtime.data["last_battery_transport"] == "raw_2a19_int12"
    assert runtime.data["last_battery_len"] == 3
    assert not any(key.startswith("probe_3_") for key in runtime.data)
    runtime._notification(WRITE_UUID, bytearray.fromhex("02fc00"))
    assert runtime.data["ble_auth_ok"] is True
    runtime._auth_ack_event.set.assert_called_once()


def test_int14_baseline_raw_notifications_unchanged():
    runtime = _runtime_for_replay("int14_bw")
    runtime._notification(LIVE_UUID, bytearray.fromhex("d200d200" * 4 + "0203"))
    runtime._notification(BATTERY_UUID, bytearray.fromhex("5004636261"))
    runtime._notification(STATE_UUID, bytearray.fromhex("0110" * 4 + "010100"))
    for probe in range(1, 5):
        assert runtime.data[f"probe_{probe}_internal_f_tenths"] == 698
        assert runtime.data[f"probe_{probe}_ambient_f_tenths"] == 698
    assert runtime.data["base_temp_f_tenths"] == 770
    assert runtime.data["base_power"] == 80
    assert runtime.data["probe_1_battery"] == 4
    assert runtime.data["probe_4_battery"] == 97
    assert runtime.data["last_battery_transport"] == "raw_2a19"
