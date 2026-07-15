from __future__ import annotations

from dataclasses import dataclass

MODEL_INT14_BW = "int14_bw"
MODEL_INT14_BW_WH = "int14_bw_wh"
MODEL_ING14 = "ing14"
MODEL_INT14S_BW = "int14s_bw"
MODEL_INT14P_BW = "int14p_bw"
MODEL_INT12_BW = "int12_bw"
MODEL_INT12I_BW = "int12i_bw"
MODEL_INT12E_BW = "int12e_bw"
MODEL_INT11I_B = "int11i_b"
MODEL_INT11P_B = "int11p_b"
MODEL_INT11S_B = "int11s_b"
MODEL_INT31_BW = "int31_bw"
MODEL_INT33_BW = "int33_bw"

DEFAULT_MODEL = MODEL_INT14_BW
AUTH_MODE_BW = "bw_challenge"
AUTH_MODE_GATT_POLL = "gatt_poll"
AUTH_MODE_SCAN_ONLY = "scan_only"


@dataclass(frozen=True)
class TemperatureChannel:
    key: str
    display_name: str
    parser_key: str | None = None
    entity_key: str | None = None
    entity_name: str | None = None

    @property
    def is_live_mapped(self) -> bool:
        return self.parser_key is not None

    @property
    def data_key(self) -> str:
        return self.parser_key or self.key

    @property
    def live_entity_key(self) -> str:
        return self.entity_key or self.data_key

    @property
    def live_entity_name(self) -> str:
        return self.entity_name or self.display_name


@dataclass(frozen=True)
class ProbeLayout:
    index: int
    channels: tuple[TemperatureChannel, ...]
    label: str | None = None

    @property
    def temperature_channel_count(self) -> int:
        return len(self.channels)

    @property
    def live_temperature_channels(self) -> tuple[TemperatureChannel, ...]:
        return tuple(channel for channel in self.channels if channel.is_live_mapped)

    @property
    def summary(self) -> str:
        label = self.label or f"Probe {self.index}"
        return f"{label}: " + ", ".join(channel.key for channel in self.channels)


@dataclass(frozen=True)
class InkbirdIntModelProfile:
    key: str
    display_name: str
    app_model: str
    product_id: str | None
    probe_layout: tuple[ProbeLayout, ...]
    asset_family: str
    ble_auth_mode: str
    supports_ble_snapshot: bool
    supports_lan: bool
    supports_cloud_history: bool
    write_support: str
    support_status: str
    notes: str
    supports_base_temperature: bool = True
    allows_authenticated_ble_diagnostics: bool = False

    @property
    def is_tested(self) -> bool:
        return self.support_status == "tested"

    @property
    def probe_count(self) -> int:
        return len(self.probe_layout)

    @property
    def physical_probe_count(self) -> int:
        return self.probe_count

    @property
    def temperature_channel_count(self) -> int:
        return sum(probe.temperature_channel_count for probe in self.probe_layout)

    @property
    def live_temperature_channel_count(self) -> int:
        return sum(len(probe.live_temperature_channels) for probe in self.probe_layout)

    @property
    def has_live_runtime_data(self) -> bool:
        return self.supports_ble_snapshot or self.supports_lan or self.supports_cloud_history

    @property
    def supports_ble_diagnostics(self) -> bool:
        """Allow non-live GATT inspection without claiming model support."""
        return self.support_status == "cataloged" or self.allows_authenticated_ble_diagnostics

    @property
    def supports_authenticated_ble_diagnostics(self) -> bool:
        """Allow an explicitly reviewed BW session/snapshot diagnostic."""
        return self.ble_auth_mode == AUTH_MODE_BW and self.allows_authenticated_ble_diagnostics

    @property
    def probe_layout_summary(self) -> str:
        return "; ".join(probe.summary for probe in self.probe_layout)


