"""Optional Cook Control backend. Reads thermometer entities, never their drivers."""

import asyncio
import logging
import re
import time
from copy import deepcopy
from datetime import timedelta

try:
    import probatio as vol
except ImportError:
    import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .engine import Engine, announcement, number

DOMAIN = "inkbird_cook_control"
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)
LOGGER = logging.getLogger(__name__)


def state_value(hass, entity_id):
    state = hass.states.get(entity_id or "")
    return state.state if state else None


def temperature(hass, entity_id):
    state = hass.states.get(entity_id or "")
    value = number(state.state) if state else None
    if value is not None and state.attributes.get("unit_of_measurement") == "\u00b0F":
        value = (value - 32) * 5 / 9
    return value


def discover(hass):
    """Registry identities and unique-id suffixes survive entity renaming."""
    groups = {}
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    for entity in registry.entities.values():
        if entity.platform not in {"inkbird_int14", "inkbird_iht2pb"} or not entity.device_id or entity.disabled_by:
            continue
        groups.setdefault(entity.device_id, []).append(entity)
    result = []
    for device_id, entities in groups.items():
        device = devices.async_get(device_id)
        if not device:
            continue
        iht = entities[0].platform == "inkbird_iht2pb"
        if not iht and (device.model or "").upper().removeprefix("INKBIRD ").strip() not in {"INT-14-BW", "INT-14"}:
            continue

        def find(suffix, domain="sensor"):
            matches = [e.entity_id for e in entities if e.unique_id.endswith(suffix) and e.entity_id.startswith(domain + ".")]
            return matches[0] if len(matches) == 1 else None

        layout = []
        for index in range(1, 4 if iht else 5):
            entity = find(f"_probe_{index}_temp" if iht else f"_probe_{index}_internal_temp")
            if not entity:
                continue
            layout.append(
                {
                    "id": str(index),
                    "name": ["Built-in tip", "External 1", "External 2"][index - 1] if iht else f"Probe {index}",
                    "entity": entity,
                    "ambient_entity": None if iht else find(f"_probe_{index}_ambient_temp"),
                    "battery_entity": None if iht else find(f"_probe_{index}_battery"),
                }
            )
        if len(layout) != (3 if iht else 4):
            continue
        result.append(
            {
                "id": device_id,
                "name": device.name_by_user or device.name or ("IHT-2PB" if iht else "INT-14-BW"),
                "model": "iht2pb" if iht else "int14_bw",
                "layout": layout,
                "epochs": [
                    e
                    for suffix in (["_last_update_epoch_s"] if iht else ["_last_ble_update_epoch_s", "_last_lan_update_epoch_s"])
                    if (e := find(suffix))
                ],
                "battery_quality_entity": find("_battery_quality"),
                "battery_raw_entity": find("_battery_raw_level"),
                "battery_low_entity": find("_battery_low_candidate", "binary_sensor") if iht else None,
            }
        )
    # Identical device names are common when two IHT units are installed.
    for item in result:
        if sum(other["name"] == item["name"] for other in result) > 1:
            item["name"] += " / " + item["id"][-4:]
    return result


