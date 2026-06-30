"""INT-14 BLE authentication helpers."""

from __future__ import annotations

import time

AUTH_CHALLENGE_REQUEST = bytes.fromhex("01fb")


def _crc8(data: bytes | list[int], poly: int, init: int) -> int:
    crc = init
    for value in data:
        crc ^= value & 0xFF
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ poly) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def crc8_dvbs2(data: bytes | list[int]) -> int:
    return _crc8(data, 0xD5, 0x00)


def crc8_cdma2000(data: bytes | list[int]) -> int:
    return _crc8(data, 0x9B, 0xFF)


def build_auth_response(challenge: bytes, now_ms: int | None = None) -> bytes:
    """Build the FF02 authentication response for a 6-byte challenge.

    Algorithm adapted from paul43210/inkbird-bw-ble.
    Copyright (c) 2026 Paul Faure. MIT License.
    """
    if len(challenge) != 6:
        raise ValueError("INT-14 auth challenge must be exactly 6 bytes")
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    seconds = now_ms // 1000
    millis = now_ms % 1000
    body = [
        millis & 0xFF,
        (millis >> 8) & 0xFF,
        seconds & 0xFF,
        (seconds >> 8) & 0xFF,
        (seconds >> 16) & 0xFF,
        (seconds >> 24) & 0xFF,
    ]
    inner = crc8_dvbs2(body)
    challenge_crc = crc8_cdma2000(challenge)
    body.append(crc8_dvbs2(body + [inner, challenge_crc]))
    return bytes([len(body) + 1, 0xFC, *body])


def auth_challenge_from_frame(raw: bytes) -> bytes | None:
    if len(raw) >= 8 and raw[0] == 0x07 and raw[1] == 0xFB:
        return raw[2:8]
    return None


def auth_ack_ok(raw: bytes) -> bool | None:
    if len(raw) >= 3 and raw[0] == 0x02 and raw[1] == 0xFC:
        return raw[2] == 0
    return None
