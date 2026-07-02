from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_models_module():
    path = ROOT / "custom_components" / "inkbird_int14" / "models.py"
    spec = importlib.util.spec_from_file_location("inkbird_int14_models", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_model_profiles_cover_target_modern_family() -> None:
    models = _load_models_module()
    expected = {
        "int14_bw",
        "int14_bw_wh",
        "ing14",
        "int14s_bw",
        "int14p_bw",
        "int12_bw",
        "int12i_bw",
        "int12e_bw",
        "int11i_b",
        "int11p_b",
        "int11s_b",
        "int31_bw",
        "int33_bw",
    }
    assert expected <= set(models.MODEL_PROFILES)


def test_default_model_is_tested_int14() -> None:
    models = _load_models_module()
    profile = models.model_profile(None)
    assert profile.key == "int14_bw"
    assert profile.probe_count == 4
    assert profile.support_status == "tested"
    assert profile.supports_ble_snapshot is True
    assert profile.supports_lan is True


def test_probe_counts_match_profile_family() -> None:
    models = _load_models_module()
    assert models.model_profile("int14_bw").probe_count == 4
    assert models.model_profile("int12_bw").probe_count == 2
    assert models.model_profile("int12e_bw").probe_count == 2
    assert models.model_profile("int11i_b").probe_count == 1
    assert models.model_profile("int11p_b").supports_ble_snapshot is False
    assert models.model_profile("int11s_b").probe_count == 1
    assert models.model_profile("int31_bw").probe_count == 1
    assert models.model_profile("int33_bw").probe_count == 3


def test_transport_capabilities_are_not_overstated() -> None:
    models = _load_models_module()
    assert models.model_profile("int14_bw").supports_lan is True
    assert models.model_profile("int14_bw").supports_cloud_history is True
    assert models.model_profile("int11i_b").supports_lan is False
    assert models.model_profile("int11i_b").supports_cloud_history is False
    assert models.model_profile("int11p_b").write_support == "not_supported"
    for profile_key in ("int11s_b", "int31_bw", "int33_bw"):
        profile = models.model_profile(profile_key)
        assert profile.support_status == "cataloged"
        assert profile.supports_ble_snapshot is False
        assert profile.supports_lan is False
        assert profile.supports_cloud_history is False
        assert profile.write_support == "not_supported"
