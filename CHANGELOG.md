# Changelog

## 0.2.11-beta.1

- Fix experimental INT-12-BW BLE decoding using issue #7 captures and the model-specific app layout: ten-byte FF01 temperatures, three-byte 2A19 battery and seven-byte FF03 basic status.
- Route INT-12-BW data by characteristic UUID and parse FF02 settings strictly, preventing status/settings packets from overwriting battery percentages.
- Map probe 1 food/ambient and probe 2 food only. Preserve existing valid temperature IDs and remove the previously unmapped probe 2 ambient temperature entity on setup.
- Add capture replay and runtime regression tests. The fix still needs live confirmation from the reporter; INT-12-BW remains experimental. No changes to INT-14-BW parsing, write commands or reconnect timing.
- Include a [short BLE test guide](docs/int12_bw_beta_test.md) and a runtime-only manual installation ZIP with license notices. Stable users can remain on v0.2.10.

## 0.2.10

- Add optional Inkbird INT Cook Control for one INT-14-BW: single-prefix discovery/setup, English/Italian core labels, two-sensor probe diagrams, responsive controls and real HA screenshots.
- Add native Alexa Media Player announcements and optional silent TV popups, with no volume/input changes. A controlled HA threshold crossing was physically confirmed on Echo and LG webOS.
- Guard target alerts against stale data and reconnect duplicates; make Snooze/Dismiss and cook changes cancel pending reminders. Verify real five-minute timers and add automated regression coverage.
- Include a separate Cook Control ZIP, bilingual installation/rollback guides and a deterministic bundle builder. HACS installs the integration only; Cook Control is an optional manual setup. Thermometer runtime and model support are unchanged; only the integration manifest version is bumped.
- Add verified Buy Me a Coffee and GitHub Sponsors buttons near the top of the GitHub/HACS page, and include both options in the repository funding links. Documentation-only change.

## 0.2.9

- Add official INT-14S-BW, INT-12E-BW and INT-11I-B product photos to the model guide, with explicit read-only and experimental support labels and source credits. No runtime or model-support changes.
- Keep image links absolute for HACS and retain INT-14-BW as the tested baseline.
- Documentation-only release: thermometer runtime, transports, settings controls and support levels are unchanged from 0.2.8.

## 0.2.8

- Refresh the GitHub/HACS presentation with a product photo, a sanitized INT-14 preview and the optional INT-12E community dashboard.
- Use absolute public image URLs so media also loads when the README is rendered inside HACS.
- Replace custom-repository installation steps with direct search in the default HACS catalog following inclusion through hacs/default#9786.
- Add a shorter model support summary, clickable user guides and a dedicated configuration guide. Keep validated, experimental and cataloged profiles clearly separated.
- Documentation-only release: thermometer runtime and protocol support are unchanged from 0.2.7.

## 0.2.7