class Manager:
    def __init__(self, hass):
        self.hass = hass
        self.store = Store(hass, 1, DOMAIN)
        self.engine = Engine()
        self.lock = asyncio.Lock()
        self.readings = {}
        self.listeners = set()
        self.ready = False
        self.remove_timer = None

    def archive_store(self, sid):
        if not re.fullmatch(r"[a-f0-9]{32}", sid):
            raise ValueError("Invalid session id")
        return Store(self.hass, 1, f"{DOMAIN}.session.{sid}")

    async def save(self):
        # Persist the alert latch before dispatch: restarting must not repeat an announcement.
        try:
            for sid, history in self.engine.histories.items():
                await self.archive_store(sid).async_save(deepcopy(history))
            await self.store.async_save(deepcopy(self.engine.data))
        except Exception:
            self.ready = False
            self.publish()
            raise

    def read(self):
        result = {}
        for key, device in self.engine.data["devices"].items():
            epochs = [number(state_value(self.hass, entity)) for entity in device.get("epochs", [])]
            epoch = max((value for value in epochs if value is not None), default=None)
            result[key] = {
                channel["id"]: {
                    "temperature": temperature(self.hass, channel["entity"]),
                    "ambient": temperature(self.hass, channel["ambient_entity"]),
                    "battery": number(state_value(self.hass, channel["battery_entity"])),
                    "battery_suspect": (
                        self.hass.states.get(channel["battery_entity"]).attributes.get("report_suspect")
                        if self.hass.states.get(channel["battery_entity"] or "")
                        else None
                    ),
                    "battery_low": state_value(self.hass, device.get("battery_low_entity")) == "on",
                    "epoch": epoch,
                }
                for channel in device["layout"]
            }
        self.readings = result
        return result

    def snapshot(self):
        return self.engine.snapshot(self.readings, time.time())

    @callback
    def publish(self):
        snapshot = self.snapshot()
        self.hass.states.async_set(
            "sensor.inkbird_cook_control",
            "active" if self.ready else "starting",
            {
                "friendly_name": "Cook Control",
                "version": "1.2.0",
                "device_count": len(snapshot["devices"]),
                "active_cooks": sum(bool(d["session"]) for d in snapshot["devices"]),
            },
        )
        for listener in tuple(self.listeners):
            listener(snapshot)

    async def initialize(self, _event=None):
        async with self.lock:
            self.engine = Engine(await self.store.async_load())
            self.engine.discover(discover(self.hass))
            for device in self.engine.data["devices"].values():
                if sid := device["session"]:
                    history = await self.archive_store(sid).async_load()
                    if history is None:
                        raise ValueError("An active cooking archive is missing; restore it from backup")
                    self.engine.histories[sid] = history
            if not self.engine.data["migrated"]:
                prefix = state_value(self.hass, "input_text.inkbird_sensor_prefix") or ""
                for key, device in self.engine.data["devices"].items():
                    if not any(c["entity"].startswith(prefix + "_") for c in device["layout"]):
                        continue
                    self.engine.data["initial_device"] = key
                    for channel in device["channels"]:
                        target = number(state_value(self.hass, f"input_number.inkbird_target_{channel}")) or 0
                        name = state_value(self.hass, f"input_text.inkbird_name_{channel}")
                        armed = state_value(self.hass, f"input_boolean.bbq_probe_{channel}_enabled") == "on"
                        patch = {"target": target, "armed": armed and target > 0}
                        if name and name not in {"unknown", "unavailable"}:
                            patch["name"] = name
                        self.engine.configure(key, channel, patch, time.time())
                        if armed and state_value(self.hass, f"input_text.bbq_last_alert_{channel}") not in {
                            None,
                            "",
                            "unknown",
                            "unavailable",
                        }:
                            config = device["channels"][channel]
                            config["alerted"] = config["generation"]
                self.engine.data["migrated"] = True
            self.read()
            await self.save()
            self.ready = True
            self.publish()
        self.remove_timer = async_track_time_interval(self.hass, self.tick, timedelta(seconds=5))

    async def tick(self, _now=None):
        if not self.ready or self.lock.locked():
            return
        async with self.lock:
            self.engine.discover(discover(self.hass))
            notices, changed = self.engine.tick(
                self.read(),
                time.time(),
                {
                    "battery": state_value(self.hass, "input_boolean.bbq_battery_alerts") == "on",
                    "stall": state_value(self.hass, "input_boolean.bbq_stall_alerts") == "on",
                    "battery_threshold": number(state_value(self.hass, "input_number.bbq_battery_threshold")) or 10,
                },
            )
            if changed:
                try:
                    await self.save()
                except Exception:
                    self.ready = False
                    self.publish()
                    LOGGER.exception("Cook Control storage failed; notification dispatch paused")
                    return
            for notice in notices:
                await self.notify(notice)
            self.publish()

    async def notify(self, notice):
        italian = state_value(self.hass, "input_select.bbq_language") == "Italiano"
        title = "BBQ: promemoria" if notice["kind"] != "target" and italian else "BBQ: reminder" if notice["kind"] != "target" else "BBQ"
        device = self.engine.data["devices"][notice["device_id"]]
        message = announcement(notice, device, italian)
        tag = f"cook_{notice['session']}_{notice['channel']}"
        actions = [
            {"action": f"COOK:{notice['session']}:{notice['channel']}:{notice['generation']}:{kind}", "title": label}
            for kind, label in (("snooze", "Snooze"), ("rest", "Rest"), ("dismiss", "OK"))
        ]
        try:
            await self.hass.services.async_call(
                "script",
                "bbq_notify",
                {
                    "title": title,
                    "message": f"{device['alias']}: {message}",
                    "tts_message": message,
                    "tag": tag,
                    "actions": actions,
                },
                blocking=True,
            )
            status = "router_completed"
        except Exception as err:
            status = type(err).__name__
            LOGGER.exception("Cook Control notification router failed")
        self.engine.event(notice["device_id"], time.time(), "notification_result", channel=notice["channel"], result=status)
        await self.save()

    async def command(self, action, payload):
        async with self.lock:
            if not self.ready:
                raise ValueError("Cook Control is not ready; check the Home Assistant log")
            key = payload.get("device_id")
            now = time.time()
            if action == "snapshot":
                self.read()
                return self.snapshot()
            if action == "history":
                sid = payload.get("session_id", "")
                if sid not in self.engine.data["index"]:
                    raise ValueError("Unknown session")
                history = self.engine.histories.get(sid) or await self.archive_store(sid).async_load()
                offset = int(payload.get("offset", 0))
                if offset < 0:
                    raise ValueError("Invalid offset")
                return {
                    **history,
                    "samples": history["samples"][offset : offset + 1000],
                    "next_offset": offset + 1000 if len(history["samples"]) > offset + 1000 else None,
                }
            if key not in self.engine.data["devices"]:
                raise ValueError("Unknown thermometer")
            if action == "configure":
                channel = payload.get("channel")
                if channel not in self.engine.data["devices"][key]["channels"]:
                    raise ValueError("Unknown channel")
                self.engine.configure(key, channel, payload.get("settings", {}), now)
            elif action == "rename":
                name = payload.get("name")
                if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
                    raise ValueError("Enter a name of 1 to 100 characters")
                self.engine.data["devices"][key]["alias"] = name.strip()
                self.engine.event(key, now, "renamed", name=name.strip())
            elif action == "start":
                self.engine.start(key, now, payload.get("name", ""))
            elif action == "finish":
                sid = self.engine.finish(key, now)
                await self.save()
                self.engine.histories.pop(sid, None)
            elif action in {"snooze", "rest", "dismiss"}:
                channel = payload.get("channel")
                if channel not in self.engine.data["devices"][key]["channels"]:
                    raise ValueError("Unknown channel")
                if "expected_generation" in payload and (
                    self.engine.data["devices"][key]["session"] != payload.get("expected_session")
                    or self.engine.data["devices"][key]["channels"][channel]["generation"] != payload["expected_generation"]
                ):
                    raise ValueError("That notification belongs to an older cook")
                minutes = number(state_value(self.hass, f"input_number.bbq_{action}_minutes")) or 5
                self.engine.reminder(key, channel, action, minutes, now)
            else:
                raise ValueError("Unknown action")
            await self.save()
            self.read()
            self.publish()
            return self.snapshot()

    async def mobile_action(self, event):
        match = re.fullmatch(r"COOK:([a-f0-9]{32}):([1-4]):(\d+):(snooze|rest|dismiss)", event.data.get("action", ""))
        if not match:
            return
        sid, channel, generation, action = match.groups()
        # Old mobile buttons cannot affect a later cook or a changed target.
        for key, device in self.engine.data["devices"].items():
            if device["session"] == sid and channel in device["channels"] and device["channels"][channel]["generation"] == int(generation):
                await self.command(
                    action, {"device_id": key, "channel": channel, "expected_session": sid, "expected_generation": int(generation)}
                )
                break


