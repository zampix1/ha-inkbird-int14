# Release Audit

Last reviewed: 2026-11-05

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

## Cook Control 1.2.0, 2026-11-05

- Optional preview bundle attached to `v0.2.11-beta.5`. A small separate backend owns per-device cooks, target/notification latches and private archives; it reads registered INT/IHT entities and sends through the existing notification router. It never calls a thermometer write service.
- Three simultaneous sessions on one INT-14-BW and two IHT-2PB devices were recorded, finished and exported on HA 2026.11.0. Legacy helper values were preserved. The user confirmed the two selected Echo announcements and silent LG popup; a true fresh-device threshold crossing remains pending.
- 315 Python tests cover isolation, migration, restart latches, reminders, histories, spoken food names and explicit Echo destinations. Node checks cover the canonical strategy even with a cached old constructor. Desktop/mobile preview checks verify 4/3/3 food-channel layouts, no horizontal overflow, and no HA writes on view changes.
- Upgrade instructions replace the strategy with `custom:inkbird-cook-control`, keep one versioned module resource, and explain the obsolete 1.1.0 confirmation dialog. Images are isolated previews with declared sample data, not screenshots of a private installation.
- The deterministic optional bundle has 17 allowlisted entries, including the backend. No private device references, captures, tools, secrets or caches belong in it. Gitleaks and TruffleHog report no secrets; detect-secrets reports no findings in Cook Control and only existing reviewed field-name/UI-label matches elsewhere.
- Main integration runtime is unchanged from beta.4 except for its manifest version. Integration stable remains v0.2.10; users can install the dashboard ZIP without the BLE beta. Publication is gated on Tests/HACS/Hassfest for the commit/tag and a downloaded-asset hash match.

## Cook Control 1.1.0, 2026-11-04

- `v0.2.11-beta.4` publishes the previously local INT/IHT selector, source-specific
  temperature/history/battery handling and guarded HA-only cook reset. A repeat
  selection of the active thermometer is a no-op. Same-named devices are distinct.
- The optional dashboard follows one cook, not simultaneous independent sessions.
  INT-14-BW and IHT-2PB retain their separate integrations and model-specific
  layouts. Normal dashboard targets never write physical thermometer settings.
- 275 Python tests, frontend Node checks, Ruff format/lint and external-cache
  compilation pass. Tests cover source changes, stale/missing readings, reminders,
  upgrade-safe helpers, same-device selection and notification routing.
- The read-only HA check preserved all 87 protected settings and all three
  deployed package/module hashes. No service calls, threshold changes, restart,
  reload or deployment. No fresh hardware readings were available on this date.
  Earlier INT and IHT delivery tests remain bounded as described in VALIDATION.md.
- Gitleaks and TruffleHog find no secrets. Detect-secrets reports only eight
  reviewed field-name/UI-label matches, not credentials. Generated caches were
  removed. Public screenshots exclude home navigation, account and speaker IDs.
- English/Italian guides include simple upgrade steps, reset-on-switch behavior,
  independent device alarms and separate stable-compatible dashboard installation.
  The optional ZIP uses the existing 12-file allowlist and reproducible metadata.
- Integration runtime differs from beta.3 only in the manifest version. The
  INT-11I-B / INT-12-BW reconnect work is not promoted to stable by this release.
  IHT-2PB's integration repository is untouched; stable remains v0.2.10.
- Publication requires green Tests/HACS/Hassfest on the commit and tag and a
  downloaded-package hash match. The HACS README is updated for beta.4; stable
  installations can keep their runtime and download just the dashboard asset.

## INT-11I-B Reconnect Beta, 2026-11-04

- `v0.2.11-beta.3` sets `continuous_gatt_polling=True` for INT-11I-B. Runtime changes versus beta.2 are limited to this profile metadata and the manifest version; the shared connection implementation is unchanged.
- Regression tests cover polling beyond the former 20-second limit, normal versus failed-cycle retry pauses, existing connector arguments, cleanup and unchanged read-only capabilities. Other profiles retain their beta.2 policy.
- The isolated release tree passes 202 tests, Ruff formatting/lint, Cook Control frontend checks and compilation with bytecode outside the tree. No test, Ruff or bytecode caches are included.
- Gitleaks and TruffleHog found no secrets. Detect-secrets found eight existing field-name/label matches for `cloud_api_key` and `cloud_api_secret`; manual inspection confirmed no credential values.
- The optional manual ZIP contains only the component, license notices and the INT-11I-B test guide. Pending local dashboard changes and household configuration are excluded.
- No Home Assistant deployment, restart or live-device changes were part of this release check. @tolixx's local-patch measurements support trying the packaged beta, but do not replace its follow-up hardware test. INT-11I-B remains experimental and read-only; station-initiated disconnects and longer failed-connect gaps remain possible.
- Publication is gated on Tests, HACS and Hassfest for the commit and tag, with the uploaded ZIP checked against the local package. Stable remains `v0.2.10`.

