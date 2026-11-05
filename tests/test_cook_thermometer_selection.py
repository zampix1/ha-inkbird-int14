"""Render the optional package's selection and source-isolation contracts."""

import ast
from datetime import timedelta
from types import SimpleNamespace

import pytest
from test_cook_control import AUTOMATIONS, NOW, PACKAGE, SENSORS, live_values, render

PREFIX = "sensor.test_inkbird"
IHT_SUFFIXES = ("_built_in_temperature", "_external_1_temperature", "_external_2_temperature")


def source_values(model, n=1):
    values = live_values(n)
    if model == "iht":
        for suffix in IHT_SUFFIXES:
            values[PREFIX + suffix] = "85"
        values[PREFIX + "_last_update_epoch"] = NOW.timestamp() - 10
        entity = PREFIX + IHT_SUFFIXES[n - 1] if n < 4 else None
    else:
        for i in range(1, 5):
            values[f"{PREFIX}_probe_{i}_internal_temperature"] = "85"
        entity = f"{PREFIX}_probe_{n}_internal_temperature"
    for kind in ("control_temperature", "status"):
        values[f"sensor.bbq_probe_{n}_{kind}:source_entity"] = entity
    return values


def truth(template, values, **variables):
    return render(template, values, **variables).lower() == "true"


@pytest.mark.parametrize("model", ("int", "iht"))
@pytest.mark.parametrize("n", range(1, 5))
@pytest.mark.parametrize("fahrenheit", (False, True))
def test_source_mapping_and_fahrenheit(model, n, fahrenheit):
    values = source_values(model, n)
    control = SENSORS[f"bbq_probe_{n}_control_temperature"]
    expected = PREFIX + IHT_SUFFIXES[n - 1] if model == "iht" and n < 4 else f"{PREFIX}_probe_{n}_internal_temperature"
    values[expected] = "185" if fahrenheit else "85"
    values[expected + ":unit_of_measurement"] = "\u00b0F" if fahrenheit else "\u00b0C"
    if model == "iht" and n == 4:
        # Even an accidentally present INT-style fourth channel must be ignored.
        assert not truth(control["availability"], values)
        assert render(control["state"], values) == "None"
        assert render(control["attributes"]["source_entity"], values) == "None"
        assert render(SENSORS[f"bbq_probe_{n}_status"]["state"], values) == "idle"
    else:
        assert truth(control["availability"], values)
        assert float(render(control["state"], values)) == 85
        assert render(control["attributes"]["source_entity"], values) == expected
        assert render(control["attributes"]["source_prefix"], values) == PREFIX
        assert render(SENSORS[f"bbq_probe_{n}_status"]["state"], values) == "ready"


@pytest.mark.parametrize("model", ("int", "iht"))
@pytest.mark.parametrize("age,valid", [(120, True), (121, False), (-60, True), (-61, False)])
def test_freshness_is_source_specific(model, age, valid):
    values = source_values(model)
    key = "_last_update_epoch" if model == "iht" else "_last_ble_update_epoch"
    values[PREFIX + key] = NOW.timestamp() - age
    # The other model's fresh timestamp must not rescue this source.
    values[PREFIX + ("_last_ble_update_epoch" if model == "iht" else "_last_update_epoch")] = NOW.timestamp()
    assert truth(SENSORS["bbq_probe_1_control_temperature"]["availability"], values) is valid
    assert (render(SENSORS["bbq_probe_1_status"]["state"], values) == "ready") is valid


def test_int_lan_can_supply_freshness_without_ble():
    values = source_values("int")
    values[PREFIX + "_last_ble_update_epoch"] = "unknown"
    values[PREFIX + "_last_lan_update_epoch"] = NOW.timestamp() - 30
    assert truth(SENSORS["bbq_probe_1_control_temperature"]["availability"], values)
    assert render(SENSORS["bbq_probe_1_status"]["state"], values) == "ready"


