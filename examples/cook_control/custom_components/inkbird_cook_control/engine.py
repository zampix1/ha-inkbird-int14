"""Independent cooks and restart-safe alert latches. No Home Assistant imports."""

import math
from copy import deepcopy
from uuid import uuid4

FRESH_SECONDS = 120
READY_SECONDS = 30
SAMPLE_SECONDS = 30


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def fresh(reading, now):
    epoch = number(reading.get("epoch"))
    return epoch is not None and -60 <= now - epoch <= FRESH_SECONDS and number(reading.get("temperature")) is not None


class Engine:
    """All mutations are serialized by the HA adapter; timestamps are UTC epochs."""

    def __init__(self, data=None):
        self.data = deepcopy(data) if data else {"devices": {}, "index": {}, "migrated": False}
        self.histories = {}
        self.pending = {}
        self.live_history = {}
        self.stall_tracking = {}
        self.options = {}
        self.data.setdefault("outbox", {})
        self.data.setdefault("preset", {"name": "Custom", "target": 60})
        for event in self.data["outbox"].values():
            for output in event["outputs"].values():
                if output["state"] == "sending":
                    output.update(state="unknown", error="Interrupted during delivery; retry manually")

    def discover(self, descriptors):
        for descriptor in descriptors:
            key = descriptor["id"]
            device = self.data["devices"].setdefault(key, {"channels": {}, "session": None})
            device.update(deepcopy(descriptor))
            if "alias" not in device:
                handhelds = sum(d.get("model") == "iht2pb" for d in self.data["devices"].values())
                device["alias"] = "Station BBQ" if device["model"] == "int14_bw" else f"Termometro portatile {handhelds}"
            for channel in descriptor["layout"]:
                device["channels"].setdefault(
                    channel["id"],
                    {
                        "name": channel["name"],
                        "target": 0,
                        "armed": False,
                        "generation": 0,
                        "alerted": None,
                        "snooze": None,
                        "rest": None,
                    },
                )
                config = device["channels"][channel["id"]]
                config.setdefault("rest_auto", True)
                config.setdefault("rest_minutes", None)
                config.setdefault("stall", {"enabled": None, "minutes": 45, "rate": 1, "min_temp": 40})

    def start(self, key, now, name=""):
        device = self.data["devices"][key]
        if device["session"]:
            return device["session"]
        sid = uuid4().hex
        row = {
            "id": sid,
            "device_id": key,
            "device_name": device["alias"],
            "model": device["model"],
            "name": str(name).strip()[:100] or device["alias"],
            "started": now,
            "ended": None,
            "layout": [{**deepcopy(channel), "name": device["channels"][channel["id"]]["name"]} for channel in device["layout"]],
            "sample_count": 0,
        }
        self.data["index"][sid] = row
        self.histories[sid] = {"summary": deepcopy(row), "samples": [], "events": []}
        device["session"] = sid
        # A new cook is a new alert generation, without changing targets or names.
        for config in device["channels"].values():
            config.update(generation=config["generation"] + 1, alerted=None, snooze=None, rest=None)
        return sid

    def event(self, key, now, kind, **details):
        sid = self.data["devices"][key]["session"]
        if sid and sid in self.histories:
            self.histories[sid]["events"].append({"at": now, "kind": kind, **details})

    def configure(self, key, channel, patch, now):
        device = self.data["devices"][key]
        config = device["channels"][channel]
        if set(patch) - {"name", "target", "armed", "rest_auto", "rest_minutes", "stall"}:
            raise ValueError("Unknown channel setting")
        updated = dict(patch)
        if "target" in patch:
            value = number(patch["target"])
            if value is None or not 0 <= value <= 350:
                raise ValueError("Target must be between 0 and 350 C")
            updated["target"] = value
        if "name" in patch:
            if not isinstance(patch["name"], str) or not patch["name"].strip() or len(patch["name"]) > 100:
                raise ValueError("Enter a name of 1 to 100 characters")
            updated["name"] = patch["name"].strip()
        if "armed" in patch and not isinstance(patch["armed"], bool):
            raise ValueError("Armed must be a boolean")
        if "rest_auto" in patch and not isinstance(patch["rest_auto"], bool):
            raise ValueError("Automatic rest must be a boolean")
        if "rest_minutes" in patch and patch["rest_minutes"] is not None:
            minutes = number(patch["rest_minutes"])
            if minutes is None or not 0 <= minutes <= 1440:
                raise ValueError("Rest duration must be between 0 and 1440 minutes")
            updated["rest_minutes"] = minutes
        if "stall" in patch:
            rule = patch["stall"]
            if not isinstance(rule, dict) or set(rule) - {"enabled", "minutes", "rate", "min_temp"}:
                raise ValueError("Invalid stall rule")
            rule = {**config["stall"], **rule}
            if rule["enabled"] is not None and not isinstance(rule["enabled"], bool):
                raise ValueError("Stall enabled must be true, false or null")
            for field, low, high in (("minutes", 5, 180), ("rate", 0.1, 10), ("min_temp", 0, 150)):
                value = number(rule[field])
                if value is None or not low <= value <= high:
                    raise ValueError(f"Invalid stall {field}")
                rule[field] = value
            updated["stall"] = rule
        if updated.get("armed", config["armed"]) and updated.get("target", config["target"]) <= 0:
            raise ValueError("Set a target before enabling an alert")
        if all(config.get(k) == v for k, v in updated.items()):
            return
        if updated.get("armed") and not device["session"]:
            self.start(key, now)
        config.update(updated)
        if set(updated) & {"name", "target", "armed"}:
            config.update(generation=config["generation"] + 1, alerted=None, snooze=None, rest=None)
            self.pending.pop((key, channel), None)
            self.cancel_deliveries(key, channel)
        if set(updated) & {"name", "target", "armed", "stall"}:
            self.stall_tracking.pop((key, channel), None)
        if "stall" in updated:
            config["stall_alerted"] = None
            self.cancel_deliveries(key, channel, "stall")
        if updated.get("rest_minutes") == 0 or (updated.get("rest_auto") is False and config.get("rest_source") == "auto"):
            config["rest"] = None
        self.event(key, now, "settings", channel=channel, settings=deepcopy(config))
        if "name" in updated and device["session"]:
            summary = self.data["index"][device["session"]]
            next(c for c in summary["layout"] if c["id"] == channel)["name"] = config["name"]
            self.histories[device["session"]]["summary"] = deepcopy(summary)

    def finish(self, key, now):
        device = self.data["devices"][key]
        sid = device["session"]
        if not sid:
            return None
        self.event(key, now, "finished")
        for channel, config in device["channels"].items():
            config.update(armed=False, snooze=None, rest=None)
            self.pending.pop((key, channel), None)
            self.pending.pop((key, channel, "stall"), None)
            self.stall_tracking.pop((key, channel), None)
            self.cancel_deliveries(key, channel)
        self.data["index"][sid]["ended"] = now
        self.histories[sid]["summary"] = deepcopy(self.data["index"][sid])
        device["session"] = None
        return sid

    def reminder(self, key, channel, kind, minutes, now):
        config = self.data["devices"][key]["channels"][channel]
        if kind == "dismiss":
            config.update(snooze=None, rest=None)
        elif kind in {"snooze", "rest"} and config["armed"] and config["alerted"] == config["generation"]:
            value = number(minutes)
            if value is None or not 0 <= value <= 1440:
                raise ValueError("Reminder must be between 0 and 1440 minutes")
            config.update(snooze=None, rest=None)
            if value > 0:
                config[kind] = now + value * 60
                if kind == "rest":
                    config["rest_source"] = "manual"
        else:
            raise ValueError("Reach the target before setting a reminder")
        self.event(key, now, kind, channel=channel)

    def tick(self, readings, now, options=None):
        options = options or {}
        self.options = options
        notices = []
        changed = False
        for key, device in self.data["devices"].items():
            sid = device["session"]
            history = self.histories.get(sid)
            current = readings.get(key, {})
            recent = self.live_history.setdefault(key, [])
            if not recent or now - recent[-1]["at"] >= SAMPLE_SECONDS:
                recent.append(self.sample(device, current, now))
                self.live_history[key] = recent[-120:]
            if history and (not history["samples"] or now - history["samples"][-1]["at"] >= SAMPLE_SECONDS):
                history["samples"].append(self.sample(device, current, now))
                self.data["index"][sid]["sample_count"] = len(history["samples"])
                history["summary"] = deepcopy(self.data["index"][sid])
                changed = True
            for channel, config in device["channels"].items():
                row = current.get(channel, {})
                ready = bool(
                    sid and config["armed"] and config["target"] > 0 and fresh(row, now) and row["temperature"] >= config["target"]
                )
                pending_key = (key, channel)
                kind = None
                if not ready:
                    self.pending.pop(pending_key, None)
                else:
                    since = self.pending.setdefault(pending_key, now)
                    if config["alerted"] != config["generation"] and now - since >= READY_SECONDS:
                        config["alerted"] = config["generation"]
                        kind = "target"
                        minutes = config.get("rest_minutes")
                        if minutes is None:
                            minutes = options.get("rest_minutes", 0)
                        if config.get("rest_auto") and minutes > 0:
                            config["rest"] = now + minutes * 60
                            config["rest_source"] = "auto"
                for reminder in ("snooze", "rest"):
                    deadline = config[reminder]
                    if deadline is not None and now - deadline > 300:
                        config[reminder] = None
                        self.event(key, now, "reminder_expired", channel=channel, reminder=reminder)
                        changed = True
                    elif deadline is not None and now >= deadline and sid and config["armed"] and (reminder == "rest" or ready):
                        config[reminder] = None
                        kind = reminder
                if kind:
                    notice = {
                        "device_id": key,
                        "device_name": device["alias"],
                        "channel": channel,
                        "name": config["name"],
                        "temperature": number(row.get("temperature")),
                        "target": config["target"],
                        "session": sid,
                        "generation": config["generation"],
                        "kind": kind,
                    }
                    notices.append(notice)
                    self.event(key, now, "alert", notice=deepcopy(notice), channel=channel)
                    changed = True
        warnings = self.warnings(readings, now, options)
        return notices + warnings, changed or bool(warnings)

    @staticmethod
    def sample(device, readings, now):
        return {
            "at": now,
            "channels": {
                channel: {
                    "temperature": row.get("temperature") if fresh(row, now) else None,
                    "ambient": row.get("ambient") if fresh(row, now) else None,
                    "battery": row.get("battery"),
                    "target": config["target"],
                    "armed": config["armed"],
                }
                for channel, config in device["channels"].items()
                if (row := readings.get(channel, {})) is not None
            },
        }

    def warnings(self, readings, now, options):
        notices = []
        for key, device in self.data["devices"].items():
            history = self.histories.get(device["session"])
            if not history:
                continue
            for channel, config in device["channels"].items():
                row = readings.get(key, {}).get(channel, {})
                if not config["armed"] or not fresh(row, now):
                    self.stall_tracking.pop((key, channel), None)
                    continue
                battery = number(row.get("battery"))
                low = row.get("battery_low") is True or (
                    battery is not None and battery <= options.get("battery_threshold", 10) and row.get("battery_suspect") is False
                )
                kinds = []
                if options.get("battery") and low:
                    if device["model"] != "iht2pb" or device.get("battery_alerted_session") != device["session"]:
                        kinds.append("battery")
                        if device["model"] == "iht2pb":
                            device["battery_alerted_session"] = device["session"]
                rule = config["stall"]
                enabled = options.get("stall") if rule["enabled"] is None else rule["enabled"]
                stall_key = (key, channel)
                if not enabled or not rule["min_temp"] <= row["temperature"] < config["target"]:
                    self.stall_tracking.pop(stall_key, None)
                else:
                    tracking = self.stall_tracking.setdefault(
                        stall_key,
                        {
                            "since": now,
                            "last": now,
                            "low": row["temperature"],
                            "high": row["temperature"],
                        },
                    )
                    tracking["low"] = min(tracking["low"], row["temperature"])
                    tracking["high"] = max(tracking["high"], row["temperature"])
                    if now - tracking["last"] > 90 or tracking["high"] - tracking["low"] > rule["rate"] * rule["minutes"] / 60:
                        tracking.update(since=now, low=row["temperature"], high=row["temperature"])
                    tracking["last"] = now
                if stall_key in self.stall_tracking and now - self.stall_tracking[stall_key]["since"] >= rule["minutes"] * 60:
                    kinds.append("stall")
                for kind in kinds:
                    latch = f"{kind}_alerted"
                    if config.get(latch) == config["generation"]:
                        continue
                    config[latch] = config["generation"]
                    notice = {
                        "device_id": key,
                        "device_name": device["alias"],
                        "channel": channel,
                        "name": config["name"],
                        "temperature": row["temperature"],
                        "target": config["target"],
                        "session": device["session"],
                        "generation": config["generation"],
                        "kind": kind,
                    }
                    notices.append(notice)
                    self.event(key, now, "alert", channel=channel, notice=deepcopy(notice))
        return notices

    def cancel_deliveries(self, key, channel, kind=None):
        for event in self.data["outbox"].values():
            if event["device_id"] == key and event["channel"] == channel and (kind is None or event["kind"] == kind):
                for output in event["outputs"].values():
                    if output["state"] in {"queued", "error"}:
                        output["state"] = "cancelled"

    def enqueue(self, notice, outputs, now):
        identifier = uuid4().hex
        self.data["outbox"][identifier] = {**deepcopy(notice), "id": identifier, "created": now, "outputs": outputs}
        if notice["kind"] != "test":
            self.data["devices"][notice["device_id"]]["channels"][notice["channel"]]["last_notice"] = identifier
        protected = {c.get("last_notice") for d in self.data["devices"].values() for c in d["channels"].values()}
        removable = [
            key
            for key, event in self.data["outbox"].items()
            if key not in protected
            and all(o["state"] in {"accepted", "disabled", "cancelled", "skipped"} for o in event["outputs"].values())
        ]
        for key in removable[: max(0, len(self.data["outbox"]) - 200)]:
            del self.data["outbox"][key]
        return identifier

    def retry(self, identifier, output_id=None):
        event = self.data["outbox"].get(identifier)
        if not event:
            raise ValueError("Unknown notification")
        device = self.data["devices"][event["device_id"]]
        config = device["channels"][event["channel"]]
        if event["kind"] != "test" and (
            device["session"] != event["session"] or config["generation"] != event["generation"] or not config["armed"]
        ):
            raise ValueError("That notification belongs to an older cook")
        for key, output in event["outputs"].items():
            if (output_id is None or key == output_id) and output["state"] in {"error", "unknown"}:
                output.update(state="queued", attempts=0, next_at=0, error=None)

    def expire_deliveries(self, now):
        changed = False
        for event in self.data["outbox"].values():
            if now - event["created"] <= 300:
                continue
            for output in event["outputs"].values():
                if output["state"] in {"queued", "error"}:
                    output.update(state="unknown", error="Old event: check before retrying")
                    changed = True
        return changed

    def snapshot(self, readings, now):
        result = []
        for key, device in self.data["devices"].items():
            row = deepcopy(device)
            for channel, config in row["channels"].items():
                reading = readings.get(key, {}).get(channel, {})
                config.update(reading)
                config["fresh"] = fresh(reading, now)
                since = self.pending.get((key, channel))
                config["ready_seconds"] = max(0, now - since) if since is not None else 0
                config["status"] = (
                    "off"
                    if not config["armed"]
                    else "stale"
                    if not config["fresh"]
                    else "reached"
                    if config["alerted"] == config["generation"]
                    else "ready"
                    if since is not None
                    else "cooking"
                )
                config["reached"] = config["alerted"] == config["generation"]
                notice = self.data["outbox"].get(config.get("last_notice"), {})
                config["delivery"] = [
                    {"id": name, **{field: value.get(field) for field in ("state", "label", "attempts", "error")}}
                    for name, value in notice.get("outputs", {}).items()
                ]
                config["notice_id"] = notice.get("id")
                tracking = self.stall_tracking.get((row["id"], channel))
                config["stall_progress"] = {"elapsed": max(0, now - tracking["since"]) if tracking else 0, "tracking": bool(tracking)}
                rule = config["stall"]
                enabled = self.options.get("stall") if rule["enabled"] is None else rule["enabled"]
                config["stall_progress"]["reason"] = (
                    "not_armed"
                    if not config["armed"]
                    else "disabled"
                    if not enabled
                    else "stale"
                    if not config["fresh"]
                    else "below_minimum"
                    if reading["temperature"] < rule["min_temp"]
                    else "above_target"
                    if reading["temperature"] >= config["target"]
                    else "tracking"
                )
                recent = self.live_history.get(row["id"], [])
                window = [sample for sample in recent if now - 720 <= sample["at"] <= now]
                valid = (
                    len(window) >= 22
                    and now - window[0]["at"] >= 660
                    and all(sample["channels"].get(channel, {}).get("temperature") is not None for sample in window)
                )
                config["rate"] = (
                    ((reading["temperature"] - window[0]["channels"][channel]["temperature"]) * 3600 / (now - window[0]["at"]))
                    if valid and fresh(reading, now)
                    else None
                )
            row["cook"] = deepcopy(self.data["index"].get(row["session"]))
            recorded = self.histories.get(row["session"], {}).get("samples", [])
            row["recent"] = deepcopy((recorded or self.live_history.get(key, []))[-120:])
            result.append(row)
        return {
            "version": "1.2.1",
            "now": now,
            "initial_device": self.data.get("initial_device"),
            "devices": result,
            "history": sorted(deepcopy(list(self.data["index"].values())), key=lambda r: r["started"], reverse=True),
            "preset": deepcopy(self.data["preset"]),
            "tests": [
                {
                    "id": event["id"],
                    "device_name": event["device_name"],
                    "created": event["created"],
                    "outputs": [
                        {"id": name, **{field: value.get(field) for field in ("label", "state", "error")}}
                        for name, value in event["outputs"].items()
                    ],
                }
                for event in list(self.data["outbox"].values())[-20:]
                if event["kind"] == "test"
            ],
        }


