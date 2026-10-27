# Configuration And Everyday Use

Install **Inkbird INT** from the default HACS catalog, restart Home Assistant,
then add it from **Settings > Devices & services > Add integration**.
If it is already installed, keep the existing entry when updating.

## Manual Installation

1. Download a release from [GitHub](https://github.com/zampix1/ha-inkbird-int14/releases).
2. Copy `custom_components/inkbird_int14` into Home Assistant's `custom_components/` directory.
3. Restart Home Assistant.
4. Add **Inkbird INT** from **Settings > Devices & services > Add integration**.

## First Setup

Choose your exact [model profile](model_profiles.md). The setup form asks for
the station's BLE address, a display name and the transport mode. Optional
Tuya LAN fields include host, device ID, local key, protocol version, port
and poll interval. The connection test before saving is optional.

The BLE fallback direct-read interval is configurable from 5 to 300 seconds,
with a default of 10 seconds. It matters for profiles that keep a GATT
session open; it does not throttle valid notifications.

The profile affects the number of physical probes, mapped temperature
channels, model identity and which connections and controls are available.
For example, the INT-14S-BW's four probes expose 20 temperature channels.
Selecting INT-14-BW for that station can produce incorrect readings.

## Options And Reconfigure

Options includes the BLE fallback interval, transport, LAN fields and
optional experimental cloud history settings. Reconfigure also lets you
review the existing entry's base settings. Save through these dialogs
rather than editing Home Assistant's storage files.

Version 0.2.7 fixed an Options initialization error on current Home Assistant
versions and competing reloads after configuration changes. After updating
from an older version, restart Home Assistant once to load the corrected
Python code. There is no need to remove the entry or pair the station again.

Valid device and entity identities are retained. Since 0.2.6, setup also
removes known stale entities that belong to an incompatible earlier model
profile; it does not rename valid entities.

## Transport Modes

| Mode | Behaviour |
| --- | --- |
| Auto | Prefers Tuya LAN when it is completely configured and supported by the selected model. Avoids a continuous BLE session when LAN is working. |
| BLE only | Uses a Home Assistant Bluetooth adapter or ESPHome Bluetooth Proxy. Snapshot, connected-update and write availability are model-specific. |
| Wi-Fi LAN only | Uses local Tuya LAN through TinyTuya. Requires host, device ID and local key from your own station. |
| Wi-Fi cloud only | Uses optional experimental DP109 cloud history on supported profiles. It is read-only history, not complete live cloud support. |

On INT-14-BW, BLE-only snapshots and validated local operations can also be
used while the station remains connected to Wi-Fi. Actual BLE availability
depends on firmware, reachability and other connected clients. Do not
disconnect Wi-Fi or reset the station just to try this mode.

INT-12E-BW instead keeps a read-only GATT loop, processes notifications
immediately and uses direct reads as a fallback. The station may end the
session after about 30 seconds; the integration reconnects automatically.

INT-12-BW uses a continuous session in `v0.2.11-beta.2`, with notifications
and fallback reads of temperatures, basic state and batteries. Its beta.1
readings have been confirmed on hardware, but reconnect/wake-up recovery
still needs validation. Use the [INT-12-BW beta test guide](int12_bw_beta_test.md)
before trying it; Wi-Fi and settings writes are not validated by this test.

See [local Wi-Fi setup](lan_setup.md), [Bluetooth proxies](bluetooth_proxy.md)
and [cloud history](cloud_history_experimental.md) for their requirements.

## Entities

Main entities include mapped probe temperatures, station temperature where
supported, transport status, local LAN status and selected battery fields.
Settings and target entities depend on the exact profile and transport.
Noisy or fragile diagnostic fields are hidden or disabled by default.

Diagnostic layout entities distinguish physical probes, expected
temperature channels and live mapped channels. Cataloged profiles can
describe the expected layout but create no fake live temperature entities.

Battery values are station reports. Repeated 100% values can be marked by
the battery quality and suspect diagnostics; they are not proof that a
probe is fully charged or docked. Unmapped charging/state fields remain
unavailable rather than being guessed.

## Local Controls And Services

INT-14-BW has validated local operations for unit, display light, target
temperature, pre-alarm, timer/reset and calibration. Supported writes use
Tuya LAN when configured and can fall back to BLE when the selected
profile and transport permit it.

INT-14S-BW, INT-12E-BW and INT-11I-B are read-only in normal operation.
INT-14S has separate opt-in diagnostic unit/target tests; these are disabled
by default and must not be confused with general write support. Read the
[BLE diagnostics](ble_diagnostics.md) and [LAN diagnostics](lan_diagnostics.md)
before enabling those tests.

Public services are named local operations, listed in
[`services.yaml`](../custom_components/inkbird_int14/services.yaml).
They do not expose arbitrary BLE payloads or external cloud DP injection.
Cloud writes are not supported.

## Dashboards

The integration supplies entities, not a dashboard installed automatically.
Use standard Home Assistant cards or adapt the optional
[INT-12E-BW community example](int12e_dashboard.md). Its entity placeholders
must be replaced with the entities in your own installation.

## Sharing A Useful Report

Start with [Discussions](https://github.com/zampix1/ha-inkbird-int14/discussions)
for setup questions or early model validation, and
[Issues](https://github.com/zampix1/ha-inkbird-int14/issues) for reproducible bugs.

Include the selected profile, HA/integration versions, transport and which
readings or actions failed. For multisensor probes, include physical probe
count, app channel count and a controlled tip/body/ambient mapping if possible.

Inspect diagnostics, screenshots and logs before posting. Replace private
addresses, entity identifiers and credentials with placeholders. Never
upload local keys, tokens or a Tuya `devices.json` file.
