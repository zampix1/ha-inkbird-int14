from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_protocol_module():
    path = ROOT / "custom_components" / "inkbird_int14" / "protocol.py"
    spec = importlib.util.spec_from_file_location("inkbird_int14_protocol", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_int11i_ff01_temperature_uses_fahrenheit_hundredths() -> None:
    protocol = _load_protocol_module()
    raw = int(7250).to_bytes(2, "little")

    parsed = protocol.parse_int11i_temperature_payload(raw)

    assert parsed["base_temp_f_tenths"] is None
    assert parsed["probes"] == [
        {
            "probe": 1,
            "internal_f_tenths": 725,
            "ambient_f_tenths": None,
        }
    ]


def test_int11i_2a19_battery_uses_base_then_probe() -> None:
    protocol = _load_protocol_module()

    parsed = protocol.parse_int11i_battery_payload(bytes([88, 77]))

    assert parsed == {
        "base_power": 88,
        "probe_battery": {1: 77},
    }


def test_int11i_2a19_battery_handles_unknown_marker() -> None:
    protocol = _load_protocol_module()

    parsed = protocol.parse_int11i_battery_payload(bytes([0x7F, 0x7F]))

    assert parsed == {
        "base_power": None,
        "probe_battery": {1: None},
    }


def test_int14s_multisensor_ff01_shape_is_decoded_without_channel_claims() -> None:
    protocol = _load_protocol_module()
    sentinel_block = bytes.fromhex("fe7ffe7ffe7ffe7ffe7ffe7f7e")
    raw = sentinel_block * 4 + bytes.fromhex("4c03")

    parsed = protocol.parse_multisensor_temperature_payload(raw, 4)

    assert parsed["probe_block_length"] == 13
    assert parsed["temperature_slots_per_probe"] == 6
    assert parsed["base_temp_f_tenths"] == 844
    assert len(parsed["probes"]) == 4
    assert parsed["probes"][0] == {
        "probe": 1,
        "raw_f_tenths_slots": [32766] * 6,
        "available_f_tenths_slots": [None] * 6,
        "status": 0x7E,
    }


def test_multisensor_ff01_rejects_unexpected_length() -> None:
    protocol = _load_protocol_module()

    assert protocol.parse_multisensor_temperature_payload(bytes(18), 4) is None


def test_diagnostic_snapshot_queries_exclude_clock_sync_and_settings() -> None:
    protocol = _load_protocol_module()

    commands = protocol.split_frames(b"".join(protocol.diagnostic_snapshot_query_chunks()))

    assert [command.hex() for command in commands] == [frame[2:] for frame in protocol.INIT_STATIC_FRAMES]
    assert all(command[0] != 0x19 for command in commands)
