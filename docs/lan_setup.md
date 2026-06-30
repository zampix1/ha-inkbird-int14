# Tuya LAN Setup

Tuya LAN is the preferred steady-state path for this integration when available. It keeps polling local to the user's network and supports the mapped local writes without using cloud write APIs.

## Required Values

The user must provide:

- station host or IP;
- device ID;
- local key;
- protocol version, default `3.5`;
- port, default `6668`;
- poll interval, default `10` seconds.

These values are private. Do not post real values in public issues.

## Config Flow

The initial config flow accepts LAN fields directly. Options can be edited later from Home Assistant.

The optional LAN test attempts a local status poll before saving. If it fails, check:

- the station and Home Assistant are on networks that can reach each other;
- host/IP is correct;
- device ID is correct;
- local key is current;
- protocol version is correct.

## Capabilities

Tuya LAN can read the DP values emitted by the station and can write mapped DP values for:

- display light;
- unit;
- target high;
- calibration;
- pre-alarm;
- timer set/reset.

The station firmware may not return every DP on every LAN poll. Battery and state DPs can be incomplete; BLE snapshot remains available as an opportunistic supplement.

`Auto` mode prefers Tuya LAN for normal polling. If you need to validate BLE reachability or a BLE-only command while Wi-Fi remains connected, temporarily select `BLE only`, run the snapshot or command, then return to `Auto`.

## Privacy

Use placeholders in logs and issues:

```text
host: 192.0.2.10
device_id: example-device-id
local_key: example-local-key
```