- Fix competing reloads when changing the transport or other settings through Reconfigure (issue #5). Reloads now use Home Assistant's config-entry manager, which also removes the previous update listener.
- Keep the runtime available if Home Assistant cannot unload the entity platforms.
- Fix opening Options on current Home Assistant versions by using the config entry supplied by the options-flow framework.
- Verify the fixes on Home Assistant Core 2026.10.1 with an existing INT-14-BW entry: Options, saving/restoring the BLE interval, Auto/BLE transport changes and a managed reload. Device/entity identities and effective settings were preserved. Hardware was offline during this lifecycle test.

## 0.2.6

- Promote INT-12E-BW read-only BLE temperature and battery support after stable community testing of notifications, fallback reads and automatic reconnects.
- Promote INT-14S-BW local support with community-validated BLE temperatures/batteries and CRC-checked, read-only Tuya LAN temperatures, batteries and display brightness.
- Keep INT-14S-BW normal operation read-only. Its LAN alarm-threshold controls remain advanced diagnostics, disabled by default and LAN-only.
- Mark the INT-14S-BW Probe 1 food-high write as hardware validated after the station displayed `H` and sounded the alarm.
- Preserve the beta.13 fixes that serialize DP122-125 target writes and keep inactive raw `0 F` thresholds unavailable.
- Remove stale entities that belong to an incompatible model profile after reconfiguration while preserving valid entity IDs.
- Rename the polling option to `BLE fallback direct-read interval`, clarifying that valid BLE notifications can update entities more frequently than the configured fallback cadence.

## 0.2.6-beta.13

- Serialize the complete INT-14S target validation operation, including payload construction, LAN write, read-back, local state update and diagnostic history.
- Prevent rapid writes from preparing multiple compound DP122-125 payloads against the same stale threshold state.
- Keep target controls temporarily unavailable while another target write is active.
- Treat raw `0 F` values as unset when their high/low mode is disabled instead of exposing the misleading `-17.8 C` placeholder.
- Supersede beta.12 for the four-threshold hardware test; no device or pairing change is required.

## 0.2.6-beta.12

- Mark the beta.11 INT-14S-BW food-high LAN write as community validated after a real Probe 1 test applied 90 C and the station displayed the high-target indication.
- Expand the disabled-by-default validation controls to food high, food low, ambient high and ambient low for each physical probe.
- Preserve every previously accepted threshold in the 20-byte DP122-125 target block when the next threshold is written, even when the station omits the target DP from immediate read-back.
- Add a bounded diagnostic history for the last eight target tests so one final diagnostics file can cover a complete four-threshold sequence.
- Preserve the beta.11 food-high entity unique IDs and keep all validation LAN-only, with no BLE fallback or normal INT-14S controls yet.

## 0.2.6-beta.11

- Add a model-specific parser and builder for the 20-byte INT-14S-BW target blocks carried by DP122-125.
- Add four disabled-by-default diagnostic number entities that perform an opt-in Tuya LAN write of the food high target for Probes 1-4.
- Encode the 20-byte value as Base64 for TinyTuya's local JSON representation of Tuya raw DPs.
- Keep the validation strictly LAN-only: it never falls back to BLE and remains unavailable without complete Tuya LAN configuration.
- Preserve known low-target, ambient, preset, timestamp and pre-alarm fields when constructing the compound target payload.
- Validate read-back only when the station returns the written DP; otherwise report `awaiting_visual_confirmation` instead of claiming success.
- Keep normal INT-14S settings controls and every other write disabled pending a real-device report.

## 0.2.6-beta.10

- Add read-only INT-14S-BW Tuya LAN display brightness from DP104 after a sanitized real-device capture confirmed the configured 85% value.
- Keep the last valid INT-14S temperature and battery CRC diagnostics when those DPs are absent from a later partial Tuya response.
- Add visible diagnostic capture status and timestamp entities so users can tell when a LAN capture has actually completed before downloading diagnostics.
- Keep INT-14S brightness, sound, alarm and all other writes disabled.

## 0.2.6-beta.9

- Add read-only INT-14S-BW Tuya LAN battery readings from DP103.
- Decode DP103 as station battery followed by Probe 1-4 battery percentages and a trailing CRC-8/ATM byte, matching both the vendor app parser and a sanitized real-device report.
- Reject unexpected lengths and checksum failures before updating battery entities.
- Keep battery values marked as station-reported; the existing quality diagnostics flag an all-100% plateau as suspect when charging state is unavailable.
- Keep every INT-14S LAN write and all unvalidated charging/state/settings DPs blocked.
- Thanks to @remb0 for the sanitized beta.8 diagnostics that confirmed the live DP103 frame.

## 0.2.6-beta.8

- Confirm experimental read-only INT-14S-BW Tuya LAN temperature polling from a real Home Assistant beta.7 report.
- Remove only known entity-registry entries that are incompatible with the currently selected model profile.
- Clean up stale INT-14-BW internal-temperature, target, timer, calibration and protocol-state entities after the same config entry is reconfigured as INT-14S-BW.
- Preserve valid temperature, battery, transport and diagnostic entities, including customized entity IDs.
- Report the cleanup count in downloaded integration diagnostics.

## 0.2.6-beta.7

- Add experimental read-only Tuya LAN temperatures for INT-14S-BW from community hardware validation of DP109.
- Decode DP109 as the validated 54-byte multisensor temperature frame plus a trailing CRC-8/ATM byte (`poly 0x07`, init `0x00`).
- Reject unexpected lengths and checksum failures before applying any live temperature.
- Keep every INT-14S LAN write and all unvalidated battery, state, target, timer and calibration DPs blocked.
- Thanks to @remb0 for obtaining the local credentials privately and sharing a sanitized capture.

## 0.2.6-beta.6

- Add an INT-14S-BW-only `Capture Read-Only LAN Diagnostics` button for mapping its model-specific Tuya DPs without enabling normal LAN polling.
- Keep the INT-14S Tuya LAN runtime and all normal writes disabled; captured DPs are not passed to the INT-14-BW parser or exposed as live entities.
- Sanitize the capture by exporting numeric/boolean DP values and recognized encoded payloads while reducing arbitrary strings and unknown binary values to length/type/hash metadata.
- Document that impossible INT-14S temperatures seen through the INT-14-BW profile are parser mismatch artifacts, not calibration errors.

## 0.2.6-beta.5

- Show `BLE direct-read interval` in initial setup, Reconfigure and Options instead of relying on the Options form alone.
- Persist the interval explicitly in config-entry data during setup/reconfiguration and preserve compatibility with values already stored in options.
- Keep the allowed range at 5-300 seconds and the INT-12E default at 10 seconds.

## 0.2.6-beta.4

- Treat the repeatable INT-12E-BW remote BLE disconnect after approximately 30 seconds as a station session limit rather than a parser failure.
- Reduce the normal continuous-GATT reconnect delay from 10 to 5 seconds, while retaining a 10-second minimum backoff after actual connection errors to avoid proxy retry storms.
- Keep the validated 10-second default temperature/battery read interval unchanged.

## 0.2.6-beta.3

- Keep the INT-12E-BW GATT connection open and read FF01 plus 2A19 directly at a configurable interval instead of reconnecting for every update.
- Add a `BLE direct-read interval` option from 5 to 300 seconds, defaulting to 10 seconds for continuous GATT polling profiles.
- Use the configured interval as the INT-12E reconnect delay after a dropped connection, reducing the previous 45-60 second recovery cycle.
- Confirm from community hardware testing that all ten INT-12E temperature entities populate and that `Food 4` is the tip sensor on both probes.

## 0.2.6-beta.2

- Add experimental read-only BLE polling for INT-12E-BW from a real-device community capture: two physical probes and ten live temperature channels (`Food 1-4` plus `Ambient` per probe).
- Decode the 28-byte FF01 frame as two 13-byte multisensor blocks plus station temperature, and decode the three-byte 2A19 station/probe battery report.
- Use direct GATT reads so snapshots remain useful when notification subscriptions fail through an ESPHome Bluetooth Proxy.
- Keep INT-12E-BW Tuya LAN, cloud, writes and unvalidated protocol-state entities disabled.
- Thanks to @Nexus1212 for the careful capture and hardware testing.

## 0.2.6-beta.1

- Add two disabled-by-default INT-14S-BW diagnostic buttons for a controlled, reversible BLE unit write test: set Celsius and set Fahrenheit.
- Authenticate the BLE session before sending the unit opcode, issue only read/snapshot queries afterward and record command/readback status in sanitized diagnostics.
- Keep normal INT-14S writes blocked: target, preset, alarm, timer, calibration, display and pairing controls remain unavailable.
- Include the complete diagnostics privacy fixes released in v0.2.4 and v0.2.5.

## 0.2.5

- Redact the config entry `unique_id`, which is derived from the BLE address and remained visible after the v0.2.4 LAN-key fix.
- Validate the generated diagnostics against a live Home Assistant config entry: no LAN credential, LAN identifier, top-level runtime address or config-entry BLE address remains exposed.

## 0.2.4

- Fix diagnostics redaction for the actual Tuya LAN config-entry keys: `lan_host`, `lan_device_id` and `lan_local_key`.
- Stop exporting the runtime BLE address as a bare top-level diagnostics string.
- Add regression coverage tying the diagnostics redaction set to the LAN storage-key constants.
- Users of v0.2.3 and earlier should not share diagnostics containing LAN configuration; remove previously shared files and rotate/re-provision exposed local keys where practical.

## 0.2.3

- Add community-validated, read-only BLE support for INT-14S-BW: 4 physical probes and 20 live temperature channels (`Food 1-4` plus `Ambient` per probe).
- Confirm the INT-14S FF01 field order, signed values, mixed Fahrenheit scales and docked-probe sentinel through authenticated real-device captures.
- Keep INT-14S Tuya LAN, cloud, settings writes and unvalidated protocol-state entities disabled.
- Retain passive and authenticated BLE diagnostics for future state-frame work.
- Thanks to @lyonhome for patiently testing all four prereleases, sharing sanitized diagnostics and catching the misleading inherited state entities before the stable release.

## 0.2.3-beta.4

- Keep the community-validated INT-14S-BW BLE temperature and battery path from beta.3.
- Hide inherited charging, connected, paired, timer, alarm, Wi-Fi, sound and mute binary sensors for INT-14S-BW because its protocol-state frame has not been mapped yet.
- Retain only transport and derived battery-quality binary diagnostics for this profile, avoiding plausible-looking but unvalidated state values.

## 0.2.3-beta.3

- Add experimental read-only BLE temperatures for INT-14S-BW after a community hardware capture confirmed authentication and the 54-byte FF01 frame.
- Map each of the four physical probes to four food channels plus ambient, preserving the separate Internal aggregate as diagnostic runtime data.
- Correct the INT-14S wire scales: Internal/Food values are Fahrenheit hundredths; Ambient and station values are Fahrenheit tenths.
- Keep INT-14S Tuya LAN, cloud history and all settings writes disabled. Its snapshot path sends authentication and read queries but omits clock synchronization.

## 0.2.3-beta.2

- Add a separate authenticated BLE diagnostic capture for the observed INT-14S-BW profile. It sends only the volatile challenge/response exchange and snapshot queries; it omits the normal clock-sync frame and does not send settings, target, calibration, timer, display or pairing commands.
- Decode the observed 13-byte multi-sensor probe blocks into numbered raw temperature slots for diagnostics, without assigning those slots to Home Assistant entities yet.
- Keep the original passive capture available and keep cataloged profiles non-live and write-blocked.

## 0.2.3-beta.1

- Add an opt-in BLE diagnostic capture button for cataloged profiles. It discovers the station through Home Assistant Bluetooth, enumerates GATT, reads readable characteristics and captures unsolicited notifications without sending Inkbird application commands.
- Keep cataloged profiles non-live and write-blocked: diagnostic capture does not create temperature entities or claim parser support.
- Include sanitized runtime BLE diagnostic data in Home Assistant diagnostic downloads.

## 0.2.2

- Add INT-11I-B GATT-poll BLE parsing from community validation: FF01 temperature in Fahrenheit hundredths and 2A19 base/probe battery.
- Treat INT-11I-B as read-only BLE for now: no Tuya LAN, no cloud history and no writes until hardware write behavior is validated.
- Add a proper Home Assistant reconfigure flow and harden form defaults so older/partial entries do not open the config flow with a 500 error.

## 0.2.1

- Add cataloged INT-11S-B, INT-31-BW and INT-33-BW model profiles without enabling unvalidated live transports or writes.
- Add physical-probe and temperature-channel layouts for modern multi-sensor INT profiles.
- Keep cataloged multi-sensor profiles read-only/non-live until their BLE frames, Tuya LAN DPs and write behavior are validated.
- Clarify that `probe_count` means physical probes; expected temperature channels are tracked separately.

## 0.2.0

- Add model profiles for the modern INT-14, INT-12 and INT-11 family targets.
- Make probe entity creation, diagnostics and service validation profile-aware.
- Document tested versus experimental model support.
- Add sanitized GitHub templates for model validation, bug reports, feature requests and support discussions.

## 0.1.2

- Add local BLE challenge/response authentication before INT-14 snapshots and BLE writes.
- Expose lightweight BLE authentication diagnostics for troubleshooting local sessions.
- Fix request-init-on-connect to reuse the active BLE client instead of re-entering the connection lock.

## 0.1.1

- Fix Home Assistant Hassfest metadata for Bluetooth dependency and config-entry-only setup.

## 0.1.0

- Prepare `ha-inkbird-int14` candidate as hybrid/local-first.
- Move Tuya LAN setup into config flow/options.
- Keep cloud history optional, experimental and read-only.
- Remove public raw BLE payload and external DP injection services.
- Mark noisy diagnostics as diagnostic and disabled by default where appropriate.
- Keep fresh INT-14 battery readings numeric while exposing suspicious repeated 100% reports through diagnostic quality/suspect entities.
- Document forced BLE snapshot/write validation while the station remains connected to Wi-Fi, with `Auto` returning to LAN polling afterward.
