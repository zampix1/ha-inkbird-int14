# Release Audit

Last reviewed: 2026-10-26

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

Release `v0.2.10` adds the optional INT-14-BW Cook Control bundle, native Alexa/TV notification routing, bilingual setup guides and real dashboard screenshots. HACS still installs only the integration; the optional ZIP is installed separately. Runtime Python files are unchanged from `v0.2.7`; only the manifest version is bumped. The release retains the model photo gallery, Options/reload fixes and existing model-support boundaries.

HACS default inclusion was approved and merged on 2026-10-18 through [hacs/default#9786](https://github.com/hacs/default/pull/9786). Users can now search for Inkbird INT directly. Images in the README use absolute public URLs so that HACS can display them without resolving GitHub-relative paths. HACS serves documentation for the installed or selected release, so an existing installation must update to see the new README.

INT-14S-BW's normal runtime remains read-only. Its unit and alarm-threshold validation controls are diagnostic, disabled by default and not proof of general write support.

The `v0.2.9` documentation-only release adds official INT-14S-BW, INT-12E-BW and INT-11I-B photos beside the model selection guide. Captions retain the existing support boundaries, including experimental INT-11I-B support. Image source pages and third-party ownership are recorded in `THIRD_PARTY_NOTICES.md`; no runtime, transport or write capability is changed.

This gallery follow-up passed Ruff format/check, all 68 tests and `git diff --check`. All three downloaded assets are 700 x 700 JPEGs and were visually matched to their official model pages. A local Markdown/browser preview loaded all three photos at desktop and mobile widths; this is not a live Home Assistant rendering check.

The `v0.2.9` pre-publication checks also passed compilation with bytecode outside the repository and the cache audit. Gitleaks and TruffleHog found no secrets. Detect-secrets reported only the same eight reviewed constant/UI-label matches for `cloud_api_key` and `cloud_api_secret`, not credential values. The component diff against `v0.2.8` contains only the manifest version change.

## Model Boundaries

INT-14-BW remains the only profile with the full tested combination of BLE snapshots, Tuya LAN polling and mapped local writes.

INT-14S-BW exposes 20 mapped temperatures and battery readings over read-only BLE. Beta.7 added experimental read-only Tuya LAN temperatures from CRC-validated DP109, and a real beta.7 Home Assistant report confirmed station plus undocked-probe readings. Beta.8 removes known stale entities left by an earlier incompatible profile selection. Beta.9 adds CRC-validated read-only station/probe battery percentages from DP103. Beta.10 adds read-only DP104 display brightness after a real capture matched the configured 85% value. A real beta.11 Probe 1 test confirmed the LAN food-high target write at 90 C. Beta.12 expanded the disabled-by-default DP122-125 validation to food high/low and ambient high/low, but a real test exposed concurrent diagnostic/state preparation and a misleading unset `0 F` display. Beta.13 serializes the entire operation and hides inactive thresholds. LAN charging/state DPs, cloud, normal writes and unverified protocol-state entities remain disabled.

INT-12E-BW exposes ten mapped temperatures, station temperature and battery readings over read-only BLE. Notifications are applied immediately; configurable direct reads are only a fallback. The device may close sessions after about 30 seconds with reason `0x13`, and the integration reconnects automatically. Food 4 is confirmed as the tip channel on both probes; Food 1-3 still need physical mapping.

INT-11I-B has experimental community-tested direct GATT reads for temperature and battery. Normal writes remain disabled.

A cataloged probe layout is metadata, not a decoded protocol. Cataloged profiles create no fake live temperature entities and keep BLE runtime, LAN, cloud and writes blocked.

## Public Surface

- Config flow and options flow are enabled.
- Tuya LAN fields are supplied by the user: host, device ID, local key, protocol version, port and poll interval.
- The BLE fallback direct-read interval is configurable from 5 to 300 seconds for profiles that use a connected GATT loop.
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

For this 2026-08-06 stable-release review, Ruff format/check, compileall and all 60 tests passed. Gitleaks and TruffleHog reported no secrets. Detect-secrets reported eight expected keyword matches for the `cloud_api_key` and `cloud_api_secret` field names in constants and translations; no credential values were present. The submitted INT-14S runtime reports were checked before analysis: host, BLE address, device ID and local key were redacted. No test or bytecode cache remains in the repository.

The 2026-10-15 lifecycle smoke test reproduced the Options HTTP 500 on Home Assistant Core 2026.10.1 before applying the patch. Afterward, opening Options, saving and restoring the BLE interval, changing Auto/BLE transport and a managed reload all passed. Each setting change produced exactly one observed unload/setup cycle. The existing config entry, device and entity identities were preserved, effective settings were restored and no Inkbird errors appeared in the post-restart system log. Hardware was offline, so this test does not add protocol or device-write validation. The local suite passes all 68 tests, including eight lifecycle regression cases.

For the `v0.2.7` pre-release checks on 2026-10-15, Ruff formatting/lint, compilation with bytecode outside the repository and all 68 tests passed. Gitleaks and TruffleHog found no secrets. Detect-secrets reported the same eight field-name matches for `cloud_api_key` and `cloud_api_secret`; manual inspection confirmed that these are constants and UI labels, not credentials. The cache audit found no remaining test, Ruff or bytecode caches.

The `v0.2.8` presentation review on 2026-10-19 passed all 68 tests, Ruff formatting/lint and the cache audit. Gitleaks and TruffleHog found no secrets; detect-secrets reported only the same eight field-name matches. All seven README media URLs returned HTTP 200 and every linked repository file exists locally. The product image and both dashboard previews were visually reviewed. A diff against `v0.2.7` confirms that runtime Python files are unchanged. The linked English/Italian wiki installation guides were also updated for default-catalog installation.

## Remaining Risks

### Optional Cook Control, 2026-10-26

- Kept separate under `examples/cook_control`; the integration manifest advances to 0.2.10 for HACS release tracking. Domain, runtime code and model support are unchanged.
- Exercised on HA 2026.10.4 during an INT-14-BW cook. Eight live channels and existing identities preserved; no device writes or HA restart.
- Threshold-to-Echo/TV path physically confirmed. Actual five-minute reminders, Dismiss and cook-change cancellation checked in HA. See the [validation matrix](examples/cook_control/VALIDATION.md) for the precise boundary between physical tests and fixtures.
- Full local suite: 128 tests; dashboard Node checks, Ruff formatting/lint and compilation checked. Optional bundle has 12 allowlisted entries and byte-identical rebuilds.
- Gitleaks and TruffleHog found no secrets. Detect-secrets' eight existing matches are `cloud_api_key` / `cloud_api_secret` constants and UI labels, not credentials. The new dashboard files contain no household IDs, hosts, credentials or captured diagnostics.
- Screenshots contain only the thermometer views. MIT notices and the distinction between protocol work and dashboard design are retained.
- Publication requires successful Tests, HACS and hassfest CI on the release commit, followed by a downloaded-asset hash check. The GitHub Actions runs and release asset provide those publication records. Fresh-install discovery is covered by frontend fixtures; the physical HA check was an upgrade, not a second clean HA instance.

### Integration

- INT-12E-BW needs a controlled physical mapping for Food 1-3.
- INT-14S-BW read-only LAN temperatures, batteries and display brightness are validated from sanitized captures and real runtime reports. Longer reconnect and dock/undock testing is still useful.
- INT-14S-BW Probe 1 food-high LAN target writing is community validated by the station's `H` indication and audible alarm. Food-low and ambient high/low remain opt-in diagnostic tests; normal controls and unrelated writes stay blocked.
- INT-11I-B support is based on limited community hardware validation.
- Tuya local keys must be obtained and protected by each device owner.
- Battery percentages are station-reported values and may remain at 100% for long periods.
- Cataloged models still need sanitized hardware captures before live support can be enabled honestly.
- HACS, hassfest and release packaging must pass again before the next stable tag.

## INT-12-BW Prerelease, 2026-10-27

- `v0.2.11-beta.1` addresses issue #7 only: dedicated ten-byte FF01 temperature parsing, three-byte 2A19 battery and seven-byte FF03 basic status, with strict characteristic-based routing. FF02 settings replies cannot overwrite battery data.
- The app decoder and sanitized captures support an asymmetric mapping: probe 1 food/ambient, probe 2 food, and station temperature separately. Bytes 4 and 7 remain unmapped. No new device-control commands, session timing or other model parsers are introduced.
- INT-12-BW remains experimental. This is capture replay and code validation, not a real-device confirmation of the fixed build. The test guide asks for both app probe screens, a room-temperature comparison, both dock/hand-warming permutations and recovery after reconnect. LAN, cloud history, writes and alarm-bit semantics are not validated by this prerelease. Existing experimental controls are not part of the requested test.
- All 178 tests pass, including production runtime replay and INT-14-BW baseline regressions. Ruff format/check, compileall with bytecode outside the repository, Cook Control Node checks and the cache audit pass.
- Gitleaks and TruffleHog find no secrets. Detect-secrets flags only the eight existing `cloud_api_key` / `cloud_api_secret` constants and UI labels, inspected as non-secret field names. Public tests contain only temperature/status/settings fixtures, not hardware addresses or device-info payloads containing private identifiers.
- The manual ZIP is built from the release commit using an explicit file allowlist: the integration directory, LICENSE, THIRD_PARTY_NOTICES.md and the INT-12-BW test guide. It excludes dashboards, tests, private captures, tools, credentials and caches. HACS still uses the tagged source with the existing hacs.json format.
- The unrelated README presentation draft is excluded. No local Home Assistant installation, restart, integration reload or device operation is performed. IHT-2PB is untouched. v0.2.10 remains stable; tag CI and downloadable asset verification are required before announcing the beta.
