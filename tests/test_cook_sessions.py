"""Concurrent device, durable session and notification-name regression tests."""

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "cook_engine", ROOT / "examples/cook_control/custom_components/inkbird_cook_control/engine.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
Engine = MODULE.Engine


def device(key, model="iht2pb"):
    return {
        "id": key,
        "model": model,
        "name": model,
        "epochs": [],
        "layout": [
            {"id": str(n), "name": f"Probe {n}", "entity": f"sensor.test_{key}_{n}", "ambient_entity": None, "battery_entity": None}
            for n in range(1, 5 if model == "int14_bw" else 4)
        ],
    }


@pytest.fixture
def engine():
    result = Engine()
    result.discover([device("station", "int14_bw"), device("handheld_a"), device("handheld_b")])
    return result


def readings(now, value=85):
    return {
        key: {
            str(n): {"epoch": now, "temperature": value, "ambient": 110 if key == "station" else None}
            for n in range(1, 5 if key == "station" else 4)
        }
        for key in ("station", "handheld_a", "handheld_b")
    }


def arm(engine, key="station", channel="1", target=80, now=1000):
    engine.configure(key, channel, {"target": target, "armed": True}, now)


def test_three_cooks_alert_independently_and_have_distinct_tags(engine):
    for key in engine.data["devices"]:
        arm(engine, key)
    assert len(engine.tick(readings(1000), 1000)[0]) == 0
    notices = engine.tick(readings(1030), 1030)[0]
    assert len(notices) == 3
    assert len({n["session"] for n in notices}) == 3
    assert len({d["alias"] for d in engine.data["devices"].values()}) == 3
    assert not engine.tick(readings(1100), 1100)[0]


def test_changing_one_target_cannot_disarm_or_restart_other_cooks(engine):
    arm(engine, "station")
    arm(engine, "handheld_a")
    before = deepcopy(engine.data["devices"]["station"])
    engine.configure("handheld_a", "1", {"target": 90, "name": "Chicken"}, 1001)
    assert engine.data["devices"]["station"] == before
    assert engine.data["devices"]["handheld_a"]["channels"]["1"]["armed"]


def test_snapshot_and_view_selection_are_not_mutations(engine):
    arm(engine)
    before = deepcopy(engine.data)
    for _ in range(30):
        snapshot = engine.snapshot(readings(1000), 1000)
        for index in (0, 2, 1):
            assert snapshot["devices"][index]["id"]
    assert engine.data == before
    assert "selected" not in engine.data


@pytest.mark.parametrize("value", [None, "unknown", "unavailable", "nan", float("nan"), float("inf")])
def test_invalid_temperature_never_alerts(engine, value):
    arm(engine)
    for now in (1000, 1030, 1060):
        assert not engine.tick(readings(now, value), now)[0]


@pytest.mark.parametrize("age", [121, 10000, -61])
def test_stale_or_future_packets_do_not_trigger(engine, age):
    arm(engine)
    assert not engine.tick(readings(1000 - age), 1000)[0]
    assert not engine.tick(readings(1030 - age), 1030)[0]


def test_ready_needs_30_continuous_fresh_seconds(engine):
    arm(engine)
    engine.tick(readings(1000), 1000)
    assert not engine.tick(readings(1029), 1029)[0]
    assert not engine.tick(readings(1030, None), 1030)[0]
    assert not engine.tick(readings(1031), 1031)[0]
    assert len(engine.tick(readings(1061), 1061)[0]) == 1


def test_persisted_latch_survives_restart_and_does_not_repeat(engine):
    arm(engine)
    engine.tick(readings(1000), 1000)
    engine.tick(readings(1030), 1030)
    restored = Engine(json.loads(json.dumps(engine.data)))
    restored.histories = json.loads(json.dumps(engine.histories))
    assert not restored.tick(readings(1040), 1040)[0]
    assert not restored.tick(readings(1100), 1100)[0]


def test_pending_wait_is_not_restored_as_verified_time(engine):
    arm(engine)
    engine.tick(readings(1000), 1000)
    restored = Engine(engine.data)
    restored.histories = deepcopy(engine.histories)
    assert not restored.tick(readings(1020), 1020)[0]
    assert not restored.tick(readings(1049), 1049)[0]
    assert len(restored.tick(readings(1050), 1050)[0]) == 1


