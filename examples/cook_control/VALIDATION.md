# Cook Control Validation

## Cook Control 1.2.1 Preview, 2026-11-05

- Published as a prerelease, replacing the withdrawn 1.2.0 ZIP. Real INT-14-BW and two-IHT threshold/output validation is pending
  while the owner is away; isolated tests are not reported as hardware passes.
- All 256 Python tests, Node contracts and Ruff format/lint checks pass. Focused
  tests cover delivery errors, lock isolation, timeout/unknown results,
  restart recovery, per-output plans, zero/manual/auto rest, missing probes,
  per-channel stall, battery deduplication, atomic preset save, safe legacy
  commands and segmented archive roundtrips.
- Edge desktop/mobile checks cover 4/3/3 channels, view selection without writes,
  live readings during editing, C/F, preset save/apply, stall controls, device
  views and active history refresh. TEST commands preserve cook settings/indexes.
- Installed after backups and one authorized restart on HA 2026.11.0. The backend
  reports 1.2.1, all three driver entries are loaded, and no backend errors were
  logged. Protected targets, names, arming state, Echo/TV helper settings and all
  three existing archives compare identically before and after.
- The live HA UI renders all four views. Device selection shows the correct
  4/3/3 layout and native driver cards; stall/rest controls and earlier archives
  open correctly. No target/arming edits, announcement tests or physical writes
  were made during this verification. Thermometers had no fresh readings.
- The 1.2.0 physical Echo/TV confirmation below belongs to its earlier router test,
  not this delivery implementation. New physical confirmation is still required.

## Cook Control 1.2.0 Preview, 2026-11-05

- 316 Python tests pass on the development branch and 242 on the isolated stable-release branch. They cover independent three-device alert latches, per-channel edits, restart recovery, migration, history gaps, friendly spoken names, battery/stall guards and explicit Alexa group membership. These include isolated HA boundary tests, not a substitute for physical cooking tests.
- Node frontend contracts pass. Playwright/Edge checks at 1440px and 390px verify four INT food cards and three cards per IHT, no horizontal overflow, no JavaScript errors, and no HA write calls when switching the view.
- Illustrated probes, circular gauges and per-channel mini-graphs are retained. The custom preset editor is tested through opening, editing, cancelling, saving without target changes, and applying only to the selected device/channel. HA target/arming state is not changed by opening or saving a preset.
- Installed on HA 2026.11.0 after backup and one authorized restart. Backend loaded successfully and discovered one INT-14-BW and two IHT-2PB devices through stable registry identities. Existing protected helper values survived unchanged.
- Recorded three simultaneous sessions clearly named as installation checks, then finished and exported each one. No fake temperature states, armed alerts or threshold changes were used. With thermometers not supplying recent data, the records correctly contain gaps.
- Verified the real dashboard selector, archive and CSV download. One end-to-end notification-router test called the two explicitly configured Echos and the configured LG webOS popup service. The trace finished without errors; monitored speaker/TV volumes were unchanged. This is software-path evidence, not proof of audible or visible physical delivery.
- The user subsequently confirmed both Echo audio and the G5 popup after checking remotely. The repeated test again targeted only the two selected Echos and the TV service; thresholds and the user's current volumes remained unchanged. No fresh real-device threshold crossing has been tested with this backend yet.
- The stable release branch retains the v0.2.10 integration/domain/driver code apart from the manifest version. The canonical strategy was tested against a pre-existing cached single-cook constructor; it does not reuse it. Installation guides explicitly migrate that strategy to prevent the old reset warning.

## Cook Control 1.1.0

Published as the separate `inkbird-cook-control-1.1.0.zip` asset with
v0.2.11-beta.4. It also works with the stable integration; installing the
Bluetooth beta is not required.

### Release Check, 2026-11-04

- 275 Python tests and the frontend Node checks pass. Additional coverage checks
  same-device selection as a no-op, preserving existing helper values on upgrade,
  distinct labels for same-named thermometers and read-only dashboard generation.
- INT's four food/ambient cards and IHT's three single-temperature cards were
  inspected in an isolated preview at 1200px and 390px widths. No horizontal
  overflow; unavailable readings remain blank. This preview uses sample data,
  not a connection to HA.
- The existing HA 2026.10.4 installation was inspected read-only. All 87 protected
  settings and the deployed package/module file hashes stayed unchanged. One
  dashboard resource was registered, Alexa's notify service existed and no BBQ
  errors appeared in the current system log.
- No thermometer had fresh readings during this release check. No test notification,
  source switch, device write, HA restart, integration reload or deployment was
  performed. Physical delivery evidence is from the earlier checks below.

### Live IHT Check, 2026-10-30

- The picker lists the INT-14-BW and both configured IHT-2PB devices separately,
  including an INT whose optional model diagnostic entity is disabled.
