"""Build the optional, deterministic Cook Control bundle, not an integration release."""

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parent
FILES = {
    "packages/inkbird_bbq.yaml": "packages/inkbird_bbq.yaml",
    "www/inkbird-int/cook-base-v1.4.3.js": "www/inkbird-int/cook-base-v1.4.3.js",
    "www/inkbird-int/inkbird-int-cook-model.mjs": "www/inkbird-int/inkbird-int-cook-model.mjs",
    "www/inkbird-int/inkbird-int-cook-control.js": "www/inkbird-int/inkbird-int-cook-control.js",
    "www/inkbird-int/inkbird-cook-panel.js": "www/inkbird-int/inkbird-cook-panel.js",
    "www/inkbird-int/inkbird-cook-session.mjs": "www/inkbird-int/inkbird-cook-session.mjs",
    "custom_components/inkbird_cook_control/__init__.py": "custom_components/inkbird_cook_control/__init__.py",
    "custom_components/inkbird_cook_control/engine.py": "custom_components/inkbird_cook_control/engine.py",
    "custom_components/inkbird_cook_control/manifest.json": "custom_components/inkbird_cook_control/manifest.json",
    "dashboard.yaml": "cook-control/dashboard.yaml",
    "README.md": "cook-control/README.md",
    "README.it.md": "cook-control/README.it.md",
    "VALIDATION.md": "cook-control/VALIDATION.md",
    "THIRD_PARTY_NOTICES.md": "cook-control/THIRD_PARTY_NOTICES.md",
    "LICENSE.remb0": "cook-control/LICENSE.remb0",
    "LICENSE.boris": "cook-control/LICENSE.boris",
}


def build(output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for source, destination in sorted(FILES.items()):
            info = ZipInfo(destination, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (ROOT / source).read_bytes())
        info = ZipInfo("cook-control/LICENSE.integration", date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        archive.writestr(info, (ROOT.parents[1] / "LICENSE").read_bytes())
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(build(parser.parse_args().output))