def test_finish_archives_only_its_device_and_preserves_targets(engine):
    arm(engine)
    arm(engine, "handheld_a")
    sid = engine.data["devices"]["station"]["session"]
    engine.tick(readings(1000), 1000)
    engine.tick(readings(1030), 1030)
    engine.finish("station", 1040)
    assert engine.data["index"][sid]["ended"] == 1040
    assert engine.histories[sid]["summary"]["ended"] == 1040
    assert engine.data["devices"]["station"]["channels"]["1"]["target"] == 80
    assert not engine.data["devices"]["station"]["channels"]["1"]["armed"]
    assert engine.data["devices"]["handheld_a"]["channels"]["1"]["armed"]


def test_history_records_real_gaps_not_zeroes_and_retains_all_channels(engine):
    for key in engine.data["devices"]:
        arm(engine, key)
    engine.tick(readings(1000), 1000)
    engine.tick(readings(1030, None), 1030)
    for key, item in engine.data["devices"].items():
        history = engine.histories[item["session"]]
        assert len(history["samples"]) == 2
        assert len(history["samples"][0]["channels"]) == (4 if key == "station" else 3)
        assert history["samples"][1]["channels"]["1"]["temperature"] is None


def test_snooze_survives_restart_and_edit_cancels_only_local_reminder(engine):
    for key in ("station", "handheld_a"):
        arm(engine, key)
    engine.tick(readings(1000), 1000)
    engine.tick(readings(1030), 1030)
    for key in ("station", "handheld_a"):
        engine.reminder(key, "1", "snooze", 1, 1031)
    restored = Engine(engine.data)
    restored.histories = deepcopy(engine.histories)
    restored.configure("handheld_a", "1", {"name": "Different food"}, 1040)
    notices = restored.tick(readings(1091), 1091)[0]
    assert len(notices) == 1 and notices[0]["device_id"] == "station" and notices[0]["kind"] == "snooze"


@pytest.mark.parametrize(
    "patch", [{"target": -1}, {"target": "nan"}, {"target": 351}, {"armed": "yes"}, {"name": ""}, {"anything": 5}, {"armed": True}]
)
def test_invalid_settings_do_not_mutate(engine, patch):
    before = deepcopy(engine.data)
    with pytest.raises(ValueError):
        engine.configure("station", "1", patch, 1000)
    assert engine.data == before


def test_discovery_renames_do_not_reset_alias_or_channel_settings(engine):
    arm(engine)
    engine.data["devices"]["station"]["alias"] = "Smoker"
    descriptor = device("station", "int14_bw")
    descriptor["name"] = "Registry name changed"
    engine.discover([descriptor])
    assert engine.data["devices"]["station"]["alias"] == "Smoker"
    assert engine.data["devices"]["station"]["channels"]["1"]["armed"]


def test_speech_uses_food_name_not_model_code(engine):
    arm(engine)
    engine.configure("station", "1", {"name": "Musetto"}, 1000)
    engine.tick(readings(1000), 1000)
    notice = engine.tick(readings(1030), 1030)[0][0]
    spoken = MODULE.announcement(notice, engine.data["devices"]["station"], True)
    assert spoken == "Musetto ha raggiunto 85 gradi."
    assert not any(code in spoken for code in ("int14", "INT-14", "PROBE", "sensor."))


def test_generic_probe_speech_includes_friendly_device_name(engine):
    arm(engine, "handheld_b", "3")
    engine.tick(readings(1000), 1000)
    notice = engine.tick(readings(1030), 1030)[0][0]
    spoken = MODULE.announcement(notice, engine.data["devices"]["handheld_b"], True)
    assert "Sonda esterna 2" in spoken
    assert "Termometro portatile 2" in spoken


@pytest.mark.parametrize("suspect,expected", [(False, 1), (True, 0), (None, 0)])
def test_battery_warning_uses_trustworthy_percentages_only(engine, suspect, expected):
    arm(engine)
    data = readings(1000, 50)
    data["station"]["1"].update(battery=4, battery_suspect=suspect)
    notices = engine.tick(data, 1000, {"battery": True, "battery_threshold": 10})[0]
    assert len(notices) == expected
    assert not engine.tick(data, 1001, {"battery": True})[0]


def test_iht_low_battery_flag_not_raw_level(engine):
    arm(engine, "handheld_a")
    data = readings(1000, 50)
    data["handheld_a"]["1"].update(battery=None, battery_low=True)
    assert engine.tick(data, 1000, {"battery": True})[0][0]["kind"] == "battery"


def test_stall_waits_for_history_and_45_continuous_minutes(engine):
    arm(engine)
    notices = []
    for now in range(1000, 1000 + 3600, 30):
        notices.extend(engine.tick(readings(now, 60), now, {"stall": True})[0])
    assert len(notices) == 1 and notices[0]["kind"] == "stall"
