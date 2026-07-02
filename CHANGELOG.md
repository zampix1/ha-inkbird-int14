# Changelog

## Unreleased

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