def announcement(notice, device, italian):
    """Food names belong in speech; model codes and entity IDs do not."""
    name = notice["name"]
    default = next(c["name"] for c in device["layout"] if c["id"] == notice["channel"])
    if name == default or name.lower() in {f"sonda {notice['channel']}", f"probe {notice['channel']}"}:
        channel = (
            (
                f"Sonda {notice['channel']}"
                if device["model"] == "int14_bw"
                else ["Punta integrata", "Sonda esterna 1", "Sonda esterna 2"][int(notice["channel"]) - 1]
            )
            if italian
            else default
        )
        name = f"{channel}, {device['alias']}"
    if notice.get("disambiguate") and name == notice["name"]:
        name = f"{name}, {device['alias']}, " + (f"sonda {notice['channel']}" if italian else f"probe {notice['channel']}")
    value = f"{notice['temperature']:.1f}".rstrip("0").rstrip(".") if notice.get("temperature") is not None else ""
    if notice["kind"] == "battery":
        return f"{name}: batteria bassa." if italian else f"{name}: low battery."
    if notice["kind"] == "stall":
        return (
            f"{name}: la temperatura non sale da un po, siamo a {value} gradi."
            if italian
            else f"{name}: the temperature has stalled at {value} degrees."
        )
    if notice["kind"] == "rest":
        return f"{name}: il tempo di riposo e finito." if italian else f"{name}: the rest timer has finished."
    if notice["kind"] == "snooze":
        return f"{name} e ancora sopra soglia, a {value} gradi." if italian else f"{name} is still above the target, at {value} degrees."
    return f"{name} ha raggiunto {value} gradi." if italian else f"{name} has reached {value} degrees."
