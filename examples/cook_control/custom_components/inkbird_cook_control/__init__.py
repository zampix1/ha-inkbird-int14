"""Optional Cook Control backend. Reads thermometer entities, never their drivers."""

import asyncio
import logging
import re
import time
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

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

from .delivery import plan, send
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
                    "target_entity": find(f"_probe_{index}_target_high_temp"),
                    "control_entities": [
                        entity
                        for suffix in (
                            f"_probe_{index}_target_high_command",
                            f"_probe_{index}_advance_command",
                            f"_probe_{index}_calibration_command",
                        )
                        if (entity := find(suffix, "number"))
                    ],
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
                "inspection": [
                    entity
                    for suffix, domain in (
                        ("_base_battery", "sensor"),
                        ("_base_temp", "sensor"),
                        ("_active_transport", "sensor"),
                        ("_ble_connected", "binary_sensor"),
                        ("_wi_fi_connected", "binary_sensor"),
                        ("_sound_enabled", "binary_sensor"),
                        ("_muted", "binary_sensor"),
                        ("_temperature_unit", "sensor"),
                        ("_transport_mode", "select"),
                        ("_display_light_command", "number"),
                        ("_request_snapshot", "button"),
                        ("_battery_raw_level", "sensor"),
                        ("_battery_low_candidate", "binary_sensor"),
                    )
                    if (entity := find(suffix, domain))
                ],
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
        self.delivery_tasks = {}
        self.archive_versions = {}

    def archive_store(self, sid, part=""):
        if not re.fullmatch(r"[a-f0-9]{32}", sid):
            raise ValueError("Invalid session id")
        if part and not re.fullmatch(r"(?:samples|events)\.\d+", part):
            raise ValueError("Invalid archive part")
        return Store(self.hass, 1, f"{DOMAIN}.session.{sid}" + ("." + part if part else ""))

    async def load_archive(self, sid):
        meta = await self.archive_store(sid).async_load()
        if not meta or meta.get("format") != 2:
            return meta
        result = {"summary": meta["summary"], "samples": [], "events": []}
        for field, size in (("samples", 120), ("events", 100)):
            count = meta[field]
            for index in range((count + size - 1) // size):
                rows = await self.archive_store(sid, f"{field}.{index}").async_load()
                if rows is None:
                    raise ValueError("Cooking archive part missing; restore backup")
                result[field].extend(rows[: min(size, count - index * size)])
        return result

    async def save(self):
        # Persist the alert latch before dispatch: restarting must not repeat an announcement.
        try:
            for sid, history in self.engine.histories.items():
                version = (len(history["samples"]), len(history["events"]), history["summary"])
                previous = self.archive_versions.get(sid)
                if previous == version:
                    continue
                for field, size, position in (("samples", 120, 0), ("events", 100, 1)):
                    rows = history[field]
                    old_count = previous[position] if previous else 0
                    for index in range(old_count // size, (len(rows) + size - 1) // size):
                        await self.archive_store(sid, f"{field}.{index}").async_save(deepcopy(rows[index * size : (index + 1) * size]))
                await self.archive_store(sid).async_save(
                    {
                        "format": 2,
                        "summary": deepcopy(history["summary"]),
                        "samples": len(history["samples"]),
                        "events": len(history["events"]),
                    }
                )
                self.archive_versions[sid] = deepcopy(version)
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
                    "device_target": temperature(self.hass, channel.get("target_entity")),
                    "battery_raw": number(state_value(self.hass, device.get("battery_raw_entity"))),
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
                "version": "1.2.1",
                "device_count": len(snapshot["devices"]),
                "active_cooks": sum(bool(d["session"]) for d in snapshot["devices"]),
            },
        )
        for listener in tuple(self.listeners):
            listener(snapshot)

    async def initialize(self, _event=None):
        async with self.lock:
            self.engine = Engine(await self.store.async_load())
            self.engine.expire_deliveries(time.time())
            self.engine.discover(discover(self.hass))
            for device in self.engine.data["devices"].values():
                if sid := device["session"]:
                    history = await self.load_archive(sid)
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
            if not self.engine.data.get("preset_migrated"):
                self.engine.data["preset"] = {
                    "name": state_value(self.hass, "input_text.bbq_custom_name") or "Custom",
                    "target": number(state_value(self.hass, "input_number.bbq_custom_target")) or 60,
                }
                self.engine.data["preset_migrated"] = True
            self.read()
            await self.save()
            self.ready = True
            self.publish()
        self.remove_timer = async_track_time_interval(self.hass, self.tick, timedelta(seconds=5))
        self.pump()

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
                    "rest_minutes": number(state_value(self.hass, "input_number.bbq_rest_minutes")) or 0,
                },
            )
            for notice in notices:
                self.enqueue(notice)
            changed = self.engine.expire_deliveries(time.time()) or changed
            if changed or notices:
                try:
                    await self.save()
                except Exception:
                    self.ready = False
                    self.publish()
                    LOGGER.exception("Cook Control storage failed; notification dispatch paused")
                    return
            self.publish()
        self.pump()

    def enqueue(self, notice):
        italian = state_value(self.hass, "input_select.bbq_language") == "Italiano"
        device = self.engine.data["devices"][notice["device_id"]]
        duplicates = [
            (d, key)
            for d in self.engine.data["devices"].values()
            if d["session"]
            for key, config in d["channels"].items()
            if config["armed"] and config["name"].casefold() == notice["name"].casefold()
        ]
        notice["disambiguate"] = len(duplicates) > 1
        message = announcement(notice, device, italian)
        alexa = {entity.entity_id for entity in er.async_get(self.hass).entities.values() if entity.platform == "alexa_media"}
        return self.engine.enqueue(notice, plan(self.hass, notice, device, message, alexa), time.time())

    def pump(self):
        destinations = {
            output.get("guard") or f"{output.get('domain')}.{output.get('service')}"
            for event in self.engine.data["outbox"].values()
            for output in event["outputs"].values()
            if output["state"] in {"queued", "error"}
            and output.get("retryable")
            and output["attempts"] < 3
            and output.get("next_at", 0) <= time.time()
        }
        for destination in destinations:
            task = self.delivery_tasks.get(destination)
            if task is None or task.done():
                self.delivery_tasks[destination] = asyncio.create_task(self.deliver(destination))

    async def deliver(self, destination):
        while self.ready:
            async with self.lock:
                job = next(
                    (
                        (event, key, output)
                        for event in self.engine.data["outbox"].values()
                        for key, output in event["outputs"].items()
                        if (output.get("guard") or f"{output.get('domain')}.{output.get('service')}") == destination
                        and output["state"] in {"queued", "error"}
                        and output.get("retryable")
                        and output["attempts"] < 3
                        and output.get("next_at", 0) <= time.time()
                    ),
                    None,
                )
                if job is None:
                    return
                event, key, output = job
                output.update(state="sending", attempts=output["attempts"] + 1)
                await self.save()
                self.publish()
                request = deepcopy(output)
            try:
                state = await asyncio.wait_for(send(self.hass, request), timeout=10)
                error = None
            except TimeoutError:
                state, error = "unknown", "Timeout: check before retrying"
            except Exception as err:
                state, error = "error", type(err).__name__
            async with self.lock:
                output.update(state=state, error=error, next_at=time.time() + 15 * 2 ** (output["attempts"] - 1))
                if event["kind"] != "test":
                    self.engine.event(
                        event["device_id"],
                        time.time(),
                        "notification_result",
                        channel=event["channel"],
                        output=key,
                        result=state,
                        error=error,
                    )
                await self.save()
                self.publish()
            if request.get("guard") and state == "accepted":
                await asyncio.sleep(min(20, max(6, len(request["data"].get("message", "")) / 14)))

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
                history = self.engine.histories.get(sid) or await self.load_archive(sid)
                offset = int(payload.get("offset", 0))
                if offset < 0:
                    raise ValueError("Invalid offset")
                total = min(len(history["samples"]), int(payload.get("limit", len(history["samples"]))))
                if total < 0:
                    raise ValueError("Invalid history limit")
                return {
                    "summary": deepcopy(history["summary"]),
                    "events": deepcopy(history["events"]),
                    "samples": deepcopy(history["samples"][offset : min(total, offset + 1000)]),
                    "total_samples": total,
                    "next_offset": offset + 1000 if total > offset + 1000 else None,
                }
            if action == "preset":
                name, target = payload.get("name"), number(payload.get("target"))
                if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100 or target is None or not 0 < target <= 350:
                    raise ValueError("Enter a preset name and a temperature between 0 and 350 C")
                self.engine.data["preset"] = {"name": name.strip(), "target": target}
                await self.save()
                self.publish()
                return self.snapshot()
            if action == "retry":
                event = self.engine.data["outbox"].get(payload.get("notice_id"))
                if not event:
                    raise ValueError("Unknown notification")
                selected = {
                    key
                    for key, output in event["outputs"].items()
                    if output["state"] in {"error", "unknown"} and (payload.get("output_id") is None or payload["output_id"] == key)
                }
                self.engine.retry(payload.get("notice_id"), payload.get("output_id"))
                event["created"] = now
                device = self.engine.data["devices"][event["device_id"]]
                italian = state_value(self.hass, "input_select.bbq_language") == "Italiano"
                message = ("TEST Cook Control: " + device["alias"]) if event["kind"] == "test" else announcement(event, device, italian)
                alexa = {e.entity_id for e in er.async_get(self.hass).entities.values() if e.platform == "alexa_media"}
                fresh_outputs = plan(self.hass, event, device, message, alexa)
                for key in selected:
                    if key in fresh_outputs:
                        event["outputs"][key] = fresh_outputs[key]
                    elif key == "voice":
                        del event["outputs"][key]
                        for name, output in fresh_outputs.items():
                            if name.startswith("echo:") and event["outputs"].get(name, {}).get("state") != "accepted":
                                event["outputs"][name] = output
                    else:
                        event["outputs"][key].update(state="cancelled", error="Destination configuration changed")
                await self.save()
                self.publish()
                self.pump()
                return self.snapshot()
            if key not in self.engine.data["devices"]:
                raise ValueError("Unknown thermometer")
            if action == "test":
                device = self.engine.data["devices"][key]
                notice = {
                    "device_id": key,
                    "device_name": device["alias"],
                    "channel": device["layout"][0]["id"],
                    "session": uuid4().hex,
                    "generation": 0,
                    "kind": "test",
                    "name": "TEST",
                    "temperature": None,
                }
                message = (
                    "TEST Cook Control, nessuna cottura: "
                    if state_value(self.hass, "input_select.bbq_language") == "Italiano"
                    else "Cook Control TEST, no cook: "
                ) + device["alias"]
                alexa = {e.entity_id for e in er.async_get(self.hass).entities.values() if e.platform == "alexa_media"}
                self.engine.enqueue(notice, plan(self.hass, notice, device, message, alexa), now)
            elif action == "configure":
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
                minutes = number(state_value(self.hass, f"input_number.bbq_{action}_minutes"))
                minutes = 5 if minutes is None else minutes
                self.engine.reminder(key, channel, action, minutes, now)
            else:
                raise ValueError("Unknown action")
            await self.save()
            self.read()
            self.publish()
            self.pump()
            return self.snapshot()

    async def shutdown(self, _event=None):
        self.ready = False
        if self.remove_timer:
            self.remove_timer()
        tasks = list(self.delivery_tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        async with self.lock:
            await self.save()

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
    hass.bus.async_listen_once("homeassistant_stop", manager.shutdown)

    async def service_handler(call):
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None or not user.is_admin:
                raise ValueError("Cook Control requires administrator access")
        await manager.command(call.service, dict(call.data))

    for action in ("configure", "start", "finish", "rename", "rest", "snooze", "dismiss", "retry", "test"):
        hass.services.async_register(DOMAIN, action, service_handler)
    if hass.is_running:
        await manager.initialize()
    else:
        hass.bus.async_listen_once("homeassistant_started", manager.initialize)
    return True
