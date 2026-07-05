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
