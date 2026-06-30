"""Diagnostics support with conservative redaction."""

from __future__ import annotations

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


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return redacted config entry diagnostics."""

    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    payload: dict[str, Any] = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
    }
    if runtime is not None:
        payload["runtime_type"] = type(runtime).__name__
        for attr in ("address", "session", "device", "config"):
            value = getattr(runtime, attr, None)
            if value is not None:
                payload[attr] = async_redact_data(value if isinstance(value, dict) else str(value), TO_REDACT)
    return payload
