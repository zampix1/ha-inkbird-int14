# Changelog

## Unreleased

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