@pytest.mark.parametrize("model", ("int", "iht"))
@pytest.mark.parametrize("invalid", ("unknown", "unavailable", "fault", "nan", "inf", "-inf"))
def test_unknown_readings_and_cold_start_fail_closed(model, invalid):
    values = source_values(model)
    source = PREFIX + (IHT_SUFFIXES[0] if model == "iht" else "_probe_1_internal_temperature")
    values[source] = invalid
    control = SENSORS["bbq_probe_1_control_temperature"]
    assert not truth(control["availability"], values)
    assert render(control["state"], values) == "None"
    assert render(SENSORS["bbq_probe_1_status"]["state"], values) == "idle"
    # An existing but unknown built-in entity still identifies IHT, never INT.
    assert render(control["attributes"]["source_entity"], values) == source
    values.pop(PREFIX + ("_last_update_epoch" if model == "iht" else "_last_ble_update_epoch"))
    assert not truth(control["availability"], values)


@pytest.mark.parametrize("n", range(1, 5))
@pytest.mark.parametrize("attr", ("source_prefix", "source_entity"))
def test_old_control_first_frame_cannot_be_ready(n, attr):
    values = source_values("int", n)
    values[f"sensor.bbq_probe_{n}_control_temperature:{attr}"] = "sensor.previous_cook"
    assert render(SENSORS[f"bbq_probe_{n}_status"]["state"], values) == "idle"
    values[f"sensor.bbq_probe_{n}_status"] = "ready"
    guard = AUTOMATIONS["inkbird_bbq_probe_reached_target"]["conditions"][2]["value_template"]
    assert not truth(guard, values, trigger={"id": str(n)})


@pytest.mark.parametrize("model", ("int", "iht"))
@pytest.mark.parametrize("n", (1, 2, 3))
def test_status_provenance_tracks_control_not_just_new_prefix(model, n):
    values = source_values(model, n)
    values[f"sensor.bbq_probe_{n}_control_temperature:source_prefix"] = "sensor.previous_cook"
    status = SENSORS[f"bbq_probe_{n}_status"]
    assert render(status["attributes"]["source_prefix"], values) == "sensor.previous_cook"
    assert render(status["attributes"]["source_entity"], values) == values[f"sensor.bbq_probe_{n}_control_temperature:source_entity"]


def evaluate(value, values, variables):
    if not isinstance(value, str) or "{{" not in value and "{%" not in value:
        return value
    rendered = render(value, values, **variables)
    try:
        return ast.literal_eval(rendered)
    except (ValueError, SyntaxError):
        return rendered


def run_sequence(sequence, values, variables, calls):
    """Small service recorder, not a Home Assistant execution-engine substitute."""
    for step in sequence:
        if "if" in step:
            if truth(step["if"], values, **variables):
                run_sequence(step["then"], values, variables, calls)
            continue
        if "stop" in step:
            raise ValueError(step["stop"])
        if "condition" in step:
            if not truth(step["value_template"], values, **variables):
                return False
            continue
        if "variables" in step:
            for key, value in step["variables"].items():
                variables[key] = evaluate(value, values, variables)
            continue
        if "repeat" in step:
            for index in range(1, step["repeat"]["count"] + 1):
                run_sequence(step["repeat"]["sequence"], values, {**variables, "repeat": {"index": index}}, calls)
            continue
        action = step["action"]
        data = {k: evaluate(v, values, variables) for k, v in step.get("data", {}).items()}
        if action == "script.bbq_reset_cook":
            run_sequence(PACKAGE["script"]["bbq_reset_cook"]["sequence"], values, data, calls)
            continue
        entities = evaluate(step["target"]["entity_id"], values, variables)
        entities = entities if isinstance(entities, list) else [entities]
        calls.append((action, entities, data))
        for entity in entities:
            if action in ("input_boolean.turn_off", "script.turn_off"):
                values[entity] = "off"
            elif action in ("input_text.set_value", "input_number.set_value"):
                values[entity] = data["value"]
            elif action == "input_select.select_option":
                values[entity] = data["option"]
            elif action == "input_select.set_options":
                values[entity + ":options"] = data["options"]
            else:
                raise AssertionError(action)
    return True


