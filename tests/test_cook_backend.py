"""HA boundary contracts using isolated registries, stores and a service recorder."""

import ast
import asyncio
import re
import time
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_cook_sessions import MODULE, device

SOURCE = Path(__file__).resolve().parents[1] / "examples/cook_control/custom_components/inkbird_cook_control/__init__.py"
TREE = ast.parse(SOURCE.read_text(encoding="utf-8"))


class MemoryStore:
    files = {}

    def __init__(self, _hass, _version, key):
        self.key = key

    async def async_load(self):
        return deepcopy(self.files.get(self.key))

    async def async_save(self, data):
        self.files[self.key] = deepcopy(data)


def boundary(states=None, entities=None, devices=None):
    state_map = {key: SimpleNamespace(state=value[0], attributes=value[1]) for key, value in (states or {}).items()}
    hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda key: state_map.get(key), async_set=lambda *args: None),
        services=SimpleNamespace(async_call=AsyncMock()),
    )
    namespace = {
        "asyncio": asyncio,
        "deepcopy": deepcopy,
        "timedelta": timedelta,
        "re": re,
        "time": time,
        "callback": lambda func: func,
        "Engine": MODULE.Engine,
        "number": MODULE.number,
        "announcement": MODULE.announcement,
        "Store": MemoryStore,
        "DOMAIN": "inkbird_cook_control",
        "LOGGER": SimpleNamespace(exception=lambda *_: None),
        "er": SimpleNamespace(async_get=lambda _: SimpleNamespace(entities=entities or {})),
        "dr": SimpleNamespace(async_get=lambda _: SimpleNamespace(async_get=lambda key: (devices or {}).get(key))),
        "async_track_time_interval": lambda *_: lambda: None,
    }
    nodes = [
        node
        for node in TREE.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in {"state_value", "temperature", "discover", "Manager"}
    ]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return hass, namespace


def test_registry_identity_survives_renamed_entities_and_excludes_other_profiles():
    entities = {}
    for key, platform in [("a", "inkbird_iht2pb"), ("b", "inkbird_iht2pb"), ("unsupported", "inkbird_int14")]:
        for n in range(1, 4):
            entities[f"{key}{n}"] = SimpleNamespace(
                platform=platform,
                device_id=key,
                disabled_by=None,
                entity_id=f"sensor.renamed_{key}_{n}",
                unique_id=f"redacted_probe_{n}_temp",
            )
        entities[f"{key}epoch"] = SimpleNamespace(
            platform=platform,
            device_id=key,
            disabled_by=None,
            entity_id=f"sensor.renamed_epoch_{key}",
            unique_id="redacted_last_update_epoch_s",
        )
    devices = {
        key: SimpleNamespace(model="INT-31-BW" if key == "unsupported" else "IHT-2PB", name="Handheld", name_by_user=None)
        for key in ("a", "b", "unsupported")
    }
    hass, ns = boundary(entities=entities, devices=devices)
    found = ns["discover"](hass)
    assert {item["id"] for item in found} == {"a", "b"}
    assert found[0]["layout"][2]["entity"] == "sensor.renamed_a_3"
    assert found[0]["epochs"] == ["sensor.renamed_epoch_a"]


def test_temperature_conversion_and_invalid_values():
    hass, ns = boundary({"sensor.fahrenheit": ("185", {"unit_of_measurement": "\u00b0F"}), "sensor.missing": ("unknown", {})})
    assert ns["temperature"](hass, "sensor.fahrenheit") == 85
    assert ns["temperature"](hass, "sensor.missing") is None


def test_manager_migration_is_once_only_and_keeps_current_values():
    MemoryStore.files = {}
    hass, ns = boundary(
        {
            "input_text.inkbird_sensor_prefix": ("sensor.test_station", {}),
            "input_number.inkbird_target_1": ("85", {}),
            "input_boolean.bbq_probe_1_enabled": ("on", {}),
            "input_text.inkbird_name_1": ("Musetto", {}),
            "input_text.bbq_last_alert_1": ("old-alert", {}),
        }
    )
    descriptor = device("station", "int14_bw")
    ns["discover"] = lambda _: [descriptor]
    manager = ns["Manager"](hass)
    asyncio.run(manager.initialize())
    config = manager.engine.data["devices"]["station"]["channels"]["1"]
    assert config["target"] == 85 and config["armed"] and config["name"] == "Musetto"
    assert config["alerted"] == config["generation"]
    sid = manager.engine.data["devices"]["station"]["session"]
    restored = ns["Manager"](hass)
    asyncio.run(restored.initialize())
    assert restored.engine.data["devices"]["station"]["session"] == sid
    assert len(restored.engine.data["index"]) == 1


def test_notification_path_is_only_existing_router_and_speech_is_human():
    MemoryStore.files = {}
    hass, ns = boundary({"input_select.bbq_language": ("Italiano", {})})
    manager = ns["Manager"](hass)
    manager.engine.discover([device("station", "int14_bw")])
    manager.engine.configure("station", "1", {"target": 85, "name": "Musetto", "armed": True}, 1000)
    notice = {
        "device_id": "station",
        "channel": "1",
        "name": "Musetto",
        "temperature": 85,
        "session": manager.engine.data["devices"]["station"]["session"],
        "generation": 2,
        "kind": "target",
    }
    asyncio.run(manager.notify(notice))
    args = hass.services.async_call.call_args
    assert args.args[:2] == ("script", "bbq_notify")
    assert args.args[2]["tts_message"] == "Musetto ha raggiunto 85 gradi."
    assert "station" not in args.args[2]["actions"][0]["action"]
    assert args.kwargs["blocking"] is True


def test_websocket_auth_and_archive_path_guards():
    source = SOURCE.read_text(encoding="utf-8")
    assert source.count("@websocket_api.require_admin") == 2
    hass, ns = boundary()
    manager = ns["Manager"](hass)
    for invalid in ("../private", "", "session/1", "a" * 33):
        with pytest.raises(ValueError):
            manager.archive_store(invalid)
    assert 'async_call("inkbird' not in source
