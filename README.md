# Inkbird INT-14 for Home Assistant

Home Assistant custom integration for Inkbird INT-14 with local BLE, local Tuya LAN and optional experimental read-only cloud history.

This project is not affiliated with, endorsed by or supported by Inkbird.

## Status

This is a future HACS candidate, not a published release. The intended repository name is:

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
- Inkbird INT-14-BW or a compatible INT-14 station.
- Optional Tuya LAN credentials supplied by the user:
  - station host or IP;
  - device ID;
  - local key;
  - protocol version, usually `3.5`.
- Optional cloud history credentials supplied by the user for read-only DP109 history.
- Optional ESPHome Bluetooth Proxy when the Home Assistant Bluetooth adapter is far from the station.

## Installation

Manual test installation:

1. Copy `custom_components/inkbird_int14` into the Home Assistant `custom_components/` directory.
2. Restart Home Assistant.
3. Go to `Settings -> Devices & services -> Add integration`.
4. Search for `Inkbird INT-14`.

Do not add this repository to HACS until a maintainer has completed the release audit and created an actual GitHub repository.

## Configuration

The config flow asks for:

- BLE address of the INT-14 station;
- display name;
- transport mode;
- optional Tuya LAN host, device ID, local key, protocol version, port and poll interval;
- optional Tuya LAN test before saving.

Advanced options include the same LAN fields plus optional experimental cloud history fields.

Cloud history is disabled by default. It is read-only and only polls Inkbird history DP109.

## Transport Modes

`Auto` prefers Tuya LAN when a complete LAN configuration is available. It avoids keeping BLE connected continuously when LAN is working.

`BLE only` uses Home Assistant Bluetooth for local snapshots and supported BLE commands.

`BLE only` can be selected explicitly even while the station remains connected to Wi-Fi. This is useful for one-shot GATT snapshots or local BLE writes without changing the station's network setup. Switch back to `Auto` for steady-state LAN polling.

`Wi-Fi LAN only` uses the local Tuya protocol through `tinytuya`. It requires host, device ID and local key supplied by the user.

`Wi-Fi cloud only` uses optional cloud history polling for DP109. It is experimental, read-only and does not support live cloud data or cloud writes.

## Entities

Main entities are enabled by default:

- probe 1-4 internal and ambient temperatures;
- base station temperature;
- target high/low values when available;
- display light and temperature unit;
- transport status;
- Tuya LAN availability/status;
- selected battery/state indicators.

Noisy raw diagnostics and fragile fields that are often unknown are marked diagnostic and many are disabled by default.

Battery values remain numeric when a fresh INT-14 battery snapshot exists. Repeated 100% probe reports are flagged through `Battery Report Quality` and suspect binary sensors instead of hiding the battery value.

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
- `docs/cloud_history_experimental.md`
- `docs/bluetooth_proxy.md`

## Privacy And Security

The repository must not contain real BLE addresses, local keys, device IDs, cloud API credentials, LAN IP addresses, screenshots, local paths or Home Assistant entity IDs.

Diagnostics redact common credential and identifier keys.

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

## Alternatives

Before using a custom integration, check whether Home Assistant core or another maintained integration already supports your exact Inkbird model.