CHANNEL_FOOD_MAPPED = TemperatureChannel(
    key="food",
    display_name="Food",
    parser_key="internal",
    entity_key="internal",
    entity_name="Internal",
)
CHANNEL_AMBIENT_MAPPED = TemperatureChannel(
    key="ambient",
    display_name="Ambient",
    parser_key="ambient",
    entity_key="ambient",
    entity_name="Ambient",
)
CHANNEL_AMBIENT_EXPECTED = TemperatureChannel("ambient", "Ambient")


def _two_channel_layout(probe_count: int) -> tuple[ProbeLayout, ...]:
    channels = (CHANNEL_FOOD_MAPPED, CHANNEL_AMBIENT_MAPPED)
    return tuple(ProbeLayout(index=index, channels=channels) for index in range(1, probe_count + 1))


def _single_food_layout(probe_count: int) -> tuple[ProbeLayout, ...]:
    return tuple(ProbeLayout(index=index, channels=(CHANNEL_FOOD_MAPPED,)) for index in range(1, probe_count + 1))


def _expected_multi_sensor_probe(sensor_count: int) -> tuple[TemperatureChannel, ...]:
    return tuple(TemperatureChannel(f"food_{index}", f"Food {index}") for index in range(1, sensor_count + 1)) + (CHANNEL_AMBIENT_EXPECTED,)


def _mapped_multi_sensor_probe(sensor_count: int) -> tuple[TemperatureChannel, ...]:
    return tuple(
        TemperatureChannel(f"food_{index}", f"Food {index}", parser_key=f"food_{index}") for index in range(1, sensor_count + 1)
    ) + (CHANNEL_AMBIENT_MAPPED,)


def _expected_multi_sensor_layout(probe_count: int, sensor_count: int = 4) -> tuple[ProbeLayout, ...]:
    channels = _expected_multi_sensor_probe(sensor_count)
    return tuple(ProbeLayout(index=index, channels=channels) for index in range(1, probe_count + 1))


def _expected_int33_layout() -> tuple[ProbeLayout, ...]:
    long_probe_channels = _expected_multi_sensor_probe(4)
    mini_probe_channels = tuple(TemperatureChannel(f"food_{index}", f"Food {index}") for index in range(1, 4))
    return (
        ProbeLayout(index=1, label="Probe 1 long", channels=long_probe_channels),
        ProbeLayout(index=2, label="Probe 2 long", channels=long_probe_channels),
        ProbeLayout(index=3, label="Probe 3 mini", channels=mini_probe_channels),
    )


