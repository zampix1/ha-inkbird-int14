from __future__ import annotations

import json
import py_compile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_and_hacs_metadata() -> None:
    components = list((ROOT / "custom_components").iterdir())
    assert len(components) == 1
    component = components[0]
    manifest = json.loads((component / "manifest.json").read_text(encoding="utf-8"))
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert manifest["domain"] == component.name
    assert manifest["config_flow"] is True
    assert manifest["documentation"].startswith("https://github.com/zampix1/")
    assert manifest["issue_tracker"].startswith("https://github.com/zampix1/")
    assert "ha-inkbird-int14-local" not in manifest["documentation"]
    assert "ha-inkbird-int14-local" not in manifest["issue_tracker"]
    assert manifest["iot_class"] == "local_polling"
    assert manifest["iot_class"] in {"local_polling", "local_push", "cloud_polling", "cloud_push"}
    assert manifest["version"]
    assert hacs["name"]


def test_component_python_syntax() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for path in (ROOT / "custom_components").rglob("*.py"):
            py_compile.compile(str(path), cfile=str(tmp / f"{path.stem}.pyc"), doraise=True)


def test_no_private_artifact_directories() -> None:
    forbidden = {".storage", "secrets", "out", "backup", "backups", "node_modules"}
    present = {path.name for path in ROOT.rglob("*") if path.is_dir()}
    assert not (present & forbidden)


def test_required_public_files_exist() -> None:
    for name in ("README.md", "CHANGELOG.md", "LICENSE", "hacs.json", "SECURITY.md", "CONTRIBUTING.md", "RELEASE_AUDIT.md"):
        assert (ROOT / name).is_file(), name
    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / "model_validation_report.yml").is_file()
    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml").is_file()
    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml").is_file()
    assert (ROOT / ".github" / "DISCUSSION_TEMPLATE" / "q-a.yml").is_file()
    assert (ROOT / ".github" / "DISCUSSION_TEMPLATE" / "general.yml").is_file()
    component = next((ROOT / "custom_components").iterdir())
    assert (component / "diagnostics.py").is_file()
    assert (component / "translations" / "en.json").is_file()
    assert (component / "translations" / "it.json").is_file()


def test_no_private_research_terms_in_public_docs() -> None:
    forbidden_terms = (
        "ha-inkbird-int14-local",
        "fri" + "da",
        "side" + "car",
        "emu" + "lator",
        "decom" + "piled",
    )
    for path in ROOT.rglob("*"):
        if "tests" in path.relative_to(ROOT).parts:
            continue
        if not path.is_file() or path.suffix.lower() in {".png", ".pyc"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for term in forbidden_terms:
            assert term not in text, f"{term} found in {path.relative_to(ROOT)}"


def test_passive_and_authenticated_ble_diagnostics_remain_separate() -> None:
    runtime = (ROOT / "custom_components" / "inkbird_int14" / "runtime.py").read_text(encoding="utf-8")
    passive_wrapper = runtime.split("    async def request_ble_diagnostics", 1)[1].split(
        "    async def request_authenticated_ble_diagnostics", 1
    )[0]
    authenticated_block = runtime.split("    async def request_authenticated_ble_diagnostics", 1)[1].split(
        "    async def _request_init_on_client", 1
    )[0]
    assert "authenticated=False" in passive_wrapper
    assert "write_gatt_char" not in passive_wrapper
    assert "authenticated=True" in authenticated_block
    assert "AUTH_CHALLENGE_REQUEST" in authenticated_block
    assert "diagnostic_snapshot_query_chunks" in authenticated_block
    assert "init_command_chunks" not in authenticated_block
    for forbidden_builder in (
        "build_calibration_command",
        "build_display_light_command",
        "build_pre_alarm_command",
        "build_target_command",
        "build_timer_command",
        "build_timer_reset_command",
        "build_unit_command",
    ):
        assert forbidden_builder not in authenticated_block
