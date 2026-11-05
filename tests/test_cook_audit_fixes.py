"""Regression cases from the Cook Control audit, without real HA services."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_cook_backend import DELIVERY, MemoryStore, boundary
from test_cook_sessions import Engine, arm, device, readings


def manager_fixture():
    MemoryStore.files = {}
    hass, ns = boundary()
    manager = ns["Manager"](hass)
    manager.engine.discover([device("station", "int14_bw"), device("handheld_a"), device("handheld_b")])
    manager.ready = True
    arm(manager.engine)
    manager.engine.tick(readings(1000), 1000)
    notice = manager.engine.tick(readings(1030), 1030)[0][0]
    identifier = manager.enqueue(notice)
    return hass, ns, manager, identifier


def test_failed_output_is_visible_and_retries_but_snapshot_is_not_locked():
    async def scenario():
        hass, ns, manager, identifier = manager_fixture()
        entered, release = asyncio.Event(), asyncio.Event()

        async def delayed(*_args, **_kwargs):
            entered.set()
            await release.wait()
            raise ConnectionError("fixture")

        hass.services.async_call.side_effect = delayed
        task = asyncio.create_task(manager.deliver("persistent_notification.create"))
        await entered.wait()
        snapshot = await asyncio.wait_for(manager.command("snapshot", {}), 0.2)
        assert len(snapshot["devices"]) == 3
        assert not manager.lock.locked()
        release.set()
        await task
        output = manager.engine.data["outbox"][identifier]["outputs"]["ha"]
        assert output["state"] == "error" and output["attempts"] == 1
        assert output["next_at"] > ns["time"].time()
        assert manager.snapshot()["devices"][0]["channels"]["1"]["status"] != "notified"
        manager.engine.retry(identifier, "ha")
        hass.services.async_call.side_effect = None
        await manager.deliver("persistent_notification.create")
        assert output["state"] == "accepted"

    asyncio.run(scenario())


def test_interrupted_send_is_unknown_not_automatically_replayed():
    _, _, manager, identifier = manager_fixture()
    manager.engine.data["outbox"][identifier]["outputs"]["ha"]["state"] = "sending"
    restored = Engine(manager.engine.data)
    assert restored.data["outbox"][identifier]["outputs"]["ha"]["state"] == "unknown"


def test_timeout_is_unknown_and_has_no_automatic_retry():
    async def scenario():
        _, ns, manager, identifier = manager_fixture()

        async def blocked(*_):
            await asyncio.Event().wait()

        async def short_wait(awaitable, timeout):
            return await asyncio.wait_for(awaitable, 0.01)

        ns["send"] = blocked
        ns["asyncio"] = SimpleNamespace(wait_for=short_wait, sleep=asyncio.sleep)
        await manager.deliver("persistent_notification.create")
        output = manager.engine.data["outbox"][identifier]["outputs"]["ha"]
        assert output["state"] == "unknown" and output["attempts"] == 1
        await manager.deliver("persistent_notification.create")
        assert output["attempts"] == 1

    asyncio.run(scenario())


def test_old_pending_notice_needs_manual_confirmation_after_restart():
    _, _, manager, identifier = manager_fixture()
    event = manager.engine.data["outbox"][identifier]
    assert manager.engine.expire_deliveries(event["created"] + 301)
    assert event["outputs"]["ha"]["state"] == "unknown"


def test_test_outputs_does_not_arm_rename_start_or_change_any_cook():
    async def scenario():
        _, _, manager, _ = manager_fixture()
        manager.pump = lambda: None
        before = deepcopy(manager.engine.data["devices"])
        history = deepcopy(manager.engine.data["index"])
        for key in before:
            await manager.command("test", {"device_id": key})
        assert manager.engine.data["devices"] == before
        assert manager.engine.data["index"] == history
        assert len(manager.snapshot()["tests"]) == 3

    asyncio.run(scenario())


def test_legacy_commands_fail_before_any_helper_write_with_backend_active():
    from test_cook_control import PACKAGE
    from test_cook_thermometer_selection import run_sequence

    for name in ("bbq_reset_cook", "inkbird_apply_recipe", "inkbird_apply_custom_recipe"):
        values = {"sensor.inkbird_cook_control": "active", "input_number.inkbird_target_1": "75"}
        calls = []
        with pytest.raises(ValueError):
            run_sequence(PACKAGE["script"][name]["sequence"], values, {}, calls)
        assert not calls and values["input_number.inkbird_target_1"] == "75"


def test_output_routing_is_per_echo_and_tv_without_volume_or_power_calls():
    states = {
        "input_boolean.bbq_tts_alerts": ("on", {}),
        "input_boolean.bbq_tv_alerts": ("on", {}),
        "input_select.bbq_tts_engine": ("Alexa (native)", {}),
        "input_select.bbq_tts_speaker": ("Day", {}),
        "input_text.bbq_alexa_group_name": ("Day", {}),
        "input_text.bbq_alexa_group_targets": ("media_player.echo_a,media_player.echo_b", {}),
        "input_text.bbq_tv_notify_service": ("tv_fixture", {}),
        "input_text.bbq_tv_entity": ("media_player.tv", {}),
        "media_player.echo_a": ("idle", {"friendly_name": "Echo A"}),
        "media_player.echo_b": ("idle", {"friendly_name": "Echo B"}),
        "media_player.tv": ("off", {}),
    }
    hass, _ = boundary(states)
    notice = {"session": "test", "channel": "1", "kind": "target", "generation": 2}
    plan = DELIVERY.plan(hass, notice, {"alias": "Station"}, "Test", {"media_player.echo_a", "media_player.echo_b"})
    assert len([key for key in plan if key.startswith("echo:")]) == 2
    assert asyncio.run(DELIVERY.send(hass, plan["tv"])) == "skipped"
    for key in ("echo:media_player.echo_a", "echo:media_player.echo_b"):
        assert asyncio.run(DELIVERY.send(hass, plan[key])) == "accepted"
    assert [call.args[:2] for call in hass.services.async_call.call_args_list] == [("notify", "alexa_media")] * 2
    assert all("volume" not in str(call) for call in hass.services.async_call.call_args_list)


def test_rest_auto_is_local_survives_missing_probe_and_zero_disables():
    _, _, manager, _ = manager_fixture()
    engine = Engine()
    engine.discover([device("station", "int14_bw"), device("handheld_a")])
    arm(engine)
    arm(engine, "handheld_a")
    engine.configure("handheld_a", "1", {"rest_minutes": 0}, 1000)
    engine.tick(readings(1000), 1000, {"rest_minutes": 5})
    engine.tick(readings(1030), 1030, {"rest_minutes": 5})
    assert engine.data["devices"]["station"]["channels"]["1"]["rest"] == 1330
    assert engine.data["devices"]["handheld_a"]["channels"]["1"]["rest"] is None
    notices = engine.tick(readings(1330, None), 1330)[0]
    assert [(n["device_id"], n["kind"]) for n in notices] == [("station", "rest")]


def test_stall_config_is_per_channel_and_duration_includes_observation():
    engine = Engine()
    engine.discover([device("station", "int14_bw"), device("handheld_a")])
    arm(engine)
    arm(engine, "handheld_a")
    before = deepcopy(engine.data["devices"]["handheld_a"])
    engine.configure("station", "1", {"stall": {"enabled": True, "minutes": 5}}, 1000)
    assert engine.data["devices"]["handheld_a"] == before
    notices = []
    for now in range(1000, 1301, 30):
        notices.extend(engine.tick(readings(now, 60), now, {"stall": False})[0])
    assert [(n["device_id"], n["kind"]) for n in notices] == [("station", "stall")]


def test_iht_common_battery_only_warns_once():
    engine = Engine()
    engine.discover([device("handheld_a")])
    for channel in ("1", "2", "3"):
        arm(engine, "handheld_a", channel)
    data = readings(1000, 60)
    for row in data["handheld_a"].values():
        row["battery_low"] = True
    assert len(engine.tick(data, 1000, {"battery": True})[0]) == 1


def test_segmented_archives_roundtrip_and_closed_history_stays_readable():
    async def scenario():
        _, _, manager, _ = manager_fixture()
        sid = manager.engine.data["devices"]["station"]["session"]
        for now in range(1060, 1060 + 4000, 30):
            manager.engine.tick(readings(now, 60), now)
        await manager.save()
        restored = await manager.load_archive(sid)
        assert restored == manager.engine.histories[sid]
        assert MemoryStore.files[f"inkbird_cook_control.session.{sid}"]["format"] == 2
        assert len(MemoryStore.files[f"inkbird_cook_control.session.{sid}.samples.0"]) == 120

    asyncio.run(scenario())


@pytest.mark.parametrize("patch", [{"stall": {"minutes": 0}}, {"rest_minutes": -1}, {"rest_auto": "yes"}])
def test_new_settings_validate_without_mutating_targets(patch):
    _, _, manager, _ = manager_fixture()
    before = deepcopy(manager.engine.data)
    with pytest.raises(ValueError):
        manager.engine.configure("station", "1", patch, 1040)
    assert manager.engine.data == before
