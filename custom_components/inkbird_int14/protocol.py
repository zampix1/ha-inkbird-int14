from __future__ import annotations

import re
import time
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

SENTINELS = {32766, 32767, 32768}
INIT_STATIC_FRAMES = [
    "0104",
    "020201",
    "020202",
    "020204",
    "020208",
    "0106",
    "020aff",
    "010c",
    "0115",
    "0124",
    "022601",
    "022602",
    "022604",
    "022608",
]
DEGREE_INDEX_TO_CODE = {
    1: 0x01,
    2: 0x03,
    3: 0x05,
    4: 0x07,
    5: 0x0A,
}


def clean_hex(value: str) -> str:
    text = re.sub(r"[^0-9a-fA-F]", "", value)
    if len(text) % 2:
        raise ValueError("odd hex length")
    return text.lower()


def frame(raw_command_hex: str) -> str:
    raw = clean_hex(raw_command_hex)
    return f"{len(raw) // 2:02x}{raw}"


def frame_bytes(raw_command_hex: str) -> bytes:
    return bytes.fromhex(frame(raw_command_hex))


def probe_mask(probe: int) -> int:
    if probe < 1 or probe > 4:
        raise ValueError("probe must be 1..4")
    return 1 << (probe - 1)


def split_frames(payload: bytes) -> list[bytes]:
    out: list[bytes] = []
    pos = 0
    while pos < len(payload):
        size = payload[pos]
        pos += 1
        if size == 0 or pos + size > len(payload):
            return [payload]
        out.append(payload[pos : pos + size])
        pos += size
    return out


def time_service(now_ms: int | None = None) -> str:
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    seconds = now_ms // 1000
    millis = now_ms % 1000
    return seconds.to_bytes(4, "little").hex() + millis.to_bytes(2, "little").hex()


def init_payload(now_ms: int | None = None) -> bytes:
    return b"".join(init_command_frames(now_ms))


def init_command_frames(now_ms: int | None = None) -> list[bytes]:
    return [
        bytes.fromhex(frame("19" + time_service(now_ms))),
        *[bytes.fromhex(command) for command in INIT_STATIC_FRAMES],
    ]


def init_command_chunks(now_ms: int | None = None, max_chunk_len: int = 18) -> list[bytes]:
    chunks: list[bytes] = []
    current = bytearray()
    for item in init_command_frames(now_ms):
        if current and len(current) + len(item) > max_chunk_len:
            chunks.append(bytes(current))
            current.clear()
        current.extend(item)
    if current:
        chunks.append(bytes(current))
    return chunks


def build_unit_command(unit: str) -> bytes:
    unit_u = unit.upper()
    if unit_u not in {"C", "F"}:
        raise ValueError("unit must be C or F")
    return frame_bytes("03" + ("43" if unit_u == "C" else "46"))


def build_display_light_command(value: int) -> bytes:
    if value < 0 or value > 255:
        raise ValueError("display light must be 0..255")
    return frame_bytes(f"05{value:02x}")


def build_target_command(
    *,
    probe: int,
    mode: str,
    high_tenths: int = 0,
    low_tenths: int = 0,
    degree_index: int = 0,
    food_index: int = -1,
) -> bytes:
    if mode not in {"01", "10", "11"}:
        raise ValueError("mode must be 01, 10, or 11")
    degree_code = DEGREE_INDEX_TO_CODE.get(degree_index, 0)
    raw = (
        "01"
        + f"{probe_mask(probe):02x}"
        + mode
        + int(high_tenths).to_bytes(2, "little", signed=True).hex()
        + int(low_tenths).to_bytes(2, "little", signed=True).hex()
        + f"{degree_code:02x}"
        + f"{food_index + 1:02x}"
    )
    return frame_bytes(raw)


def build_pre_alarm_command(probe: int, advance_values: list[int]) -> bytes:
    values = (advance_values + [0, 0, 0, 0])[:4]
    raw = "23" + f"{probe_mask(probe):02x}" + "".join(f"{value & 0xFF:02x}" for value in values)
    return frame_bytes(raw)


