# Release Audit

## Repository Candidate

- Intended repository: `ha-inkbird-int14`
- Domain: `inkbird_int14`
- Publication status: public repository prepared.
- Current recommendation: publishable as a public test release candidate, not yet recommended as a mature HACS default until broader hardware validation is complete.

## Public Positioning

Home Assistant custom integration for the modern Inkbird INT food thermometer family. INT-14-BW is the tested baseline; related INT-14, INT-12, INT-31, INT-33 and selected INT-11 profiles are exposed as experimental or cataloged until validated by real hardware reports.

This is a hybrid/local-first integration, not a cloud-control integration.

## Included Files

- Root metadata: `README.md`, `hacs.json`, `LICENSE`, `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md`.
- Workflows: `.github/workflows/validate.yml`, `.github/workflows/hassfest.yml`, `.github/workflows/tests.yml`.
- Community templates: model validation report, bug report, feature request and support/setup discussion forms.
- Component: `custom_components/inkbird_int14`.
- Docs: `docs/bluetooth_proxy.md`, `docs/lan_setup.md`, `docs/cloud_history_experimental.md`, `docs/model_profiles.md`.
- Tests: `tests/test_static_release.py`, `tests/test_auth.py`, `tests/test_model_profiles.py`.
- Third-party notices: `THIRD_PARTY_NOTICES.md` for MIT-licensed BLE authentication helper attribution.

## Architecture

- BLE direct mode for snapshots and supported local commands.
- BLE challenge/response authentication is performed locally before snapshots and command readback.
- Tuya LAN mode through `tinytuya` for local Wi-Fi station polling and mapped writes when the user supplies host, device ID and local key.
- Optional read-only cloud history polling for DP109.
- Profile-aware probe counts for INT-14, INT-12, INT-31, INT-33 and selected INT-11 family targets.
- Model profiles distinguish physical probes from expected temperature channels so modern multi-sensor probes can be cataloged without pretending their live parser is implemented.
- No cloud live subscription support.
- No cloud write support.
- No raw BLE payload service in the public service surface.

## Home Assistant Metadata

- `iot_class`: `local_polling`
- `config_flow`: `true`
- `integration_type`: `device`
- `codeowners`: present
- `documentation`: `ha-inkbird-int14` repository URL
- `issue_tracker`: `ha-inkbird-int14` repository URL

## Config Flow

The config flow stores the BLE address, model profile, transport mode and optional Tuya LAN settings:

- host/IP;
- device ID;
- local key;
- protocol version;
- port;
- poll interval.

Options expose experimental read-only cloud history fields. Cloud history is disabled by default.

## Entity Surface

Primary readings and controls remain enabled. Raw diagnostics and fragile fields that frequently remain unknown are diagnostic and many are disabled by default.

Battery readings remain numeric when a fresh INT-14 battery snapshot exists. Suspicious repeated 100% reports are surfaced through diagnostic quality and suspect entities instead of making the battery sensors unavailable.

INT-14-BW is the validated profile. Other model profiles are experimental or cataloged as documented in `docs/model_profiles.md`. Cataloged profiles such as INT-14S-BW, INT-12E-BW, INT-11S-B, INT-31-BW and INT-33-BW are selectable for validation intake and expose expected layout diagnostics, but their live transports and writes stay disabled until hardware captures confirm the parser and DP maps.

Hardware validation also confirmed that selecting `BLE only` can force a BLE snapshot/write while the station remains connected to Wi-Fi, and returning to `Auto` restores LAN-first polling.

## Community Intake

GitHub Issues and Discussions include a model validation report form. The Discussion form is attached to the `Q&A` category for early model reports; the Issue form is for reproducible validation findings. Both forms require explicit privacy confirmation before submission.

## Privacy Risks

No real BLE address, cloud credential, local key, LAN IP, account identifier, screenshot, private path or Home Assistant entity ID should be embedded.

Diagnostics redact common credential and identifier keys.

## ESPHome Bluetooth Proxy

Documented only as an optional Home Assistant Bluetooth radio placement aid. It is not published as a separate repository.

## Testable Without Hardware

- Python syntax compilation.
- Static metadata tests.
- Ruff format/check.
- Privacy string audit.
- Secret scanners when installed.

## Current Check Results

- `py -3 -m ruff format --check .`: passed.
- `py -3 -m ruff check --no-cache .`: passed.
- `py -3 -m pytest -q .`: passed, 18 tests.
- `py -3 -m compileall -q .`: passed with bytecode cache outside the candidate directory.
- Cache audit: no `.pytest_cache`, `.ruff_cache`, `__pycache__`, `*.pyc` or `*.pyo` left in the candidate directory after cleanup.
- Manual privacy audit: no private local path, real BLE address, private LAN IP, real MAC or private analysis artifacts found in public files. Only field names and placeholder examples remain.
- `gitleaks detect --no-git -s .`: passed, no leaks found.
- `py -3 -m detect_secrets scan --all-files` with a narrow line exclude for documented cloud credential field labels: passed with an empty result set.
- `trufflehog filesystem . --no-update --fail --no-verification`: passed through the local `trufflehog.exe`, 0 verified and 0 unverified findings.

## Testable With Hardware

- BLE snapshot.
- Tuya LAN polling and mapped writes.
- Optional DP109 cloud history.

## Residual Blockers Before Publication

- Confirm Home Assistant config/options flow in a clean HA test instance.
- Confirm Tuya LAN setup with user-supplied values and no private files.
- Confirm cloud history remains read-only and disabled by default.
- Review HACS metadata after the real GitHub repository exists.
- Consider adding a release CI scanner policy or baseline for expected credential-field label false positives.
