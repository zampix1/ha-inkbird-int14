from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_ADDRESS,
    CONF_CLOUD_API_KEY,
    CONF_CLOUD_API_SECRET,
    CONF_CLOUD_BASE_URL,
    CONF_CLOUD_COUNTRY_CODE,
    CONF_CLOUD_DEV_ID,
    CONF_CLOUD_HISTORY_ENABLED,
    CONF_CLOUD_POLL_SECONDS,
    CONF_CLOUD_PRODUCT_ID,
    CONF_LAN_DEVICE_ID,
    CONF_LAN_HOST,
    CONF_LAN_LOCAL_KEY,
    CONF_LAN_POLL_SECONDS,
    CONF_LAN_PORT,
    CONF_LAN_TEST_ON_SETUP,
    CONF_LAN_VERSION,
    CONF_MODEL,
    CONF_NAME,
    CONF_REQUEST_INIT_ON_CONNECT,
    CONF_TRANSPORT_MODE,
    DEFAULT_CLOUD_BASE_URL,
    DEFAULT_CLOUD_POLL_SECONDS,
    DEFAULT_LAN_POLL_SECONDS,
    DEFAULT_LAN_PORT,
    DEFAULT_LAN_VERSION,
    DEFAULT_NAME,
    DOMAIN,
    TRANSPORT_MODE_AUTO,
    TRANSPORT_MODES,
)
from .lan import TuyaLanConfig, fetch_lan_dps
from .models import DEFAULT_MODEL, model_options


def _stripped(data: dict[str, Any], key: str) -> str:
    return str(data.get(key) or "").strip()


def _lan_config_from_input(data: dict[str, Any]) -> TuyaLanConfig | None:
    host = _stripped(data, CONF_LAN_HOST)
    dev_id = _stripped(data, CONF_LAN_DEVICE_ID)
    local_key = _stripped(data, CONF_LAN_LOCAL_KEY)
    if not any((host, dev_id, local_key)):
        return None
    return TuyaLanConfig(
        host=host,
        dev_id=dev_id,
        local_key=local_key,
        version=float(data.get(CONF_LAN_VERSION, DEFAULT_LAN_VERSION)),
        port=int(data.get(CONF_LAN_PORT, DEFAULT_LAN_PORT)),
        poll_seconds=max(5, int(data.get(CONF_LAN_POLL_SECONDS, DEFAULT_LAN_POLL_SECONDS))),
    )


def _cloud_enabled(data: dict[str, Any]) -> bool:
    return bool(data.get(CONF_CLOUD_HISTORY_ENABLED, False))


def _base_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_ADDRESS, default=defaults.get(CONF_ADDRESS, "")): str,
            vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Optional(CONF_MODEL, default=defaults.get(CONF_MODEL, DEFAULT_MODEL)): vol.In(model_options()),
            vol.Optional(
                CONF_REQUEST_INIT_ON_CONNECT,
                default=defaults.get(CONF_REQUEST_INIT_ON_CONNECT, True),
            ): bool,
            vol.Optional(
                CONF_TRANSPORT_MODE,
                default=defaults.get(CONF_TRANSPORT_MODE, TRANSPORT_MODE_AUTO),
            ): vol.In(TRANSPORT_MODES),
            vol.Optional(CONF_LAN_HOST, default=defaults.get(CONF_LAN_HOST, "")): str,
            vol.Optional(CONF_LAN_DEVICE_ID, default=defaults.get(CONF_LAN_DEVICE_ID, "")): str,
            vol.Optional(CONF_LAN_LOCAL_KEY, default=defaults.get(CONF_LAN_LOCAL_KEY, "")): str,
            vol.Optional(
                CONF_LAN_VERSION,
                default=defaults.get(CONF_LAN_VERSION, DEFAULT_LAN_VERSION),
            ): vol.All(vol.Coerce(float), vol.Range(min=3.1, max=3.5)),
            vol.Optional(
                CONF_LAN_PORT,
                default=defaults.get(CONF_LAN_PORT, DEFAULT_LAN_PORT),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Optional(
                CONF_LAN_POLL_SECONDS,
                default=defaults.get(CONF_LAN_POLL_SECONDS, DEFAULT_LAN_POLL_SECONDS),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600)),
            vol.Optional(CONF_LAN_TEST_ON_SETUP, default=False): bool,
        }
    )


