# Release Audit

Last reviewed: 2026-07-15

## Public Positioning

- Repository: `zampix1/ha-inkbird-int14`
- Public name: Inkbird INT
- Home Assistant domain: `inkbird_int14`
- Architecture: hybrid/local-first
- Stable baseline: INT-14-BW
- Community-validated read-only BLE: INT-14S-BW and INT-12E-BW
- Experimental community GATT support: INT-11I-B
- Remaining profiles: cataloged only unless `docs/model_profiles.md` says otherwise

The integration supports local BLE, local Tuya LAN where the model and DP map have been validated, and optional experimental read-only cloud history for DP109. It does not support live cloud control or cloud writes.

## Release State

The latest stable release is `v0.2.5`. The `v0.2.6` prerelease line adds the community-validated INT-12E-BW connected BLE path and guarded INT-14S-BW unit-write validation.

Do not describe prerelease behavior as part of the latest stable release. INT-14S-BW's normal runtime remains read-only; its Celsius/Fahrenheit validation buttons are diagnostic, disabled by default and not proof of general write support.

## Model Boundaries

INT-14-BW remains the only profile with the full tested combination of BLE snapshots, Tuya LAN polling and mapped local writes.

INT-14S-BW exposes 20 mapped temperatures and battery readings over read-only BLE. Tuya LAN, cloud, normal writes and unverified protocol-state entities remain disabled.

INT-12E-BW exposes ten mapped temperatures, station temperature and battery readings over read-only BLE. Notifications are applied immediately; configurable direct reads are only a fallback. The device may close sessions after about 30 seconds with reason `0x13`, and the integration reconnects automatically. Food 4 is confirmed as the tip channel on both probes; Food 1-3 still need physical mapping.

INT-11I-B has experimental community-tested direct GATT reads for temperature and battery. Normal writes remain disabled.

A cataloged probe layout is metadata, not a decoded protocol. Cataloged profiles create no fake live temperature entities and keep BLE runtime, LAN, cloud and writes blocked.

## Public Surface

- Config flow and options flow are enabled.
- Tuya LAN fields are supplied by the user: host, device ID, local key, protocol version, port and poll interval.
- The `v0.2.6` prerelease adds a BLE fallback direct-read interval configurable from 5 to 300 seconds for profiles that use a connected GATT loop.
- Cloud history is disabled by default, experimental and read-only.
- Raw BLE payload writes and arbitrary cloud DP injection are not exposed as public services.
- Diagnostic captures redact common credentials, addresses and identifiers, but users are still asked to inspect files before posting them.
- ESPHome Bluetooth Proxy is documented only as an optional remote Home Assistant radio; it is not a separate project.

## Metadata And Packaging

- `iot_class`: `local_polling`
- `config_flow`: `true`
- `integration_type`: `device`
- `codeowners`, documentation and issue tracker are present.
- HACS and hassfest workflows are present.
- Runtime code is contained in `custom_components/inkbird_int14`.
- BLE authentication attribution is documented in `THIRD_PARTY_NOTICES.md`.

## Current Checks

Run these checks again immediately before tagging a release:

- `py -m ruff format --check .`
- `py -m ruff check --no-cache .`
- `py -m pytest -q .`
- `py -m compileall -q .` with bytecode redirected outside the repository
- `gitleaks detect --no-git -s .`
- `detect-secrets scan --all-files`
- `trufflehog filesystem . --no-update --fail --no-verification`
- cache audit for `.pytest_cache`, `.ruff_cache`, `__pycache__`, `*.pyc` and `*.pyo`

For this 2026-07-15 review, Ruff format/check and all 30 stable-branch tests passed; the `v0.2.6` prerelease branch passed 36 tests plus compileall. Gitleaks and TruffleHog reported no secrets. Detect-secrets reported eight expected keyword matches for the `cloud_api_key` and `cloud_api_secret` field names in constants and translations; no credential values were present. The manual privacy scan found only documented placeholder addresses. No test or bytecode cache remains in the repository after cleanup.

## Remaining Risks

- INT-12E-BW needs a controlled physical mapping for Food 1-3.
- INT-14S-BW unit write validation is awaiting a real-device prerelease report; other writes remain blocked.
- INT-11I-B support is based on limited community hardware validation.
- Tuya local keys must be obtained and protected by each device owner.
- Battery percentages are station-reported values and may remain at 100% for long periods.
- Cataloged models still need sanitized hardware captures before live support can be enabled honestly.
- HACS, hassfest and release packaging must pass again before the next stable tag.