def build_timer_command(probe: int, start_epoch_s: int, end_epoch_s: int, *, count_down: bool) -> bytes:
    flags = probe_mask(probe)
    if not count_down:
        flags |= 0x80
    raw = "25" + f"{flags:02x}" + int(start_epoch_s).to_bytes(4, "little").hex() + int(end_epoch_s).to_bytes(4, "little").hex()
    return frame_bytes(raw)


def build_timer_reset_command(probe: int) -> bytes:
    return frame_bytes("27" + f"{probe_mask(probe):02x}" + "00")


def build_probe_pair_command(probe: int, *, rssi_threshold: int = -80, version_code_literal: str = "34") -> bytes:
    raw = version_code_literal + f"{probe_mask(probe):02x}" + f"{rssi_threshold & 0xFF:02x}"
    return frame_bytes(raw)


def build_probe_pair_cancel_command(*, rssi_threshold: int = -80) -> bytes:
    return frame_bytes("3200" + f"{rssi_threshold & 0xFF:02x}")


def build_calibration_command(*, probe: int, channel: str, c_value: float) -> bytes:
    if channel not in {"internal", "ambient"}:
        raise ValueError("channel must be internal or ambient")
    raw_f_tenths = half_up_int(c_value * 18.0)
    if raw_f_tenths < -128 or raw_f_tenths > 127:
        raise ValueError("calibration must fit signed int8 after C to F-tenths conversion")
    mask = probe_mask(probe)
    payload = [0] * 9
    if channel == "ambient":
        mask <<= 4
        payload[4 + probe] = raw_f_tenths & 0xFF
    else:
        payload[probe] = raw_f_tenths & 0xFF
    payload[0] = mask
    return frame_bytes("09" + bytes(payload).hex())


def _single_command_payload(command: bytes, opcode: int) -> bytes:
    frames = split_frames(command)
    if len(frames) != 1 or not frames[0] or frames[0][0] != opcode:
        raise ValueError(f"unexpected command shape for opcode {opcode:02x}")
    return frames[0][1:]


def build_target_dp_value(
    *,
    probe: int,
    mode: str,
    high_tenths: int = 0,
    low_tenths: int = 0,
    degree_index: int = 0,
    food_index: int = -1,
) -> str:
    command = split_frames(
        build_target_command(
            probe=probe,
            mode=mode,
            high_tenths=high_tenths,
            low_tenths=low_tenths,
            degree_index=degree_index,
            food_index=food_index,
        )
    )[0]
    if command[0] != 0x01:
        raise ValueError("unexpected target command opcode")
    return command[2:].hex()


def build_pre_alarm_dp_value(probe: int, advance_values: list[int]) -> str:
    return _single_command_payload(build_pre_alarm_command(probe, advance_values), 0x23).hex()


def build_calibration_dp_value(*, probe: int, channel: str, c_value: float) -> str:
    return _single_command_payload(
        build_calibration_command(probe=probe, channel=channel, c_value=c_value),
        0x09,
    ).hex()


def build_timer_dp_value(probe: int, start_epoch_s: int, end_epoch_s: int, *, count_down: bool) -> str:
    return _single_command_payload(
        build_timer_command(probe, start_epoch_s, end_epoch_s, count_down=count_down),
        0x25,
    ).hex()


def build_timer_reset_dp_value(probe: int) -> str:
    return _single_command_payload(build_timer_reset_command(probe), 0x27).hex()


def le_i16(value: bytes) -> int:
    return int.from_bytes(value, "little", signed=True)


def le_u32(value: bytes) -> int:
    return int.from_bytes(value, "little", signed=False)


def signed_i8(value: int) -> int:
    return value - 256 if value >= 128 else value


def probe_from_mask(mask: int) -> int | None:
    if mask <= 0:
        return None
    return (mask & 0x0F).bit_length()