MODEL_PROFILES: dict[str, InkbirdIntModelProfile] = {
    MODEL_INT14_BW: InkbirdIntModelProfile(
        key=MODEL_INT14_BW,
        display_name="Inkbird INT-14-BW",
        app_model="INT-14-BW",
        product_id="pcjgk9zfshrkeurk",
        probe_layout=_two_channel_layout(4),
        asset_family="int14bw",
        ble_auth_mode=AUTH_MODE_BW,
        supports_ble_snapshot=True,
        supports_lan=True,
        supports_cloud_history=True,
        write_support="tested",
        support_status="tested",
        notes="Validated with live BLE and Tuya LAN captures.",
    ),
    MODEL_INT14_BW_WH: InkbirdIntModelProfile(
        key=MODEL_INT14_BW_WH,
        display_name="Inkbird INT-14-BW WH",
        app_model="INT-14-BW_WH",
        product_id="f9tfzbf2i1fzlv6q",
        probe_layout=_two_channel_layout(4),
        asset_family="int14bw_wh",
        ble_auth_mode=AUTH_MODE_BW,
        supports_ble_snapshot=True,
        supports_lan=True,
        supports_cloud_history=True,
        write_support="experimental",
        support_status="experimental",
        notes="App routes this white variant through the INT-14 family.",
    ),
    MODEL_ING14: InkbirdIntModelProfile(
        key=MODEL_ING14,
        display_name="Inkbird ING14",
        app_model="ING14",
        product_id="k6zw0f6t5tt9mmpy",
        probe_layout=_two_channel_layout(4),
        asset_family="ing14",
        ble_auth_mode=AUTH_MODE_BW,
        supports_ble_snapshot=True,
        supports_lan=True,
        supports_cloud_history=True,
        write_support="experimental",
        support_status="experimental",
        notes="App routes this grilling variant through the INT-14 family.",
    ),
    MODEL_INT14S_BW: InkbirdIntModelProfile(
        key=MODEL_INT14S_BW,
        display_name="Inkbird INT-14S-BW",
        app_model="INT-14S-BW",
        product_id="bozmpl04yva3x0sa",
        probe_layout=tuple(ProbeLayout(index=index, channels=_mapped_multi_sensor_probe(4)) for index in range(1, 5)),
        asset_family="int14sbw",
        ble_auth_mode=AUTH_MODE_BW,
        supports_ble_snapshot=True,
        supports_lan=False,
        supports_cloud_history=False,
        write_support="not_supported",
        support_status="experimental",
        notes="Community-validated read-only BLE parser for four food sensors plus ambient per probe; LAN, cloud and writes remain disabled.",
        allows_authenticated_ble_diagnostics=True,
    ),
    MODEL_INT14P_BW: InkbirdIntModelProfile(
        key=MODEL_INT14P_BW,
        display_name="Inkbird INT-14P-BW",
        app_model="INT-14P-BW",
        product_id="sbe2z2w02vc8mecy",
        probe_layout=_two_channel_layout(4),
        asset_family="int14p",
        ble_auth_mode=AUTH_MODE_BW,
        supports_ble_snapshot=True,
        supports_lan=True,
        supports_cloud_history=True,
        write_support="experimental",
        support_status="experimental",
        notes="Same BLE service family; app uses smart-switch metadata.",
    ),
    MODEL_INT12_BW: InkbirdIntModelProfile(
        key=MODEL_INT12_BW,
        display_name="Inkbird INT-12-BW",
        app_model="INT-12-BW",
        product_id="lkrzzdaex96sysha",
        probe_layout=_two_channel_layout(2),
        asset_family="int12bw",
        ble_auth_mode=AUTH_MODE_BW,
        supports_ble_snapshot=True,
        supports_lan=True,
        supports_cloud_history=True,
        write_support="experimental",
        support_status="experimental",
        notes="App uses the same FF00/FF02 BLE service family with two probes.",
    ),
    MODEL_INT12I_BW: InkbirdIntModelProfile(
        key=MODEL_INT12I_BW,
        display_name="Inkbird INT-12I-BW",
        app_model="INT-12I-BW",
        product_id="adtpe6mnmsp2loqc",
        probe_layout=_two_channel_layout(2),
        asset_family="int12ibw",
        ble_auth_mode=AUTH_MODE_BW,
        supports_ble_snapshot=True,
        supports_lan=True,
        supports_cloud_history=True,
        write_support="experimental",
        support_status="experimental",
        notes="App routes this insulated-probe variant through the INT-12 family.",
    ),
    MODEL_INT12E_BW: InkbirdIntModelProfile(
        key=MODEL_INT12E_BW,
        display_name="Inkbird INT-12E-BW",
        app_model="INT-12E-BW",
        product_id="xg7axqye8z3jpzi0",
        probe_layout=_expected_multi_sensor_layout(2),
        asset_family="int12ebw",
        ble_auth_mode=AUTH_MODE_BW,
        supports_ble_snapshot=False,
        supports_lan=False,
        supports_cloud_history=False,
        write_support="not_supported",
        support_status="cataloged",
        notes="Expected two physical probes with four food sensors plus ambient per probe; live frame and DP maps are not implemented here yet.",
    ),
    MODEL_INT11I_B: InkbirdIntModelProfile(
        key=MODEL_INT11I_B,
        display_name="Inkbird INT-11I-B",
        app_model="INT-11I-B",
        product_id=None,
        probe_layout=_single_food_layout(1),
        asset_family="int11ib",
        ble_auth_mode=AUTH_MODE_GATT_POLL,
        supports_ble_snapshot=True,
        supports_lan=False,
        supports_cloud_history=False,
        write_support="not_supported",
        support_status="experimental",
        notes="Community report validates connectable GATT reads: FF01 two-byte temperature and 2A19 two-byte base/probe battery. Writes are not enabled.",
        supports_base_temperature=False,
    ),
    MODEL_INT11P_B: InkbirdIntModelProfile(
        key=MODEL_INT11P_B,
        display_name="Inkbird INT-11P-B",
        app_model="INT-11P-B",
        product_id=None,
        probe_layout=_expected_multi_sensor_layout(1, sensor_count=1),
        asset_family="int11p",
        ble_auth_mode=AUTH_MODE_SCAN_ONLY,
        supports_ble_snapshot=False,
        supports_lan=False,
        supports_cloud_history=False,
        write_support="not_supported",
        support_status="cataloged",
        notes="The app pairs this model by scan/save; it is cataloged but not yet implemented for live reads here.",
    ),
    MODEL_INT11S_B: InkbirdIntModelProfile(
        key=MODEL_INT11S_B,
        display_name="Inkbird INT-11S-B",
        app_model="INT-11S-B",
        product_id=None,
        probe_layout=_expected_multi_sensor_layout(1),
        asset_family="int11sb",
        ble_auth_mode=AUTH_MODE_SCAN_ONLY,
        supports_ble_snapshot=False,
        supports_lan=False,
        supports_cloud_history=False,
        write_support="not_supported",
        support_status="cataloged",
        notes="Expected one physical probe with four food sensors plus ambient; live frame and DP maps are not implemented here yet.",
    ),
    MODEL_INT31_BW: InkbirdIntModelProfile(
        key=MODEL_INT31_BW,
        display_name="Inkbird INT-31-BW",
        app_model="INT-31-BW",
        product_id="xszt4p66qhevkvy2",
        probe_layout=_expected_multi_sensor_layout(1),
        asset_family="int31bw",
        ble_auth_mode=AUTH_MODE_SCAN_ONLY,
        supports_ble_snapshot=False,
        supports_lan=False,
        supports_cloud_history=False,
        write_support="not_supported",
        support_status="cataloged",
        notes="Wi-Fi/BLE one-probe family expected to expose four food sensors plus ambient; live frame and DP maps are not implemented here yet.",
    ),
    MODEL_INT33_BW: InkbirdIntModelProfile(
        key=MODEL_INT33_BW,
        display_name="Inkbird INT-33-BW",
        app_model="INT-33-BW",
        product_id="zvjymfsg50n92qr5",
        probe_layout=_expected_int33_layout(),
        asset_family="int33bw",
        ble_auth_mode=AUTH_MODE_SCAN_ONLY,
        supports_ble_snapshot=False,
        supports_lan=False,
        supports_cloud_history=False,
        write_support="not_supported",
        support_status="cataloged",
        notes="Wi-Fi/BLE three-probe family expected to expose two long probes and one mini probe; live frame and DP maps are not implemented here yet.",
    ),
}

SELECTABLE_MODEL_KEYS = tuple(MODEL_PROFILES)
MODEL_LABELS = {
    key: f"{profile.display_name} ({profile.physical_probe_count} probes / {profile.temperature_channel_count} temp channels)"
    for key, profile in MODEL_PROFILES.items()
}


def model_profile(model: str | None) -> InkbirdIntModelProfile:
    if not model:
        return MODEL_PROFILES[DEFAULT_MODEL]
    return MODEL_PROFILES.get(str(model), MODEL_PROFILES[DEFAULT_MODEL])


def model_options() -> dict[str, str]:
    return dict(MODEL_LABELS)
