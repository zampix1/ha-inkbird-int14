# Cataloged-model BLE diagnostics

Cataloged profiles describe the expected physical probes and temperature channels, but they do not claim that live BLE frames are decoded. They keep live transports and writes disabled.

A cataloged profile exposes a diagnostic `Capture BLE Diagnostics` button. The capture:

- asks Home Assistant for a connectable advertisement matching the configured address;
- requests one active Bluetooth scan when the station is not already in the scanner cache;
- falls back to one unambiguous advertisement matching the selected model name;
- connects through the Home Assistant Bluetooth layer, including ESPHome Bluetooth Proxies;
- records GATT service and characteristic UUIDs;
- reads characteristics that advertise the `read` property;
- listens briefly for unsolicited notifications;
- sends no Inkbird authentication, snapshot, settings or pairing commands.

Subscribing to a GATT notification uses the standard Bluetooth notification descriptor. It does not change thermometer settings, but this first-stage capture may still return no temperature payload if the device requires an application handshake.

## Running a capture

1. Select the exact cataloged model profile.
2. Select `BLE only` or `Auto` transport.
3. Fully close the official Inkbird app.
4. Wake the station and put it close to a Home Assistant Bluetooth adapter or ESPHome Bluetooth Proxy.
5. Press `Capture BLE Diagnostics` once.
6. Wait at least 15 seconds.
7. Download the integration diagnostics from Home Assistant.

The diagnostic status explains the first failure boundary:

- `scanner_not_seen`: no Home Assistant scanner has seen the configured address or selected model name;
- `scanner_match_ambiguous`: more than one station advertises the same model name;
- `failed`: discovery worked, but GATT connection or inspection failed;
- `complete`: GATT inspection completed, even if no notification payload arrived.

The downloaded diagnostic includes sanitized service/characteristic metadata, readable values and notification payloads. Bluetooth addresses and IPv4 addresses embedded in errors are redacted.

Do not post unredacted Home Assistant logs. Before sharing diagnostics or screenshots, verify that they contain no addresses, network names, device IDs, local keys, tokens, account data or private entity IDs.
