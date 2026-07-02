# Inkbird INT for Home Assistant

Home Assistant custom integration for modern Inkbird INT food thermometers with local BLE, local Tuya LAN and optional experimental read-only cloud history.

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=zampix1&repository=ha-inkbird-int14&category=integration)

This project is not affiliated with, endorsed by or supported by Inkbird.

<p align="center">
  <img src="docs/images/int14-product.jpg" alt="Inkbird INT-14 station and wireless probes" width="360">
  <img src="docs/images/int14-ha-card.png" alt="Home Assistant card preview for Inkbird INT-14" width="460">
</p>

Product image is included only as a device reference. Inkbird names, logos and trademarks belong to their respective owners.

## What Works

- Tested with an Inkbird INT-14 station.
- Includes experimental profiles for related INT-14, INT-12 and INT-11 family models.
- Installable as a HACS custom repository or by manual copy.
- Local BLE is used for discovery, snapshots and explicit BLE commands.
- Local Tuya LAN is used for station polling and supported writes when the user supplies their own host, device ID and local key.
- Optional cloud history is read-only and limited to DP109 temperature history.
- Exposes probe temperatures, station temperature, target values, transport status, local availability and selected battery/state indicators.

## Status

Public HACS custom repository release for testers with INT family hardware. INT-14-BW is validated; other profiles are experimental and need hardware feedback.

Repository:

```text
https://github.com/zampix1/ha-inkbird-int14
```

The integration is hybrid/local-first:

- Local BLE for discovery, snapshots and explicit BLE commands.
- Local Tuya LAN for station polling and supported writes when the user supplies host, device ID and local key.
- Optional experimental cloud history for DP109 temperature history only.

Cloud live updates and cloud writes are not supported.

## Requirements

- Home Assistant with Bluetooth enabled for BLE mode and BLE snapshots.
- Inkbird INT-14-BW, or a related model profile listed in `docs/model_profiles.md`.
- Optional Tuya LAN credentials supplied by the user:
  - station host or IP;
  - device ID;
  - local key;
  - protocol version, usually `3.5`.
- Optional cloud history credentials supplied by the user for read-only DP109 history.
- Optional ESPHome Bluetooth Proxy when the Home Assistant Bluetooth adapter is far from the station.

## Installation With HACS

1. Open HACS.
2. Add this repository as a custom repository.
3. Select category `Integration`.
4. Install the integration.
5. Restart Home Assistant.
6. Add `Inkbird INT` from **Settings > Devices & services**.

Repository URL:

```text
https://github.com/zampix1/ha-inkbird-int14
```

## Manual Installation

1. Copy `custom_components/inkbird_int14` into the Home Assistant `custom_components/` directory.
2. Restart Home Assistant.
3. Go to `Settings -> Devices & services -> Add integration`.
4. Search for `Inkbird INT`.

## Configuration

The config flow asks for:

- BLE address of the INT-14 station;
- display name;
- model profile;
- transport mode;
- optional Tuya LAN host, device ID, local key, protocol version, port and poll interval;
- optional Tuya LAN test before saving.

Advanced options include the same LAN fields plus optional experimental cloud history fields.

Cloud history is disabled by default. It is read-only and only polls Inkbird history DP109.

## Transport Modes

`Auto` prefers Tuya LAN when a complete LAN configuration is available. It avoids keeping BLE connected continuously when LAN is working.

`BLE only` uses Home Assistant Bluetooth for local snapshots and supported BLE commands.

BLE sessions perform the local challenge/response authentication before snapshots and command readback. The auth helper is adapted from the MIT-licensed [`paul43210/inkbird-bw-ble`](https://github.com/paul43210/inkbird-bw-ble) work, while this integration remains a native Home Assistant custom integration with Tuya LAN and optional history support.

`BLE only` can be selected explicitly even while the station remains connected to Wi-Fi. This is useful for one-shot GATT snapshots or local BLE writes without changing the station's network setup. Switch back to `Auto` for steady-state LAN polling.

`Wi-Fi LAN only` uses the local Tuya protocol through `tinytuya`. It requires host, device ID and local key supplied by the user.

`Wi-Fi cloud only` uses optional cloud history polling for DP109. It is experimental, read-only and does not support live cloud data or cloud writes.

## Entities

Main entities are enabled by default:

- probe internal and ambient temperatures for the configured model profile;
- base station temperature;
- target high/low values when available;
- display light and temperature unit;
- transport status;
- Tuya LAN availability/status;
- selected battery/state indicators.

Noisy raw diagnostics and fragile fields that are often unknown are marked diagnostic and many are disabled by default.

Battery values remain numeric when a fresh INT-14 battery snapshot exists. Repeated 100% probe reports are flagged through `Battery Report Quality` and suspect binary sensors instead of hiding the battery value. Local testing showed that the station can still report all probe batteries as 100% after successful BLE authentication, so those values should be treated as station-reported rather than independently verified probe fuel gauges.

See `docs/model_profiles.md` for the tested or experimental status of each profile.

## Writes

Supported local writes use Tuya LAN when configured and fall back to BLE only when the selected transport allows BLE:

- unit;
- display light;
- target temperature;
- pre-alarm;
- timer and timer reset;
- calibration.

Cloud writes are not supported.

## Services

The public service surface contains named local operations only. It does not expose raw BLE payload writes or external DP injection.

See `custom_components/inkbird_int14/services.yaml`.

## Documentation

- `docs/lan_setup.md`
- `docs/model_profiles.md`
- `docs/cloud_history_experimental.md`
- `docs/bluetooth_proxy.md`

## Privacy And Security

The repository must not contain real BLE addresses, local keys, device IDs, cloud API credentials, LAN IP addresses, screenshots, local paths or Home Assistant entity IDs.

Diagnostics redact common credential and identifier keys.

BLE authentication code includes MIT-licensed portions adapted from [`paul43210/inkbird-bw-ble`](https://github.com/paul43210/inkbird-bw-ble). See `THIRD_PARTY_NOTICES.md`.

When opening public issues, replace private values with placeholders such as:

```text
AA:BB:CC:DD:EE:FF
192.0.2.10
example-device-id
example-local-key
```

## Known Limits

- A complete local Tuya LAN setup requires the user's own local key.
- Tuya LAN polling may not always emit every DP needed for complete battery/state data.
- BLE snapshots for battery/state are opportunistic and depend on Bluetooth reachability. Forced `BLE only` mode can still work while Wi-Fi is connected, but the station may limit BLE availability depending on firmware state and radio range.
- Battery percentage is the value reported by the station. Use the diagnostic quality/suspect entities when the station reports repeated 100% probe values.
- Cloud history covers DP109 temperature history only.
- Cloud live data, cloud battery/state and cloud writes are not supported.
- Non-INT-14 profiles are experimental until hardware captures confirm their parser and write behavior.

## Alternatives

Before using a custom integration, check whether Home Assistant core or another maintained integration already supports your exact Inkbird model.