@websocket_api.websocket_command(
    {"type": "inkbird_cook_control/command", vol.Required("action"): str, vol.Optional("payload", default={}): dict}
)
@websocket_api.require_admin
@websocket_api.async_response
async def command(hass, connection, msg):
    try:
        result = await hass.data[DOMAIN].command(msg["action"], msg["payload"])
        connection.send_result(msg["id"], result)
    except (ValueError, KeyError, TypeError) as err:
        connection.send_error(msg["id"], "invalid_request", str(err))


@websocket_api.websocket_command({"type": "inkbird_cook_control/subscribe"})
@websocket_api.require_admin
@callback
def subscribe(hass, connection, msg):
    manager = hass.data[DOMAIN]

    @callback
    def send(snapshot):
        connection.send_event(msg["id"], snapshot)

    manager.listeners.add(send)
    connection.subscriptions[msg["id"]] = lambda: manager.listeners.discard(send)
    connection.send_result(msg["id"])
    send(manager.snapshot())


async def async_setup(hass, _config):
    manager = hass.data[DOMAIN] = Manager(hass)
    websocket_api.async_register_command(hass, command)
    websocket_api.async_register_command(hass, subscribe)
    hass.bus.async_listen("mobile_app_notification_action", manager.mobile_action)
    if hass.is_running:
        await manager.initialize()
    else:
        hass.bus.async_listen_once("homeassistant_started", manager.initialize)
    return True
