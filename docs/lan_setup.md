# Tuya LAN Setup

Tuya LAN is the preferred steady-state path for this integration when available. It keeps polling local to the user's network and supports the mapped local writes without using cloud write APIs.

## Beginner Version

Use this path when your INT station is already connected to Wi-Fi and you want Home Assistant to talk to it on your local network.

You need five values:

| Field | What it means | Example |
| --- | --- | --- |
| Host or IP | The address of the station on your LAN. Prefer a fixed DHCP reservation in your router. | `192.0.2.10` |
| Device ID | The Tuya device identifier for your own station. It is not the model name. | `example-device-id` |
| Local key | The per-device Tuya local key. It is not your Wi-Fi password and not your Inkbird password. | `example-local-key` |
| Protocol version | Tuya LAN protocol version. For the tested INT-14-BW station this is usually `3.5`. | `3.5` |
| Poll interval | How often Home Assistant asks the station for local data. Start with `10` seconds. | `10` |

The integration cannot discover the local key by itself. Get the device ID and local key from your own device with a Tuya/local-key workflow you trust, then paste them into Home Assistant. If you already use LocalTuya, TinyTuya or another Tuya LAN tool for the same station, these are the same kind of values. Follow those tools' current documentation for key extraction. If you reset or re-pair the station, the local key can change.

## How Do I Get The Device ID And Local Key?

This integration intentionally does not ask for Tuya cloud API credentials. It only needs the final local values. Most users get them with one of these routes:

### Route A: You Already Use LocalTuya Or Tuya Local

If the same station is already configured in LocalTuya, Tuya Local or another Tuya LAN tool, reuse the same values:

- IP/host;
- device ID;
- local key;
- protocol version.

Do not paste your Tuya API secret into this integration. Only paste the device ID and local key for the thermometer station.

### Route B: TinyTuya Wizard

TinyTuya can scan the LAN and run a setup wizard that writes a `devices.json` file containing device IDs and local keys for your own Tuya devices.

Typical commands:

```bash
python -m pip install tinytuya
python -m tinytuya scan
python -m tinytuya wizard
```

After the wizard, look for the station entry in `devices.json`:

```json
{
  "name": "example name",
  "id": "example-device-id",
  "key": "example-local-key",
  "ip": "192.0.2.10",
  "version": "3.5"
}
```

`devices.json` contains secrets. Do not upload it to GitHub and do not paste it into issues.

### Route C: Tuya IoT Developer Portal

The Tuya developer portal can also show the device ID and local key after your app account is linked to a Tuya cloud project. The exact menu labels move over time, but the usual path is:

1. create or open a Tuya IoT cloud project;
2. link the app account that owns the device;
3. find the device under the cloud project device list and copy its device ID;
4. open API Explorer;
5. use the device details query under device management;
6. copy the returned local key.

Some branded apps and regions behave differently. If the device does not appear, follow the current TinyTuya, LocalTuya or Tuya Local documentation rather than guessing.

Useful references:

- TinyTuya: <https://github.com/jasonacox/tinytuya>
- Tuya Local device details guide: <https://github.com/make-all/tuya-local/blob/main/DEVICE_DETAILS.md>
- LocalTuya: <https://github.com/rospogrigio/localtuya>

## Setup Steps For Normal Users

1. Add the thermometer to the Inkbird app and make sure Wi-Fi works there.
2. In your router, reserve a fixed IP for the station if possible.
3. Get the station's device ID and local key from your own account/device.
4. In Home Assistant, go to **Settings > Devices & services > Inkbird INT**.
5. Open the integration setup or options.
6. Fill in:
   - host or IP;
   - device ID;
   - local key;
   - protocol version, usually `3.5`;
   - poll interval, usually `10`.
7. Enable the LAN test before saving if you want Home Assistant to verify the values immediately.
8. Set transport mode to `Auto` for normal use. Use `Wi-Fi LAN only` only when you want to test LAN without BLE/cloud fallback.

If LAN works, diagnostics such as `Local LAN Configured`, `Local LAN Available`, `Local LAN Status OK`, `Local LAN Update OK` and `Last LAN Update Epoch` should start showing useful values.

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

Common mistakes:

- using the Inkbird account password instead of the local key;
- using the Wi-Fi password instead of the local key;
- using a cloud API key instead of the device's local key;
- letting the router change the station IP after setup;
- blocking traffic between the Home Assistant network and the IoT Wi-Fi/VLAN;
- keeping an old local key after resetting or re-pairing the station.

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
