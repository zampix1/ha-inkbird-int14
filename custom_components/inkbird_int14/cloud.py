from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CloudHistoryConfig:
    api_key: str
    api_secret: str
    product_id: str
    dev_id: str
    country_code: str
    base_url: str
    poll_seconds: int

    @property
    def is_complete(self) -> bool:
        return all(
            str(value).strip()
            for value in (
                self.api_key,
                self.api_secret,
                self.product_id,
                self.dev_id,
                self.country_code,
                self.base_url,
            )
        )


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return bool(value)


def build_cloud_history_config_from_sources(
    *,
    entry_data: dict[str, Any],
    entry_options: dict[str, Any],
    default_base_url: str,
    default_poll_seconds: int,
) -> CloudHistoryConfig | None:
    enabled = _as_bool(entry_options.get("cloud_history_enabled")) or _as_bool(entry_data.get("cloud_history_enabled"))
    if not enabled:
        return None

    def value(config_key: str, *, default: Any = "") -> Any:
        option_value = entry_options.get(config_key)
        if option_value not in (None, ""):
            return option_value
        data_value = entry_data.get(config_key)
        if data_value not in (None, ""):
            return data_value
        return default

    return CloudHistoryConfig(
        api_key=str(value("cloud_api_key")),
        api_secret=str(value("cloud_api_secret")),
        product_id=str(value("cloud_product_id")),
        dev_id=str(value("cloud_dev_id")),
        country_code=str(value("cloud_country_code")),
        base_url=str(value("cloud_base_url", default=default_base_url)),
        poll_seconds=int(value("cloud_poll_seconds", default=default_poll_seconds)),
    )


def build_history_body(
    *,
    product_id: str,
    dev_id: str,
    dp_id: str,
    dateline_begin: int,
    dateline_end: int,
    time_interval: int,
    country_code: str,
) -> dict[str, Any]:
    return {
        "product_id": product_id,
        "dev_id": dev_id,
        "dp_id": dp_id,
        "dateline_begin": dateline_begin,
        "dateline_end": dateline_end,
        "time_interval": time_interval,
        "delete_type": 0,
        "distinct_type": False,
        "dateline_type": False,
        "country_code": country_code,
    }


def normalize_history_list(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, dict):
        rows = response.get("list")
        if isinstance(rows, list):
            return [item for item in rows if isinstance(item, dict)]
        data = response.get("data")
        if isinstance(data, dict) and isinstance(data.get("list"), list):
            return [item for item in data["list"] if isinstance(item, dict)]
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    return []


def latest_history_row(response: Any) -> dict[str, Any] | None:
    rows = normalize_history_list(response)
    if not rows:
        return None

    def key(row: dict[str, Any]) -> int:
        try:
            return int(row.get("dateline", 0))
        except (TypeError, ValueError):
            return 0

    return max(rows, key=key)


def history_response_to_cloud_dps(response: Any) -> tuple[dict[str, str], dict[str, Any]]:
    row = latest_history_row(response)
    if row is None:
        return {}, {"reason": "no_history_rows", "history_count": 0}
    dp_value = row.get("dp_value")
    if not isinstance(dp_value, str) or not dp_value:
        return {}, {
            "reason": "latest_row_without_dp_value",
            "history_count": len(normalize_history_list(response)),
            "dateline": row.get("dateline"),
        }
    raw = base64.b64decode(dp_value)
    dp_id = str(row.get("dp_id") or "109")
    return {dp_id: raw.hex()}, {
        "history_count": len(normalize_history_list(response)),
        "dateline": row.get("dateline"),
        "dp_id": dp_id,
        "raw_len": len(raw),
        "dps_keys": [dp_id],
    }


async def fetch_history_dps(session: Any, config: CloudHistoryConfig) -> tuple[dict[str, str], dict[str, Any]]:
    now_ms = int(time.time() * 1000)
    body = build_history_body(
        product_id=config.product_id,
        dev_id=config.dev_id,
        dp_id="109",
        dateline_begin=now_ms - 24 * 60 * 60 * 1000,
        dateline_end=now_ms,
        time_interval=60,
        country_code=config.country_code,
    )
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "API-KEY": config.api_key,
        "API-SECRET-KEY": config.api_secret,
        "User-Agent": "okhttp/4.12.0",
    }
    url = f"{config.base_url.rstrip('/')}/smartAgent/history/get"
    async with session.post(url, json=body, headers=headers, timeout=20) as response:
        payload = await response.json(content_type=None)
        dps, summary = history_response_to_cloud_dps(payload)
        summary["status"] = response.status
        return dps, summary
