"""Optional dashboard contracts. Fixtures are not physical hardware tests."""

import math
import re
import runpy
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
import yaml
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = yaml.safe_load((ROOT / "examples/cook_control/packages/inkbird_bbq.yaml").read_text(encoding="utf-8"))
AUTOMATIONS = {a["id"]: a for a in PACKAGE["automation"]}
SENSORS = {s["unique_id"]: s for s in PACKAGE["template"][0]["sensor"]}
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class States:
    def __init__(self, values):
        self.values = values

    def __call__(self, key):
        return str(self.values.get(key, "unknown"))

    def __getitem__(self, key):
        if key not in self.values:
            return None
        return SimpleNamespace(
            state=self(key),
            last_changed=self.values.get(key + ":changed", NOW),
            context=SimpleNamespace(id=self.values.get(key + ":context", "test-context")),
        )

    def __getattr__(self, domain):
        parent = self

        class Domain:
            def __getattr__(self, key):
                return parent[domain + "." + key]

        return Domain()


def render(source, values=None, **variables):
    values = values or {}
    states = States(values)
    env = Environment(undefined=StrictUndefined)
    env.filters["regex_match"] = lambda value, pattern: re.match(pattern, value) is not None
    env.filters["bitwise_and"] = lambda a, b: a & b
    env.tests["match"] = lambda value, pattern: re.match(pattern, value) is not None

    def is_number(value):
        try:
            return math.isfinite(float(value))
        except (ValueError, TypeError):
            return False

    env.globals.update(
        states=states,
        is_state=lambda key, value: states(key) == value,
        has_value=lambda key: states(key) not in ("unknown", "unavailable"),
        state_attr=lambda key, attr: values.get(key + ":" + attr),
        now=lambda: NOW,
        as_timestamp=lambda value: value.timestamp(),
        is_number=is_number,
    )
    return env.from_string(source).render(**variables).strip()


def live_values(n=1):
    return {
        "input_text.inkbird_sensor_prefix": "sensor.test_inkbird",
        "input_text.inkbird_sensor_prefix:changed": datetime(2025, 12, 31, tzinfo=timezone.utc),
        f"input_text.inkbird_name_{n}": "Probe",
        "sensor.test_inkbird_last_ble_update_epoch": NOW.timestamp() - 10,
        f"sensor.test_inkbird_probe_{n}_internal_temperature": "85",
        f"input_boolean.bbq_probe_{n}_enabled": "on",
        f"sensor.bbq_probe_{n}_control_temperature": "85",
        f"sensor.bbq_probe_{n}_control_temperature:source_prefix": "sensor.test_inkbird",
        f"sensor.bbq_probe_{n}_control_temperature:source_entity": f"sensor.test_inkbird_probe_{n}_internal_temperature",
        f"sensor.bbq_probe_{n}_control_temperature:rate_valid_after": NOW.timestamp() - 1,
        f"sensor.bbq_probe_{n}_status:source_prefix": "sensor.test_inkbird",
        f"sensor.bbq_probe_{n}_status:source_entity": f"sensor.test_inkbird_probe_{n}_internal_temperature",
        f"input_number.inkbird_target_{n}": "85",
    }


@pytest.mark.parametrize("n", range(1, 5))
@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({}, "ready"),
        ({"temperature": "70"}, "heating"),
        ({"temperature": "82"}, "close"),
        ({"temperature": "unavailable"}, "idle"),
        ({"temperature": "fault"}, "idle"),
        ({"enabled": "off"}, "idle"),
        ({"target": "0"}, "idle"),
        ({"age": 121}, "idle"),
        ({"age": -61}, "idle"),
        ({"age": 120}, "ready"),
    ],
)
def test_alarm_status(n, change, expected):
    values = live_values(n)
    keys = {
        "temperature": f"sensor.bbq_probe_{n}_control_temperature",
        "target": f"input_number.inkbird_target_{n}",
        "enabled": f"input_boolean.bbq_probe_{n}_enabled",
    }
    for key, value in change.items():
        if key == "age":
            values["sensor.test_inkbird_last_ble_update_epoch"] = NOW.timestamp() - value
        else:
            values[keys[key]] = value
    assert render(SENSORS[f"bbq_probe_{n}_status"]["state"], values) == expected


