from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH_PATH = ROOT / "custom_components" / "inkbird_int14" / "auth.py"

spec = importlib.util.spec_from_file_location("inkbird_int14_auth", AUTH_PATH)
assert spec is not None
auth = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(auth)


def _millis_from_auth_response(response: bytes) -> int:
    millis = int.from_bytes(response[2:4], "little")
    seconds = int.from_bytes(response[4:8], "little")
    return seconds * 1000 + millis


def test_auth_response_matches_observed_vector() -> None:
    challenge = bytes([0xAA, 0xE1, 0x53, 0x57, 0x9B, 0x0D])
    expected = bytes([0x08, 0xFC, 0xC3, 0x01, 0x52, 0x3C, 0x44, 0x6A, 0x7C])

    assert auth.build_auth_response(challenge, _millis_from_auth_response(expected)) == expected


def test_auth_response_validates_challenge_length() -> None:
    try:
        auth.build_auth_response(bytes.fromhex("0102030405"), 0)
    except ValueError as exc:
        assert "6 bytes" in str(exc)
    else:
        raise AssertionError("short challenge accepted")


def test_auth_frame_helpers() -> None:
    challenge = bytes([0xAA, 0xE1, 0x53, 0x57, 0x9B, 0x0D])
    challenge_frame = bytes([0x07, 0xFB]) + challenge
    assert auth.AUTH_CHALLENGE_REQUEST == bytes.fromhex("01fb")
    assert auth.auth_challenge_from_frame(challenge_frame) == challenge
    assert auth.auth_challenge_from_frame(bytes.fromhex("02fc00")) is None
    assert auth.auth_ack_ok(bytes.fromhex("02fc00")) is True
    assert auth.auth_ack_ok(bytes.fromhex("02fc01")) is False
    assert auth.auth_ack_ok(challenge_frame) is None