@pytest.mark.parametrize("model,count", [("int", 4), ("iht", 3)])
def test_compatibility_selector_changes_only_view_without_touching_cooks(model, count):
    values = source_values(model, 3)
    values["input_text.inkbird_sensor_prefix"] = "sensor.old_int"
    for n in range(1, 5):
        values[f"input_boolean.bbq_probe_{n}_enabled"] = "on"
        values[f"input_number.inkbird_target_{n}"] = "85"
        values[f"input_text.inkbird_name_{n}"] = "Previous cook"
        values[f"input_text.bbq_last_alert_{n}"] = "old-session"
    calls = []
    assert run_sequence(PACKAGE["script"]["bbq_select_thermometer"]["sequence"], values, {"prefix": PREFIX}, calls)
    assert calls == [("input_text.set_value", ["input_text.inkbird_sensor_prefix"], {"value": PREFIX})]
    for n in range(1, 5):
        assert values[f"input_boolean.bbq_probe_{n}_enabled"] == "on"
        assert values[f"input_number.inkbird_target_{n}"] == "85"
        assert values[f"input_text.bbq_last_alert_{n}"] == "old-session"
        assert values[f"input_text.inkbird_name_{n}"] == "Previous cook"


@pytest.mark.parametrize("model", ("int", "iht"))
def test_selector_validates_actual_entities_not_current_readability(model):
    values = source_values(model)
    source = PREFIX + (IHT_SUFFIXES[0] if model == "iht" else "_probe_1_internal_temperature")
    guard = PACKAGE["script"]["bbq_select_thermometer"]["sequence"][0]["value_template"]
    values[source] = "unknown"
    assert truth(guard, values, prefix=PREFIX)
    values.pop(source)
    assert not truth(guard, values, prefix=PREFIX)
    for invalid in ("sensor.absent", "switch.test_inkbird", "sensor.test_inkbird\n", "", None, 42):
        assert not truth(guard, values, prefix=invalid)


@pytest.mark.parametrize("model", ("int", "iht"))
def test_selecting_current_thermometer_preserves_all_settings(model):
    values = source_values(model)
    values["input_number.inkbird_target_1"] = "76"
    values["input_text.inkbird_name_1"] = "Current cook"
    values["input_boolean.bbq_probe_1_enabled"] = "on"
    before = values.copy()
    calls = []
    assert not run_sequence(PACKAGE["script"]["bbq_select_thermometer"]["sequence"], values, {"prefix": PREFIX}, calls)
    assert values == before
    assert calls == []


def test_package_upgrade_does_not_force_helper_defaults():
    for domain in ("input_number", "input_text", "input_select", "input_boolean"):
        assert all("initial" not in settings for settings in PACKAGE[domain].values())


def test_shared_legacy_alarms_are_retired_and_only_selector_refresh_runs():
    assert "inkbird_cook_control" in PACKAGE
    for key, automation in AUTOMATIONS.items():
        if key.startswith("inkbird_bbq_") and key != "inkbird_bbq_sync_media_targets":
            assert automation["initial_state"] is False, key


@pytest.mark.parametrize(
    "profile,allowed", [("int14_bw", True), ("int14p_bw", False), ("int12_bw", False), ("unknown", True), ("unavailable", True)]
)
def test_selector_rejects_known_other_int_profiles(profile, allowed):
    values = source_values("int")
    values[PREFIX + "_configured_model_profile"] = profile
    guard = PACKAGE["script"]["bbq_select_thermometer"]["sequence"][0]["value_template"]
    assert truth(guard, values, prefix=PREFIX) is allowed


