"""Notification plans use existing settings; no volume, source or power commands."""

import re


def plan(hass, notice, device, message, alexa_entities):
    def value(key):
        state = hass.states.get(key)
        return state.state if state else "unknown"

    def output(label, domain=None, service=None, data=None, **extra):
        return {
            "label": label,
            "domain": domain,
            "service": service,
            "data": data or {},
            "state": "queued",
            "attempts": 0,
            "next_at": 0,
            "error": None,
            "retryable": True,
            **extra,
        }

    tag = f"cook_{notice['session']}_{notice['channel']}_{notice['kind']}_{notice['generation']}"
    title, full_message = "Cook Control", f"{device['alias']}: {message}"
    actions = []
    if notice["kind"] in {"target", "snooze"}:
        actions = [
            {"action": f"COOK:{notice['session']}:{notice['channel']}:{notice['generation']}:{kind}", "title": label}
            for kind, label in (("snooze", "Snooze"), ("rest", "Riposo"), ("dismiss", "OK"))
        ]
    outputs = {
        "ha": output(
            "Home Assistant", "persistent_notification", "create", {"title": title, "message": full_message, "notification_id": tag}
        )
    }
    mobile = value("input_text.bbq_notify_service")
    if mobile in {"", "unknown", "unavailable"}:
        mobile = value("input_select.bbq_notify_target")
    if mobile not in {"", "unknown", "unavailable", "persistent_notification"}:
        if re.fullmatch(r"[a-z0-9_]+", mobile):
            data = {"title": title, "message": full_message}
            if mobile.startswith("mobile_app_"):
                data["data"] = {"tag": tag, "actions": actions}
            outputs["mobile"] = output("Mobile", "notify", mobile, data)
        else:
            outputs["mobile"] = output("Mobile", state="error", retryable=False, error="Invalid notify service")
    if value("input_boolean.bbq_tv_alerts") == "on":
        service, entity = value("input_text.bbq_tv_notify_service"), value("input_text.bbq_tv_entity")
        if re.fullmatch(r"[a-z0-9_]+", service) and re.fullmatch(r"media_player\.[a-z0-9_]+", entity):
            outputs["tv"] = output("TV", "notify", service, {"message": f"{title}: {full_message}"}, guard=entity, tv=True)
        else:
            outputs["tv"] = output("TV", state="error", retryable=False, error="Invalid TV configuration")
    else:
        outputs["tv"] = output("TV", state="disabled")
    if value("input_boolean.bbq_tts_alerts") != "on":
        outputs["voice"] = output("Voce", state="disabled")
        return outputs
    engine, speaker = value("input_select.bbq_tts_engine"), value("input_select.bbq_tts_speaker")
    if engine == "Alexa (native)":
        group = speaker == value("input_text.bbq_alexa_group_name")
        targets = value("input_text.bbq_alexa_group_targets").split(",") if group else [speaker]
        targets = list(dict.fromkeys(t.strip() for t in targets))
        if not targets or any(not re.fullmatch(r"media_player\.[a-z0-9_]+", t) or t not in alexa_entities for t in targets):
            outputs["voice"] = output("Echo", state="error", retryable=False, error="Select an Alexa speaker or valid announcement group")
        else:
            for target in targets:
                state = hass.states.get(target)
                label = state.attributes.get("friendly_name", "Echo") if state else "Echo"
                outputs["echo:" + target] = output(
                    label,
                    "notify",
                    "alexa_media",
                    {"target": [target], "title": title, "message": message, "data": {"type": "announce", "method": "speak"}},
                    guard=target,
                )
    elif re.fullmatch(r"tts\.[a-z0-9_]+", engine) and re.fullmatch(r"media_player\.[a-z0-9_]+", speaker) and speaker not in alexa_entities:
        outputs["voice"] = output(
            "TTS",
            "tts",
            "speak",
            {"entity_id": engine, "media_player_entity_id": speaker, "cache": True, "message": message},
            guard=speaker,
        )
    else:
        outputs["voice"] = output("Voce", state="error", retryable=False, error="Voice engine or speaker not configured")
    return outputs


async def send(hass, output):
    if guard := output.get("guard"):
        state = hass.states.get(guard)
        if not state or state.state in {"unknown", "unavailable"}:
            raise ConnectionError("Notification destination unavailable")
        if output.get("tv") and state.state == "off":
            return "skipped"
    if not output.get("domain") or not output.get("service"):
        raise ValueError("Invalid notification destination")
    await hass.services.async_call(output["domain"], output["service"], output["data"], blocking=True)
    return "accepted"