def half_up_int(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def c_tenths_to_f_tenths(value: int) -> int:
    return half_up_int(value * 1.8 + 320)


def parse_probe_temperature_block(raw: bytes) -> list[dict[str, Any]]:
    probes = []
    for index in range(min(4, len(raw) // 4)):
        chunk = raw[index * 4 : index * 4 + 4]
        internal_c = le_i16(chunk[0:2])
        ambient_c = le_i16(chunk[2:4])
        probes.append(
            {
                "probe": index + 1,
                "internal_f_tenths": abs(internal_c) if abs(internal_c) in SENTINELS else c_tenths_to_f_tenths(internal_c),
                "ambient_f_tenths": abs(ambient_c) if abs(ambient_c) in SENTINELS else c_tenths_to_f_tenths(ambient_c),
            }
        )
    return probes


def parse_current_temp_payload(raw: bytes) -> dict[str, Any] | None:
    if len(raw) < 18:
        return None
    base_temp_f_tenths = int.from_bytes(raw[16:18], "little", signed=False)
    return {
        "probes": parse_probe_temperature_block(raw[:16]),
        "base_temp_raw": base_temp_f_tenths,
        "base_temp_f_tenths": base_temp_f_tenths,
    }


def parse_battery_payload(raw: bytes) -> dict[str, Any] | None:
    if len(raw) < 5:
        return None
    return {
        "base_power": None if raw[0] == 0x7F else raw[0],
        "probe_battery": {index: None if byte == 0x7F else min(byte, 100) for index, byte in enumerate(raw[1:5], start=1)},
    }


def bits_lsb_per_byte(raw: bytes) -> list[int]:
    bits: list[int] = []
    for byte in raw:
        for bit in range(8):
            bits.append((byte >> bit) & 1)
    return bits


def parse_state_payload(raw: bytes) -> dict[str, Any] | None:
    if len(raw) < 11:
        return None
    bits = bits_lsb_per_byte(raw)
    probes = []
    for index in range(4):
        off = index * 16
        probes.append(
            {
                "probe": index + 1,
                "connect": bool(bits[off]),
                "charging": bool(bits[off + 1]),
                "internal_low_alarm": bool(bits[off + 3]),
                "internal_high_alarm": bool(bits[off + 4]),
                "internal_over_high_alarm": bool(bits[off + 7]),
                "internal_over_low_alarm": bool(bits[off + 8]),
                "advance_alarm": bool(bits[off + 9]),
                "ambient_over_high_alarm": bool(bits[off + 10]),
                "ambient_over_low_alarm": bool(bits[off + 11]),
                "paired": bool(bits[off + 12]),
                "pair_request": bool(bits[off + 13]),
                "battery_alarm": bool(bits[off + 14]),
                "timer_alarm": bool(bits[index + 75]) if index + 75 < len(bits) else None,
                "timer_switch": bool(bits[index + 79]) if index + 79 < len(bits) else None,
            }
        )
    return {
        "probes": probes,
        "base_charging": bool(bits[64]) if len(bits) > 64 else None,
        "wifi_switch": bool(bits[65]) if len(bits) > 65 else None,
        "wifi_state": bits[68] if len(bits) > 68 else None,
        "verify": bool(bits[72]) if len(bits) > 72 else None,
        "device_over_high_temp_alarm": bool(bits[83]) if len(bits) > 83 else None,
        "device_over_low_temp_alarm": bool(bits[84]) if len(bits) > 84 else None,
    }


def parse_target_payload(raw: bytes) -> dict[str, Any] | None:
    if len(raw) < 8:
        return None
    mode = f"{raw[1]:02x}"
    return {
        "probe": probe_from_mask(raw[0]),
        "probe_mask": f"{raw[0]:02x}",
        "mode": mode,
        "mode_name": {"01": "low", "10": "high", "11": "range"}.get(mode, "unknown"),
        "target_high_f_tenths": le_i16(raw[2:4]),
        "target_low_f_tenths": le_i16(raw[4:6]),
        "degree_code": f"{raw[6]:02x}",
        "food_index": raw[7] - 1,
    }


def parse_pre_alarm_payload(raw: bytes) -> dict[str, Any] | None:
    if len(raw) < 5:
        return None
    return {
        "probe_mask": f"{raw[0]:02x}",
        "advance_values": list(raw[1:5]),
    }


def parse_timer_payload(raw: bytes) -> dict[str, Any] | None:
    if len(raw) < 9:
        return None
    flags = raw[0]
    return {
        "probe": probe_from_mask(flags),
        "probe_mask": f"{flags & 0x0F:02x}",
        "raw_flags": f"{flags:02x}",
        "cd_mode": (flags >> 7) == 0,
        "start_epoch_s": le_u32(raw[1:5]),
        "end_epoch_s": le_u32(raw[5:9]),
    }


def timer_epoch_values_plausible(
    start_epoch_s: int | None,
    end_epoch_s: int | None,
    *,
    now_epoch_s: int | None = None,
    max_duration_s: int = 7 * 24 * 60 * 60,
    max_clock_window_s: int = 30 * 24 * 60 * 60,
) -> bool:
    if not isinstance(start_epoch_s, int) or not isinstance(end_epoch_s, int):
        return False
    if start_epoch_s <= 0 or end_epoch_s <= 0 or end_epoch_s < start_epoch_s:
        return False
    if end_epoch_s - start_epoch_s > max_duration_s:
        return False
    now = int(time.time()) if now_epoch_s is None else int(now_epoch_s)
    return start_epoch_s >= now - max_clock_window_s and end_epoch_s <= now + max_clock_window_s


def parse_calibration_payload(raw: bytes) -> dict[str, Any] | None:
    if len(raw) < 9:
        return None
    mask = raw[0]
    internal: dict[int, dict[str, Any]] = {}
    ambient: dict[int, dict[str, Any]] = {}
    for index in range(4):
        if (mask >> index) & 1:
            value = signed_i8(raw[1 + index])
            internal[index + 1] = {
                "raw_f_tenths": value,
                "c_value": value / 18.0,
            }
        if (mask >> (index + 4)) & 1:
            value = signed_i8(raw[5 + index])
            ambient[index + 1] = {
                "raw_f_tenths": value,
                "c_value": value / 18.0,
            }
    return {"mask": f"{mask:02x}", "internal": internal, "ambient": ambient}


def _cloud_hex(value: Any) -> bytes:
    return bytes.fromhex(clean_hex(str(value)))


def parse_cloud_dps(dps: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"frames": [], "dp_keys": sorted(str(key) for key in dps.keys())}

    if dps.get("101") is not None:
        unit = str(dps["101"]).upper()
        result["frames"].append({"name": "unit_candidate", "transport": "cloud_dp101", "unit": unit, "is_f": unit == "F"})
    if dps.get("103") is not None:
        raw = _cloud_hex(dps["103"])
        battery = parse_battery_payload(raw)
        if battery:
            result["frames"].append({"name": "battery_candidate", "transport": "cloud_dp103", "raw_hex": raw.hex(), **battery})
    if dps.get("104") is not None:
        result["frames"].append({"name": "display_light_candidate", "transport": "cloud_dp104", "display_light": int(dps["104"])})
    if dps.get("106") is not None:
        sound = str(dps["106"]).lower() == "true"
        result["frames"].append({"name": "sound_candidate", "transport": "cloud_dp106", "sound_enabled": sound, "dev_mute": not sound})
    if dps.get("109") is not None:
        current = parse_current_temp_payload(_cloud_hex(dps["109"]))
        if current:
            result["frames"].append({"name": "current_temp_candidate", "transport": "cloud_dp109", **current})
    if dps.get("110") is not None:
        calibration = parse_calibration_payload(_cloud_hex(dps["110"]))
        if calibration:
            result["frames"].append({"name": "calibration_candidate", "transport": "cloud_dp110", **calibration})
    if dps.get("116") is not None:
        pre_alarm = parse_pre_alarm_payload(_cloud_hex(dps["116"]))
        if pre_alarm:
            result["frames"].append({"name": "pre_alarm_candidate", "transport": "cloud_dp116", **pre_alarm})

    for dp_id, probe in {"122": 1, "123": 2, "124": 3, "125": 4}.items():
        if dps.get(dp_id) is None:
            continue
        target = parse_target_payload(bytes([1 << (probe - 1)]) + _cloud_hex(dps[dp_id]))
        if target:
            result["frames"].append({"name": "target_candidate", "transport": f"cloud_dp{dp_id}", **target})

    for dp_id in ("126", "127", "128", "129"):
        if dps.get(dp_id) is None:
            continue
        timer = parse_timer_payload(_cloud_hex(dps[dp_id]))
        if timer:
            result["frames"].append({"name": "timer_candidate", "transport": f"cloud_dp{dp_id}", **timer})

    if dps.get("131") is not None:
        state = parse_state_payload(_cloud_hex(dps["131"]))
        if state:
            result["frames"].append({"name": "state_candidate", "transport": "cloud_dp131", **state})

    return result


def parse_notification(raw: bytes) -> dict[str, Any]:
    result: dict[str, Any] = {"raw_hex": raw.hex(), "frames": []}
    if len(raw) == 18:
        current = parse_current_temp_payload(raw)
        if current:
            result["frames"].append({"name": "current_temp_candidate", "transport": "raw_ff01", **current})
            return result
    if len(raw) == 5:
        battery = parse_battery_payload(raw)
        if battery:
            result["frames"].append({"name": "battery_candidate", "transport": "raw_2a19", "raw_hex": raw.hex(), **battery})
            return result
    if len(raw) == 11:
        state = parse_state_payload(raw)
        if state:
            result["frames"].append({"name": "state_candidate", "transport": "raw_ff03", **state})
            return result
    for command in split_frames(raw):
        if not command:
            continue
        opcode = command[0]
        payload = command[1:]
        item: dict[str, Any] = {"opcode": f"{opcode:02x}", "payload_hex": payload.hex()}
        if opcode == 0x02:
            target = parse_target_payload(payload)
            if target:
                item["name"] = "target_candidate"
                item.update(target)
        elif opcode == 0x04:
            unit_byte = payload[0] if payload else None
            unit = "F" if unit_byte == 0x46 else "C" if unit_byte == 0x43 else None
            item["name"] = "unit_candidate"
            item["unit"] = unit
            item["is_f"] = unit == "F" if unit is not None else None
            item["unit_byte"] = payload[:1].hex()
        elif opcode == 0x06 and len(payload) == 1:
            item["name"] = "display_light_candidate"
            item["display_light"] = payload[0]
        elif opcode == 0x06 and len(payload) >= 9:
            calibration = parse_calibration_payload(payload)
            if calibration:
                item["name"] = "calibration_candidate"
                item.update(calibration)
        elif opcode in {0x0A}:
            current = parse_current_temp_payload(payload)
            if current:
                item["name"] = "current_temp_candidate"
                item.update(current)
        elif opcode == 0x0C:
            muted = bool(payload and payload[0] == 0x11)
            item["name"] = "sound_candidate"
            item["dev_mute"] = muted
            item["sound_enabled"] = not muted
            item["value"] = payload[:1].hex()
        elif opcode == 0x03:
            battery = parse_battery_payload(payload)
            if battery:
                item["name"] = "battery_candidate"
                item["raw_hex"] = payload.hex()
                item.update(battery)
        elif opcode == 0x10:
            state = parse_state_payload(payload)
            if state:
                item["name"] = "state_candidate"
                item.update(state)
        elif opcode == 0x24 and len(payload) == 5:
            pre_alarm = parse_pre_alarm_payload(payload)
            if pre_alarm:
                item["name"] = "pre_alarm_candidate"
                item.update(pre_alarm)
        elif opcode in {0x24, 0x25, 0x26}:
            timer = parse_timer_payload(payload)
            if timer:
                item["name"] = "timer_candidate"
                item.update(timer)
        elif opcode == 0x09:
            calibration = parse_calibration_payload(payload)
            if calibration:
                item["name"] = "calibration_candidate"
                item.update(calibration)
        elif opcode == 0xFB:
            item["name"] = "auth_challenge"
            item["challenge_len"] = len(payload)
        elif opcode == 0xFC:
            item["name"] = "auth_ack"
            item["ok"] = payload[0] == 0 if payload else None
        elif opcode == 0xFE:
            item["name"] = "init_ack_or_error"
            item["status"] = payload[0] if payload else None
        result["frames"].append(item)
    return result