def test_direct_prefix_edits_reset_but_script_event_does_not_reset_after_fast_arm():
    auto = AUTOMATIONS["inkbird_bbq_thermometer_changed"]
    values = source_values("iht")
    values["script.bbq_select_thermometer"] = "off"
    values["script.bbq_select_thermometer:context"] = "selector-context"
    trigger = SimpleNamespace(
        id="all",
        from_state=SimpleNamespace(state="sensor.old_int"),
        to_state=SimpleNamespace(state=PREFIX, context=SimpleNamespace(id="selector-context")),
    )
    # The script has completed and the user can already have armed a new recipe.
    assert not truth(auto["conditions"][1]["value_template"], values, trigger=trigger)
    cancel = AUTOMATIONS["inkbird_bbq_cancel_pending"]
    assert not truth(cancel["conditions"][0]["value_template"], values, trigger=trigger)
    trigger.to_state.context.id = "direct-edit"
    assert all(truth(c["value_template"], values, trigger=trigger) for c in auto["conditions"])
    assert auto["actions"][0]["action"] == "script.bbq_reset_cook"
    trigger.to_state.state = "sensor.superseded_edit"
    assert not truth(auto["conditions"][2]["value_template"], values, trigger=trigger)


@pytest.mark.parametrize(
    "age,low,source,expected",
    [
        (10, "on", PREFIX, True),
        (121, "on", PREFIX, False),
        (10, "off", PREFIX, False),
        (10, "unknown", PREFIX, False),
        (10, "on", "sensor.old_int", False),
    ],
)
def test_iht_battery_uses_binary_candidate_fresh_active_external_channel(age, low, source, expected):
    values = source_values("iht", 3)
    values.update(
        {
            PREFIX + "_last_update_epoch": NOW.timestamp() - age,
            PREFIX + "_battery_raw_level": "2",
            "binary_sensor.test_inkbird_battery_low_candidate": low,
            "input_boolean.bbq_battery_alerts": "on",
            "sensor.bbq_probe_3_status": "heating",
            "sensor.bbq_probe_3_status:source_prefix": source,
        }
    )
    auto = AUTOMATIONS["inkbird_bbq_probe_battery_low"]
    assert truth(auto["triggers"][0]["value_template"], values) is expected
    for trigger in auto["triggers"][1:]:
        assert not truth(trigger["value_template"], values)
    for key in ("title", "message", "tts_message"):
        message = render(auto["actions"][1]["data"][key], values, iht=True, idx="1", pname="Probe", pct="2")
        assert "%" not in message and "percent" not in message and "level 2" not in message


@pytest.mark.parametrize("n", range(1, 5))
def test_derivative_window_and_reminder_sessions_are_isolated(n):
    values = source_values("int", n)
    control = SENSORS[f"bbq_probe_{n}_control_temperature"]
    values["input_text.inkbird_sensor_prefix:changed"] = NOW - timedelta(seconds=10)
    valid_after = float(render(control["attributes"]["rate_valid_after"], values))
    assert valid_after == NOW.timestamp() + 710
    values.update(
        {
            f"sensor.bbq_probe_{n}_control_temperature:rate_valid_after": valid_after,
            f"sensor.bbq_probe_{n}_status": "heating",
            f"sensor.bbq_probe_{n}_rate": "0.2",
            "input_boolean.bbq_stall_alerts": "on",
        }
    )
    trigger = AUTOMATIONS["inkbird_bbq_probe_stalled"]["triggers"][n - 1]
    assert not truth(trigger["value_template"], values)
    values[f"sensor.bbq_probe_{n}_control_temperature:rate_valid_after"] = NOW.timestamp() - 1
    assert truth(trigger["value_template"], values)
    session_template = AUTOMATIONS["inkbird_bbq_probe_reached_target"]["variables"]["session_key"]
    before = render(session_template, values, trigger={"id": str(n)})
    values["input_text.inkbird_sensor_prefix:changed"] = NOW
    assert render(session_template, values, trigger={"id": str(n)}) != before
    for kind in ("snooze", "rest"):
        guard = PACKAGE["script"][f"bbq_{kind}_{n}"]["sequence"][4]["value_template"]
        values[f"sensor.bbq_probe_{n}_status"] = "ready"
        values[f"sensor.bbq_probe_{n}_status:source_prefix"] = "sensor.old_int"
        assert not truth(guard, values, current_session="same", session_at_start="same")
