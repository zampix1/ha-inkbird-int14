from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_models_and_cleanup():
    component = ROOT / "custom_components" / "inkbird_int14"
    models = _load_module("inkbird_int14_models_cleanup_test", component / "models.py")
    cleanup = _load_module("inkbird_int14_entity_cleanup_test", component / "entity_cleanup.py")
    return models, cleanup


def test_int14s_cleanup_removes_only_incompatible_profile_entities() -> None:
    models, cleanup = _load_models_and_cleanup()
    profile = models.model_profile("int14s_bw")
    address = "AA:BB:CC:DD:EE:FF"

    obsolete = cleanup.obsolete_profile_unique_ids(address, profile)

    assert f"{address}_probe_1_internal_temp" in obsolete
    assert f"{address}_probe_1_target_high_command" in obsolete
    assert f"{address}_probe_1_internal_calibration_command" in obsolete
    assert f"{address}_probe_1_charging" in obsolete
    assert f"{address}_base_charging" in obsolete

    assert f"{address}_probe_1_food_1_temp" not in obsolete
    assert f"{address}_probe_1_food_4_temp" not in obsolete
    assert f"{address}_probe_1_ambient_temp" not in obsolete
    assert f"{address}_probe_1_battery" not in obsolete
    assert f"{address}_base_temp" not in obsolete
    assert f"{address}_transport_mode" not in obsolete
    assert f"{address}_capture_read_only_lan_diagnostics" not in obsolete


def test_cataloged_profile_cleanup_removes_old_live_entities_and_writes() -> None:
    models, cleanup = _load_models_and_cleanup()
    profile = models.model_profile("int31_bw")
    address = "AA:BB:CC:DD:EE:FF"

    obsolete = cleanup.obsolete_profile_unique_ids(address, profile)

    assert f"{address}_probe_1_internal_temp" in obsolete
    assert f"{address}_probe_1_food_1_temp" in obsolete
    assert f"{address}_probe_1_battery" in obsolete
    assert f"{address}_base_temp" in obsolete
    assert f"{address}_base_battery" in obsolete
    assert f"{address}_display_light_command" in obsolete
    assert f"{address}_request_snapshot" in obsolete

    assert f"{address}_transport_mode" not in obsolete
    assert f"{address}_capture_ble_diagnostics" not in obsolete
    assert f"{address}_ble_enabled" not in obsolete


def test_tested_int14_profile_keeps_existing_baseline_ids() -> None:
    models, cleanup = _load_models_and_cleanup()
    profile = models.model_profile("int14_bw")
    address = "AA:BB:CC:DD:EE:FF"

    obsolete = cleanup.obsolete_profile_unique_ids(address, profile)

    for probe in range(1, 5):
        assert f"{address}_probe_{probe}_internal_temp" not in obsolete
        assert f"{address}_probe_{probe}_ambient_temp" not in obsolete
        assert f"{address}_probe_{probe}_target_high_command" not in obsolete
        assert f"{address}_probe_{probe}_charging" not in obsolete
    assert f"{address}_display_light_command" not in obsolete
    assert f"{address}_base_charging" not in obsolete


def test_profile_cleanup_runs_before_platform_setup() -> None:
    init_source = (ROOT / "custom_components" / "inkbird_int14" / "__init__.py").read_text(encoding="utf-8")
    setup_block = init_source.split("async def async_setup_entry", 1)[1].split("async def async_unload_entry", 1)[0]

    assert "obsolete_profile_unique_ids" in setup_block
    assert setup_block.index("registry.async_remove") < setup_block.index("async_forward_entry_setups")


def test_int12_cleanup_removes_only_the_unmapped_probe2_ambient_temperature() -> None:
    models, cleanup = _load_models_and_cleanup()
    obsolete = cleanup.obsolete_profile_unique_ids("REDACTED", models.model_profile("int12_bw"))
    assert "REDACTED_probe_2_ambient_temp" in obsolete
    for key in ("probe_1_internal_temp", "probe_1_ambient_temp", "probe_2_internal_temp", "base_temp", "base_battery", "probe_2_battery"):
        assert f"REDACTED_{key}" not in obsolete
