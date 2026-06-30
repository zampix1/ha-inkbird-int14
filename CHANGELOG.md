# Changelog

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
