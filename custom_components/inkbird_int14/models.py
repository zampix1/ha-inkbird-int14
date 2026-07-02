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

DEFAULT_MODEL = MODEL_INT14_BW
AUTH_MODE_BW = "bw_challenge"
AUTH_MODE_SCAN_ONLY = "scan_only"


@dataclass(frozen=True)
class InkbirdIntModelProfile:
    key: str
    display_name: str
    app_model: str
    product_id: str | None
    probe_count: int
    asset_family: str
    ble_auth_mode: str
    supports_ble_snapshot: bool
    supports_lan: bool
    supports_cloud_history: bool
    write_support: str
    support_status: str
    notes: str

    @property
    def is_tested(self) -> bool:
        return self.support_status == "tested"


MODEL_PROFILES: dict[str, InkbirdIntModelProfile] = {
    MODEL_INT14_BW: InkbirdIntModelProfile(
        key=MODEL_INT14_BW,
        display_name="Inkbird INT-14-BW",
        app_model="INT-14-BW",
        product_id="pcjgk9zfshrkeurk",
        probe_count=4,
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
        probe_count=4,
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
        probe_count=4,
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
        probe_count=4,
        asset_family="int14sbw",
        ble_auth_mode=AUTH_MODE_BW,
        supports_ble_snapshot=True,
        supports_lan=True,
        supports_cloud_history=True,
        write_support="experimental",
        support_status="experimental",
        notes="Same BLE service family; app uses a separate 14S data model.",
    ),
    MODEL_INT14P_BW: InkbirdIntModelProfile(
        key=MODEL_INT14P_BW,
        display_name="Inkbird INT-14P-BW",
        app_model="INT-14P-BW",
        product_id="sbe2z2w02vc8mecy",
        probe_count=4,
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
        probe_count=2,
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
        probe_count=2,
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
        probe_count=2,
        asset_family="int12ebw",
        ble_auth_mode=AUTH_MODE_BW,
        supports_ble_snapshot=True,
        supports_lan=True,
        supports_cloud_history=True,
        write_support="experimental",
        support_status="experimental",
        notes="App uses the modern FF00/FF02 BLE service family with smart-switch metadata.",
    ),
    MODEL_INT11I_B: InkbirdIntModelProfile(
        key=MODEL_INT11I_B,
        display_name="Inkbird INT-11I-B",
        app_model="INT-11I-B",
        product_id=None,
        probe_count=1,
        asset_family="int11ib",
        ble_auth_mode=AUTH_MODE_BW,
        supports_ble_snapshot=True,
        supports_lan=False,
        supports_cloud_history=False,
        write_support="experimental",
        support_status="experimental",
        notes="BLE config uses FF00/FF02 pairing; live payload coverage still needs hardware validation.",
    ),
    MODEL_INT11P_B: InkbirdIntModelProfile(
        key=MODEL_INT11P_B,
        display_name="Inkbird INT-11P-B",
        app_model="INT-11P-B",
        product_id=None,
        probe_count=1,
        asset_family="int11p",
        ble_auth_mode=AUTH_MODE_SCAN_ONLY,
        supports_ble_snapshot=False,
        supports_lan=False,
        supports_cloud_history=False,
        write_support="not_supported",
        support_status="cataloged",
        notes="The app pairs this model by scan/save; it is cataloged but not yet implemented for live reads here.",
    ),
}

SELECTABLE_MODEL_KEYS = tuple(MODEL_PROFILES)
MODEL_LABELS = {key: profile.display_name for key, profile in MODEL_PROFILES.items()}


def model_profile(model: str | None) -> InkbirdIntModelProfile:
    if not model:
        return MODEL_PROFILES[DEFAULT_MODEL]
    return MODEL_PROFILES.get(str(model), MODEL_PROFILES[DEFAULT_MODEL])


def model_options() -> dict[str, str]:
    return dict(MODEL_LABELS)