def _advanced_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_MODEL,
                default=defaults.get(CONF_MODEL, DEFAULT_MODEL),
            ): vol.In(model_options()),
            vol.Optional(
                CONF_REQUEST_INIT_ON_CONNECT,
                default=defaults.get(CONF_REQUEST_INIT_ON_CONNECT, True),
            ): bool,
            vol.Optional(
                CONF_TRANSPORT_MODE,
                default=defaults.get(CONF_TRANSPORT_MODE, TRANSPORT_MODE_AUTO),
            ): vol.In(TRANSPORT_MODES),
            vol.Optional(CONF_LAN_HOST, default=defaults.get(CONF_LAN_HOST, "")): str,
            vol.Optional(CONF_LAN_DEVICE_ID, default=defaults.get(CONF_LAN_DEVICE_ID, "")): str,
            vol.Optional(CONF_LAN_LOCAL_KEY, default=defaults.get(CONF_LAN_LOCAL_KEY, "")): str,
            vol.Optional(
                CONF_LAN_VERSION,
                default=defaults.get(CONF_LAN_VERSION, DEFAULT_LAN_VERSION),
            ): vol.All(vol.Coerce(float), vol.Range(min=3.1, max=3.5)),
            vol.Optional(
                CONF_LAN_PORT,
                default=defaults.get(CONF_LAN_PORT, DEFAULT_LAN_PORT),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Optional(
                CONF_LAN_POLL_SECONDS,
                default=defaults.get(CONF_LAN_POLL_SECONDS, DEFAULT_LAN_POLL_SECONDS),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600)),
            vol.Optional(CONF_LAN_TEST_ON_SETUP, default=False): bool,
            vol.Optional(
                CONF_CLOUD_HISTORY_ENABLED,
                default=defaults.get(CONF_CLOUD_HISTORY_ENABLED, False),
            ): bool,
            vol.Optional(CONF_CLOUD_API_KEY, default=defaults.get(CONF_CLOUD_API_KEY, "")): str,
            vol.Optional(CONF_CLOUD_API_SECRET, default=defaults.get(CONF_CLOUD_API_SECRET, "")): str,
            vol.Optional(CONF_CLOUD_PRODUCT_ID, default=defaults.get(CONF_CLOUD_PRODUCT_ID, "")): str,
            vol.Optional(CONF_CLOUD_DEV_ID, default=defaults.get(CONF_CLOUD_DEV_ID, "")): str,
            vol.Optional(CONF_CLOUD_COUNTRY_CODE, default=defaults.get(CONF_CLOUD_COUNTRY_CODE, "")): str,
            vol.Optional(
                CONF_CLOUD_BASE_URL,
                default=defaults.get(CONF_CLOUD_BASE_URL, DEFAULT_CLOUD_BASE_URL),
            ): str,
            vol.Optional(
                CONF_CLOUD_POLL_SECONDS,
                default=defaults.get(CONF_CLOUD_POLL_SECONDS, DEFAULT_CLOUD_POLL_SECONDS),
            ): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
        }
    )


class InkbirdInt14ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return InkbirdInt14OptionsFlow(config_entry)

    async def _async_test_lan_config(self, user_input: dict[str, Any], errors: dict[str, str]) -> None:
        if not user_input.get(CONF_LAN_TEST_ON_SETUP):
            return
        lan_config = _lan_config_from_input(user_input)
        if lan_config is None or not lan_config.is_complete:
            errors["base"] = "lan_incomplete"
            return
        try:
            dps, summary = await self.hass.async_add_executor_job(fetch_lan_dps, lan_config)
        except Exception:  # noqa: BLE001 - keep setup errors privacy-safe
            errors["base"] = "lan_connect_failed"
            return
        if not dps and not summary.get("status_ok"):
            errors["base"] = "lan_connect_failed"

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_ADDRESS].upper())
            self._abort_if_unique_id_configured()
            await self._async_test_lan_config(user_input, errors)
            if not errors:
                data = {
                    CONF_ADDRESS: user_input[CONF_ADDRESS],
                    CONF_NAME: user_input.get(CONF_NAME) or DEFAULT_NAME,
                    CONF_MODEL: user_input.get(CONF_MODEL, DEFAULT_MODEL),
                    CONF_REQUEST_INIT_ON_CONNECT: user_input.get(CONF_REQUEST_INIT_ON_CONNECT, True),
                    CONF_TRANSPORT_MODE: user_input.get(CONF_TRANSPORT_MODE, TRANSPORT_MODE_AUTO),
                    CONF_LAN_HOST: _stripped(user_input, CONF_LAN_HOST),
                    CONF_LAN_DEVICE_ID: _stripped(user_input, CONF_LAN_DEVICE_ID),
                    CONF_LAN_LOCAL_KEY: _stripped(user_input, CONF_LAN_LOCAL_KEY),
                    CONF_LAN_VERSION: float(user_input.get(CONF_LAN_VERSION, DEFAULT_LAN_VERSION)),
                    CONF_LAN_PORT: int(user_input.get(CONF_LAN_PORT, DEFAULT_LAN_PORT)),
                    CONF_LAN_POLL_SECONDS: int(user_input.get(CONF_LAN_POLL_SECONDS, DEFAULT_LAN_POLL_SECONDS)),
                }
                return self.async_create_entry(title=data[CONF_NAME], data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=_base_schema(user_input or {}),
            errors=errors,
        )


class InkbirdInt14OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    def _defaults(self) -> dict[str, Any]:
        return {**self.config_entry.data, **self.config_entry.options}

    async def _async_test_lan_config(self, user_input: dict[str, Any], errors: dict[str, str]) -> None:
        if not user_input.get(CONF_LAN_TEST_ON_SETUP):
            return
        merged = {**self.config_entry.data, **self.config_entry.options, **user_input}
        lan_config = _lan_config_from_input(merged)
        if lan_config is None or not lan_config.is_complete:
            errors["base"] = "lan_incomplete"
            return
        try:
            dps, summary = await self.hass.async_add_executor_job(fetch_lan_dps, lan_config)
        except Exception:  # noqa: BLE001 - keep setup errors privacy-safe
            errors["base"] = "lan_connect_failed"
            return
        if not dps and not summary.get("status_ok"):
            errors["base"] = "lan_connect_failed"

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self._async_test_lan_config(user_input, errors)
            if not errors:
                data = dict(user_input)
                data.pop(CONF_LAN_TEST_ON_SETUP, None)
                if not _cloud_enabled(data):
                    for key in (
                        CONF_CLOUD_API_KEY,
                        CONF_CLOUD_API_SECRET,
                        CONF_CLOUD_PRODUCT_ID,
                        CONF_CLOUD_DEV_ID,
                        CONF_CLOUD_COUNTRY_CODE,
                    ):
                        data[key] = ""
                return self.async_create_entry(title="", data=data)

        return self.async_show_form(
            step_id="init",
            data_schema=_advanced_schema(user_input or self._defaults()),
            errors=errors,
        )
