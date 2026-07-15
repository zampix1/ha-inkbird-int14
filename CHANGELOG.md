# Changelog

## Unreleased

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