def test_control_conversion_and_non_numeric():
    sensor = SENSORS["bbq_probe_1_control_temperature"]
    entity_id = "sensor.test_inkbird_probe_1_internal_temperature"
    values = live_values()
    values.update({entity_id: "185", entity_id + ":unit_of_measurement": "\u00b0F"})
    assert float(render(sensor["state"], values)) == 85
    for invalid in ("unknown", "unavailable", "nan", "inf", "fault"):
        values[entity_id] = invalid
        assert render(sensor["availability"], values) == "False"


@pytest.mark.parametrize(
    "action,valid",
    [
        ("BBQ_SNOOZE_1", True),
        ("BBQ_DISMISS_4", True),
        ("BBQ_", False),
        ("BBQ_SNOOZE_9", False),
        ("BBQ_DISMISS_1_extra", False),
        (None, False),
        (12, False),
    ],
)
def test_action_validation(action, valid):
    source = AUTOMATIONS["inkbird_bbq_notification_action"]["conditions"][0]["value_template"]
    assert (render(source, trigger={"event": {"data": {"action": action}}}) == "True") is valid


def test_dismiss_and_cancel_stop_both_reminders():
    handler = AUTOMATIONS["inkbird_bbq_notification_action"]["actions"][-1]
    assert handler["default"][0]["action"] == "script.turn_off"
    assert "bbq_snooze_" in handler["default"][0]["target"]["entity_id"]
    assert "bbq_rest_" in handler["default"][0]["target"]["entity_id"]
    cancel = AUTOMATIONS["inkbird_bbq_cancel_pending"]
    assert len(cancel["triggers"]) == 9
    for n in range(1, 5):
        for kind in ("snooze", "rest"):
            script = PACKAGE["script"][f"bbq_{kind}_{n}"]
            assert script["mode"] == "restart"
            guard = script["sequence"][4]["value_template"]
            values = live_values(n)
            values[f"sensor.bbq_probe_{n}_status"] = "ready"
            assert render(guard, values, current_session="new", session_at_start="old") == "False"
            assert render(guard, values, current_session="same", session_at_start="same") == "True"
            values[f"sensor.bbq_probe_{n}_status"] = "idle"
            assert render(guard, values, current_session="same", session_at_start="same") == "False"


def test_reconnect_does_not_duplicate_alert_or_restart_reminder():
    auto = AUTOMATIONS["inkbird_bbq_probe_reached_target"]
    source = auto["variables"]["session_key"]
    values = live_values()
    key = render(source, values, trigger={"id": "1"})
    values["input_text.bbq_last_alert_1"] = key
    assert render(auto["conditions"][1]["value_template"], values, session_key=key, trigger={"id": "1"}) == "False"
    assert auto["actions"][2]["event"] == "inkbird_bbq_target_reached"
    assert all(t["trigger"] == "event" for t in AUTOMATIONS["inkbird_bbq_rest_reminder"]["triggers"])


@pytest.mark.parametrize(
    "battery,status,suspect,expected",
    [
        (4, "heating", "off", True),
        (4, "idle", "off", False),
        (4, "heating", "on", False),
        (100, "heating", "off", False),
        ("unavailable", "heating", "off", False),
        (-1, "heating", "off", False),
    ],
)
def test_battery_requires_use_freshness_and_valid_report(battery, status, suspect, expected):
    values = live_values()
    values.update(
        {
            "sensor.test_inkbird_probe_1_battery": battery,
            "sensor.bbq_probe_1_status": status,
            "binary_sensor.test_inkbird_probe_battery_report_suspect": suspect,
            "input_boolean.bbq_battery_alerts": "on",
            "input_number.bbq_battery_threshold": "15",
        }
    )
    assert (render(AUTOMATIONS["inkbird_bbq_probe_battery_low"]["triggers"][0]["value_template"], values) == "True") is expected


