from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "inkbird_int14"


def _load_const_module():
    path = COMPONENT / "const.py"
    spec = importlib.util.spec_from_file_location("inkbird_int14_const_privacy_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _literal_redaction_keys() -> set[str]:
    tree = ast.parse((COMPONENT / "diagnostics.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "TO_REDACT" for target in node.targets):
            value = ast.literal_eval(node.value)
            assert isinstance(value, set)
            return value
    raise AssertionError("TO_REDACT was not found")


def test_diagnostics_redact_actual_tuya_lan_storage_keys() -> None:
    const = _load_const_module()
    redaction_keys = _literal_redaction_keys()

    assert const.CONF_LAN_HOST in redaction_keys
    assert const.CONF_LAN_DEVICE_ID in redaction_keys
    assert const.CONF_LAN_LOCAL_KEY in redaction_keys


def test_diagnostics_do_not_export_runtime_address_as_plain_string() -> None:
    source = (COMPONENT / "diagnostics.py").read_text(encoding="utf-8")

    assert 'for attr in ("address", "session", "device", "config")' not in source
    assert 'payload["address"]' not in source
