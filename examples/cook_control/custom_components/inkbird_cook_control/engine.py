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
            "layout": deepcopy(device["layout"]),
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
        if set(patch) - {"name", "target", "armed"}:
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
        if updated.get("armed", config["armed"]) and updated.get("target", config["target"]) <= 0:
            raise ValueError("Set a target before enabling an alert")
        if all(config.get(k) == v for k, v in updated.items()):
            return
        if updated.get("armed") and not device["session"]:
            self.start(key, now)
        config.update(updated)
        config.update(generation=config["generation"] + 1, alerted=None, snooze=None, rest=None)
        self.pending.pop((key, channel), None)
        self.pending.pop((key, channel, "stall"), None)
        self.event(key, now, "settings", channel=channel, settings=deepcopy(config))

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
            if value is None or not 0 < value <= 1440:
                raise ValueError("Reminder must be between 1 and 1440 minutes")
            config.update(snooze=None, rest=None)
            config[kind] = now + value * 60
        else:
            raise ValueError("Reach the target before setting a reminder")
        self.event(key, now, kind, channel=channel)

    def tick(self, readings, now, options=None):
        notices = []
        changed = False
        for key, device in self.data["devices"].items():
            sid = device["session"]
            history = self.histories.get(sid)
            current = readings.get(key, {})
            if history and (not history["samples"] or now - history["samples"][-1]["at"] >= SAMPLE_SECONDS):
                history["samples"].append(
                    {
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
                            if (row := current.get(channel, {})) is not None
                        },
                    }
                )
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
                for reminder in ("snooze", "rest"):
                    deadline = config[reminder]
                    if deadline is not None and now - deadline > 300:
                        config[reminder] = None
                        self.event(key, now, "reminder_expired", channel=channel, reminder=reminder)
                        changed = True
                    elif (
                        deadline is not None
                        and now >= deadline
                        and sid
                        and config["armed"]
                        and fresh(row, now)
                        and (ready or reminder == "rest")
                    ):
                        config[reminder] = None
                        kind = reminder
                if kind:
                    notice = {
                        "device_id": key,
                        "device_name": device["alias"],
                        "channel": channel,
                        "name": config["name"],
                        "temperature": row["temperature"],
                        "target": config["target"],
                        "session": sid,
                        "generation": config["generation"],
                        "kind": kind,
                    }
                    notices.append(notice)
                    self.event(key, now, "alert", notice=deepcopy(notice), channel=channel)
                    changed = True
        warnings = self.warnings(readings, now, options or {})
        return notices + warnings, changed or bool(warnings)

    def warnings(self, readings, now, options):
        notices = []
        for key, device in self.data["devices"].items():
            history = self.histories.get(device["session"])
            if not history:
                continue
            for channel, config in device["channels"].items():
                row = readings.get(key, {}).get(channel, {})
                if not config["armed"] or not fresh(row, now):
                    self.pending.pop((key, channel, "stall"), None)
                    continue
                battery = number(row.get("battery"))
                low = row.get("battery_low") is True or (
                    battery is not None and battery <= options.get("battery_threshold", 10) and row.get("battery_suspect") is False
                )
                kinds = []
                if options.get("battery") and low:
                    kinds.append("battery")
                window = [s for s in history["samples"] if now - 720 <= s["at"] <= now]
                stable = (
                    options.get("stall")
                    and row["temperature"] >= 40
                    and row["temperature"] < config["target"]
                    and len(window) >= 22
                    and now - window[0]["at"] >= 660
                    and all(s["channels"].get(channel, {}).get("temperature") is not None for s in window)
                )
                if stable:
                    delta = row["temperature"] - window[0]["channels"][channel]["temperature"]
                    stable = abs(delta / ((now - window[0]["at"]) / 60)) < 1 / 60
                stall_key = (key, channel, "stall")
                if not stable:
                    self.pending.pop(stall_key, None)
                elif now - self.pending.setdefault(stall_key, now) >= 2700:
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
                    else "notified"
                    if config["alerted"] == config["generation"]
                    else "ready"
                    if since is not None
                    else "cooking"
                )
            row["cook"] = deepcopy(self.data["index"].get(row["session"]))
            row["recent"] = deepcopy(self.histories.get(row["session"], {}).get("samples", [])[-24:])
            result.append(row)
        return {
            "version": "1.2.0",
            "now": now,
            "initial_device": self.data.get("initial_device"),
            "devices": result,
            "history": sorted(deepcopy(list(self.data["index"].values())), key=lambda r: r["started"], reverse=True),
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
    value = f"{notice['temperature']:.1f}".rstrip("0").rstrip(".")
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