## Release State

Prerelease `v0.2.11-beta.5` publishes optional Cook Control 1.2.0 with independent
concurrent INT/IHT cooks, food-name announcements, persistent history and an
updated showcase. Integration runtime is unchanged from beta.4 apart from the
manifest version. The bundle also works with the stable integration and does not
require installing the Bluetooth beta. See [Cook Control validation](examples/cook_control/VALIDATION.md).

Prerelease `v0.2.11-beta.3` enabled continuous read-only GATT polling for
INT-11I-B, following @tolixx's measurements in issue #9. Its decoder, entity
IDs, experimental status and write restrictions are unchanged. This is a
profile-level change; other models retain their beta.2 behavior. The
packaged update still needs the reporter's follow-up on real hardware.

The beta also retains the INT-12-BW parser and reconnect work from beta.1
and beta.2. Stable remains `v0.2.10`. See the dated audits below.

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

### Beta.2 Reconnect Recovery

- @gilgamezh confirmed beta.1 on INT-12-BW station V1.2.7 / probes v1.1.4 through ESPHome proxies, including the app's asymmetric layout, three probe temperatures, station temperature, batteries and docking. The report also describes long reconnect gaps; these are not dismissed as normal standby.
- Beta.2 removes this model's timed session cutoff, wakes its loop on disconnect, uses configured fallback reads for FF01/FF03/2A19 and refreshes HA's scanner device between failed connection cycles. Normal disconnects wait five seconds; failed cycles wait ten. Connector/backend retries can take longer, so these are not end-to-end recovery guarantees.
- The connector gets one ordinary connection-error/timeout attempt per INT-12-BW cycle; transient retry handling stays in the library. Missing HA scanner devices are retried without fabricating an empty device. Subscription setup, fallback-read batches and disconnect cleanup are bounded. Cleanup always clears the runtime client reference and releases the lock, including transport changes and cancellation.
- All 199 tests pass: production methods exercised with HA/radio boundary doubles cover disconnect callbacks, wake-up, timeout recovery, cancellation, transport switching, polling intervals and unchanged INT-14/INT-12E policies. Parser regression tests and Cook Control Node tests pass. Ruff format/lint and external-cache compilation pass. These are not live beta.2 hardware tests.
- Diagnostics expose only connection counts, timestamps, session duration and an error type/code; no raw backend messages were added. Gitleaks and TruffleHog report no secrets. Detect-secrets reports the same eight reviewed field-name/UI-label matches, not credentials.
- The manual ZIP uses the same explicit runtime/license/test-guide allowlist as beta.1, excluding tests, tools, captures, home configuration and dashboards. Verify deterministic rebuilds, committed-file content and the downloaded release hash before announcing it. Require successful Tests/HACS/Hassfest on main and tag.
- INT-12-BW stays experimental pending the new reconnect report. Parser code, valid entity IDs, device writes and other model connection policies are unchanged. No production HA deployment/restart, IHT-2PB change or unrelated README draft is part of this release.

### Beta.1 Parser Fix

- `v0.2.11-beta.1` addresses issue #7 only: dedicated ten-byte FF01 temperature parsing, three-byte 2A19 battery and seven-byte FF03 basic status, with strict characteristic-based routing. FF02 settings replies cannot overwrite battery data.
- The app decoder and sanitized captures support an asymmetric mapping: probe 1 food/ambient, probe 2 food, and station temperature separately. Bytes 4 and 7 remain unmapped. No new device-control commands, session timing or other model parsers are introduced.
- INT-12-BW remains experimental. This is capture replay and code validation, not a real-device confirmation of the fixed build. The test guide asks for both app probe screens, a room-temperature comparison, both dock/hand-warming permutations and recovery after reconnect. LAN, cloud history, writes and alarm-bit semantics are not validated by this prerelease. Existing experimental controls are not part of the requested test.
- All 178 tests pass, including production runtime replay and INT-14-BW baseline regressions. Ruff format/check, compileall with bytecode outside the repository, Cook Control Node checks and the cache audit pass.
- Gitleaks and TruffleHog find no secrets. Detect-secrets flags only the eight existing `cloud_api_key` / `cloud_api_secret` constants and UI labels, inspected as non-secret field names. Public tests contain only temperature/status/settings fixtures, not hardware addresses or device-info payloads containing private identifiers.
- The manual ZIP is built from the release commit using an explicit file allowlist: the integration directory, LICENSE, THIRD_PARTY_NOTICES.md and the INT-12-BW test guide. It excludes dashboards, tests, private captures, tools, credentials and caches. HACS still uses the tagged source with the existing hacs.json format.
- The unrelated README presentation draft is excluded. No local Home Assistant installation, restart, integration reload or device operation is performed. IHT-2PB is untouched. v0.2.10 remains stable; tag CI and downloadable asset verification are required before announcing the beta.
