"""Diagnostics support with conservative redaction."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {
    "address",
    "api_key",
    "api_secret",
    "ble_address",
    "cloud_api_key",
    "cloud_api_secret",
    "cloud_dev_id",
    "cloud_product_id",
    "deviceCode",
    "device_id",
    "dev_id",
    "devId",
    "hashKey",
    "host",
    "ip",
    "lan_device_id",
    "lan_host",
    "lan_local_key",
    "local_key",
    "localKey",
    "mac",
    "password",
    "product_id",
    "session_sid",
    "session_token",
    "sid",
    "ssid",
    "station_mac",
    "token",
}

RUNTIME_DIAGNOSTIC_KEYS = {
    "active_transport",
    "base_temp_f_tenths",
    "ble_connected",
    "ble_enabled",
    "live_temperature_channel_count",
    "model",
    "model_profile",
    "model_support_status",
    "probe_count",
    "probe_layout_summary",
    "temperature_channel_count",
    "transport_mode",
}
MULTISENSOR_RUNTIME_KEY_PATTERN = re.compile(
    r"probe_[1-4]_(?:internal_(?:f_tenths|raw_f_hundredths)|food_[1-4]_f_tenths|ambient_f_tenths|multisensor_status)"
)
MAC_PATTERN = re.compile(r"(?i)(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}")
IPV4_PATTERN = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")


def _sanitize_runtime_value(value: Any) -> Any:
    if isinstance(value, str):
        return IPV4_PATTERN.sub("**REDACTED_IP**", MAC_PATTERN.sub("**REDACTED_MAC**", value))
    if isinstance(value, list):
        return [_sanitize_runtime_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_runtime_value(item) for key, item in value.items()}
    return value


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return redacted config entry diagnostics."""

    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    payload: dict[str, Any] = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
    }
    if runtime is not None:
        payload["runtime_type"] = type(runtime).__name__
        runtime_data = {
            key: value
            for key, value in runtime.data.items()
            if key in RUNTIME_DIAGNOSTIC_KEYS or key.startswith("ble_debug_") or MULTISENSOR_RUNTIME_KEY_PATTERN.fullmatch(key)
        }
        payload["runtime"] = async_redact_data(_sanitize_runtime_value(runtime_data), TO_REDACT)
    return payload
