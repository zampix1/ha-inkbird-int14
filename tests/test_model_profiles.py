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
    assert profile.physical_probe_count == 4
    assert profile.temperature_channel_count == 8
    assert profile.live_temperature_channel_count == 8
    assert profile.support_status == "tested"
    assert profile.supports_ble_snapshot is True
    assert profile.supports_lan is True
    assert [channel.key for channel in profile.probe_layout[0].channels] == ["food", "ambient"]
    assert [channel.data_key for channel in profile.probe_layout[0].live_temperature_channels] == ["internal", "ambient"]


def test_probe_counts_match_profile_family() -> None:
    models = _load_models_module()
    assert models.model_profile("int14_bw").probe_count == 4
    assert models.model_profile("int12_bw").probe_count == 2
    assert models.model_profile("int12e_bw").probe_count == 2
    assert models.model_profile("int11i_b").probe_count == 1
    assert models.model_profile("int11i_b").temperature_channel_count == 1
    assert models.model_profile("int11i_b").live_temperature_channel_count == 1
    assert models.model_profile("int11p_b").supports_ble_snapshot is False
    assert models.model_profile("int11s_b").probe_count == 1
    assert models.model_profile("int31_bw").probe_count == 1
    assert models.model_profile("int33_bw").probe_count == 3


def test_modern_multi_sensor_layouts_match_app_model_family() -> None:
    models = _load_models_module()
    cases = {
        "int31_bw": (1, 5, 0),
        "int14s_bw": (4, 20, 20),
        "int12e_bw": (2, 10, 0),
        "int33_bw": (3, 13, 0),
        "int11s_b": (1, 5, 0),
        "int14_bw": (4, 8, 8),
    }
    for profile_key, (physical_probes, expected_channels, mapped_channels) in cases.items():
        profile = models.model_profile(profile_key)
        assert profile.physical_probe_count == physical_probes
        assert profile.temperature_channel_count == expected_channels
        assert profile.live_temperature_channel_count == mapped_channels


def test_cataloged_profiles_do_not_expose_live_channels() -> None:
    models = _load_models_module()
    for profile_key in ("int12e_bw", "int11s_b", "int31_bw", "int33_bw"):
        profile = models.model_profile(profile_key)
        assert profile.support_status == "cataloged"
        assert profile.has_live_runtime_data is False
        assert profile.live_temperature_channel_count == 0
        assert all(channel.parser_key is None for probe_layout in profile.probe_layout for channel in probe_layout.channels)


def test_int33_expected_layout_has_two_long_probes_and_one_mini_probe() -> None:
    models = _load_models_module()
    profile = models.model_profile("int33_bw")
    assert [probe.temperature_channel_count for probe in profile.probe_layout] == [5, 5, 3]
    assert "Probe 3 mini" in profile.probe_layout_summary


def test_transport_capabilities_are_not_overstated() -> None:
    models = _load_models_module()
    assert models.model_profile("int14_bw").supports_lan is True
    assert models.model_profile("int14_bw").supports_cloud_history is True
    assert models.model_profile("int11i_b").supports_lan is False
    assert models.model_profile("int11i_b").supports_cloud_history is False
    assert models.model_profile("int11i_b").supports_ble_snapshot is True
    assert models.model_profile("int11i_b").write_support == "not_supported"
    assert models.model_profile("int11i_b").supports_base_temperature is False
    assert models.model_profile("int11p_b").write_support == "not_supported"
    for profile_key in ("int12e_bw", "int11s_b", "int31_bw", "int33_bw"):
        profile = models.model_profile(profile_key)
        assert profile.support_status == "cataloged"
        assert profile.supports_ble_snapshot is False
        assert profile.supports_lan is False
        assert profile.supports_cloud_history is False
        assert profile.write_support == "not_supported"
        assert profile.supports_ble_diagnostics is True

    assert models.model_profile("int14s_bw").supports_authenticated_ble_diagnostics is True
    assert models.model_profile("int12e_bw").supports_authenticated_ble_diagnostics is False
    assert models.model_profile("int31_bw").supports_authenticated_ble_diagnostics is False


def test_int14s_ble_read_path_is_experimental_and_write_blocked() -> None:
    models = _load_models_module()
    profile = models.model_profile("int14s_bw")

    assert profile.support_status == "experimental"
    assert profile.supports_ble_diagnostics is True
    assert profile.supports_authenticated_ble_diagnostics is True
    assert profile.supports_ble_snapshot is True
    assert profile.has_live_runtime_data is True
    assert profile.live_temperature_channel_count == 20
    assert profile.write_support == "not_supported"
    assert profile.supports_lan is False
    assert profile.supports_cloud_history is False
    assert profile.supports_protocol_state is False
    assert [channel.data_key for channel in profile.probe_layout[0].live_temperature_channels] == [
        "food_1",
        "food_2",
        "food_3",
        "food_4",
        "ambient",
    ]


def test_cataloged_ble_diagnostics_do_not_enable_live_support() -> None:
    models = _load_models_module()
    profile = models.model_profile("int12e_bw")

    assert profile.supports_ble_diagnostics is True
    assert profile.supports_ble_snapshot is False
    assert profile.has_live_runtime_data is False
    assert profile.live_temperature_channel_count == 0
    assert profile.write_support == "not_supported"