- IHT-2PB uses built-in, external 1 and external 2. The active device's built-in
  and external 2 temperatures populated; unplugged external 1 and slot 4 remained
  unavailable. No ambient temperature or battery percentage is fabricated.
- Switching runs a dedicated HA-only reset before changing the source. Source
  attributes protect against an old frame; old reminders are cancelled. Derivative
  consumers ignore their buffer for 12 minutes after a device change.
- A controlled target on the unused room-temperature built-in tip passed the real
  30-second trigger. The notification trace finished with native Alexa and LG notify
  calls and no errors. The owner physically confirmed Echo delivery. The TV was not
  being watched, so physical popup delivery is **not confirmed in this test**.
- Test helpers were restored; the cooking external channel and device thresholds
  were unchanged. No HA restart or integration reload. Existing automation
  enablement and TV destination were preserved.
- 269 Python tests plus frontend mapping/selection tests passed. This includes
  stale data, missing channels, Celsius/Fahrenheit conversion, source isolation,
  explicit model guards, disarming, cancellation and raw battery handling.
- Desktop and 390x844 mobile views were inspected with the actual IHT readings.
  The selector is compact, the three channel names fit, and disconnected channels
  do not leave a spinning per-probe graph. The shared source-specific history remains.

This is still one selected cook at a time. It does not merge the INT and IHT device
integrations or validate other INT model layouts.

## Earlier INT-14-BW Check, 2026-10-26

Cook Control for v0.2.10 was checked with Home Assistant 2026.10.4 and INT-14-BW.
This page distinguishes observed behaviour from tests using controlled inputs.

### On A Running Home Assistant

| Check | Result |
| --- | --- |
| Four physical probes, eight live food/ambient channels | Populated during a real cook; existing entity, unique and device IDs preserved. |
| Existing cook | Probe 1 name, HA target and station threshold preserved. No thermometer write, pairing change or HA restart. |
| Threshold automation | On unused probe 2, lowered only its HA target below its real room-temperature reading. The real 30-second trigger ran. Echo speech and LG text were both physically confirmed by the owner. Test helpers restored. |
| Rest reminder and snooze | Actual five-minute timers completed and invoked the notification router. Timer traces finished without errors. No claim of separate physical confirmation for each repeated message. |
| Dismiss | Synthetic Companion-action event cancelled both running reminder scripts. |
| Cook change | Changing the test probe's name cancelled its pending snooze. |
| Malformed action | Incomplete `BBQ_` event rejected by conditions, not treated as a probe number. |
| Settings | YAML configuration check passed; no new BBQ errors in the system log. Unrelated automation enablement preserved. |
| Desktop and mobile | Cook and probe views checked at 1600x1200 and 390x844. Two-point probe diagram, no five-channel placeholder. |

The threshold test is a controlled HA-level crossing, not proof that the food in
probe 1 reached its target. It also does not test the station's physical buzzer.
The Companion events were sent to HA for testing; mobile-phone delivery was not
configured or physically checked.

## Automated Coverage

The optional package tests exercise active/disabled probes, stale/future timestamps,
missing or non-numeric temperatures, Celsius conversion, target deduplication,
rest/snooze cancellation, strict action validation, suspect batteries, continuous
stall prerequisites, native Alexa routing and nonintrusive TV behaviour.

Dashboard tests check both model layouts, model rejection, first-run discovery,
thermometer selection, language regeneration, valid button-card styles and the
model-specific diagrams. The ZIP builder uses an explicit file allowlist and reproducible
metadata; it includes no live configuration or captured diagnostics.

## Not Claimed

- No forced physical low-battery, disconnected-probe or fault test in this cook.
  Battery and missing-data guards were tested with fixtures.
- No observed 45-minute real cooking stall. Its conditions and timer structure
  were checked automatically.
- No end-to-end generic TTS provider or mobile push test. Native Alexa and LG
  text are the physical outputs verified here.
- No Tuya LAN test in this cooking session; it used BLE. Both local packet
  timestamps are accepted by the freshness guard.
- No simultaneous independent cooks or multisensor INT-model dashboard validation.
  Multiple configured INT/IHT devices can be selected one at a time.
- A station packet does not independently prove every probe is healthy. Values
  and availability still depend on what the integration can decode.

## Publication Boundary

The 1.2.0 ZIP was withdrawn. Cook Control 1.2.1 is an optional preview attached
to v0.2.12-rc.1; it can also be installed alongside stable v0.2.10 or v0.2.11.
Its integration runtime is unchanged from v0.2.10 apart from manifest metadata.
The INT-11I-B and INT-12-BW connection changes remain separate beta work.

HACS does not automatically install the dashboard: the package requires the
documented configuration copy and resource registration. The IHT integration
remains separate and is not bundled here.

The new 1.2.0 showcase images are isolated previews with sample readings, labelled
as such. Older real-dashboard screenshots remain historical evidence only.
No home navigation, account details, private device references or speaker IDs are
included in the new images. The current preview is not presented as a live cook.