def test_stall_timer_requires_continuous_fresh_active_readings():
    trigger = AUTOMATIONS["inkbird_bbq_probe_stalled"]["triggers"][0]
    assert trigger["for"] == "00:45:00"
    values = live_values()
    values.update({"sensor.bbq_probe_1_status": "heating", "input_boolean.bbq_stall_alerts": "on", "sensor.bbq_probe_1_rate": "0.2"})
    assert render(trigger["value_template"], values) == "True"
    values["sensor.bbq_probe_1_status"] = "idle"
    assert render(trigger["value_template"], values) == "False"


def test_notification_router_and_non_intrusive_media():
    sequence = PACKAGE["script"]["bbq_notify"]["sequence"]
    assert sequence[0]["action"] == "persistent_notification.create"
    voice = sequence[-1]["then"][1]
    values = {"media_player.test_echo": "idle"}
    args = {"engine": "Alexa (native)", "speaker": "media_player.test_echo", "alexa_speaker": True}
    assert render(voice["choose"][1]["conditions"], values, **args) == "True"
    values["media_player.test_echo"] = "unavailable"
    assert render(voice["choose"][1]["conditions"], values, **args) == "False"
    assert voice["default"][-1]["error"] is True
    tv = sequence[-2]["then"][1]["choose"][0]
    assert render(tv["conditions"], {"media_player.test_tv": "on"}, tv_service="test_tv", tv_entity="media_player.test_tv") == "True"
    assert render(tv["sequence"][0]["if"], {"media_player.test_tv": "off"}, tv_entity="media_player.test_tv") == "False"
    for forbidden in ("media_player.turn_on", "media_player.volume_set", "media_player.select_source", "inkbird_int14."):
        assert forbidden not in str(PACKAGE)


def test_helpers_restore_and_no_default_devices():
    for domain in ("input_text", "input_number", "input_boolean", "input_select"):
        assert all("initial" not in helper for helper in PACKAGE[domain].values())
    assert PACKAGE["input_select"]["bbq_tts_speaker"]["options"] == ["none"]
    assert PACKAGE["input_select"]["inkbird_dashboard_model"]["options"] == ["INT-14-BW", "IHT-2PB"]


def test_alexa_group_targets_are_exactly_configured_available_echoes():
    variables = PACKAGE["script"]["bbq_notify"]["sequence"][-1]["then"][0]["variables"]
    values = {
        "input_text.bbq_alexa_group_targets": "media_player.test_living, media_player.test_dining",
        "input_text.bbq_alexa_group_name": "Day zone",
        "input_select.bbq_tts_speaker": "Day zone",
        "media_player.test_living": "idle",
        "media_player.test_dining": "idle",
        "media_player.test_bedroom": "idle",
    }

    def entities(_):
        return ["media_player.test_living", "media_player.test_dining", "media_player.test_bedroom"]

    targets = render(variables["alexa_targets"], values, integration_entities=entities)
    assert targets == "['media_player.test_living', 'media_player.test_dining']"
    assert render(variables["alexa_group"], values, alexa_targets=["media_player.test_living", "media_player.test_dining"]) == "True"
    values["input_text.bbq_alexa_group_targets"] += ", media_player.not_an_echo"
    assert render(variables["alexa_targets"], values, integration_entities=entities) == "[]"


def test_bundle_is_reproducible_and_has_no_household_or_development_files(tmp_path):
    builder = runpy.run_path(str(ROOT / "examples/cook_control/build_bundle.py"))
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    builder["build"](first)
    builder["build"](second)
    assert first.read_bytes() == second.read_bytes()
    with ZipFile(first) as archive:
        assert len(archive.namelist()) == 20
        assert set(archive.namelist()) == set(builder["FILES"].values()) | {"cook-control/LICENSE.integration"}
        for filename in archive.namelist():
            assert ".." not in Path(filename).parts
            content = archive.read(filename).decode("utf-8")
            for private_pattern in (
                r"\b(?:10|192\.168|172\.(?:1[6-9]|2[0-9]|3[01]))\.(?:\d{1,3}\.)?\d{1,3}\.\d{1,3}\b",
                r"\b[A-Za-z]:[/\\]Users[/\\]",
                r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b",
            ):
                assert not re.search(private_pattern, content)
