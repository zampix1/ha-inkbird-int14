# BLE diagnostics

Cataloged profiles describe the expected physical probes and temperature channels, but they do not claim that live BLE frames are decoded. They keep live transports and writes disabled. Once a parser is validated, normal runtime readings replace the passive capture as the primary test path.

A cataloged profile exposes a passive diagnostic `Capture BLE Diagnostics` button. The capture:

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

## Authenticated snapshot capture

The INT-14S-BW profile, whose FF00 service family and authentication have been confirmed by community hardware captures, also exposes `Capture Authenticated BLE Diagnostics`. This second-stage capture is not passive at the BLE protocol level. It sends only:

- the volatile Inkbird challenge request and response used to open the current BLE session;
- the read/snapshot queries used by the tested INT-14-BW baseline, with the normal clock synchronization frame deliberately omitted.

It does not send unit, display, alarm target, timer, calibration, pairing or provisioning commands. It does not enable normal write controls.

Run this capture with at least one probe awake and outside the charging dock. Keep the official app fully closed, press the authenticated diagnostic button once, wait at least 20 seconds, then download fresh integration diagnostics. The diagnostic records every application command label and payload sent by this capture.

For INT-14S-BW, `FF01` has four 13-byte probe blocks followed by a two-byte station temperature. The confirmed field order in each block is Internal aggregate, Food 1, Food 2, Food 3, Food 4, Ambient and one status byte. Internal/Food values use Fahrenheit hundredths; Ambient and station temperature use Fahrenheit tenths. Docked or unavailable probes use the `0x7FFE` temperature sentinel.

The live parser was introduced in `v0.2.3-beta.3` and community validated for stable `v0.2.3`. Home Assistant creates 20 mapped temperature entities: Food 1-4 and Ambient for each physical probe. The separate Internal aggregate is retained in diagnostics and does not count as another physical sensor. Inherited protocol-state entities are hidden because the INT-14S charging/connection/pairing/alarm bit map is not validated. LAN, cloud and all setting writes remain disabled for this profile.

The downloaded diagnostic includes sanitized service/characteristic metadata, readable values and notification payloads. Bluetooth addresses and IPv4 addresses embedded in errors are redacted.

## INT-12E-BW live BLE behavior

INT-12E-BW has community-validated read-only BLE support in the `v0.2.6` prerelease line. It exposes ten temperatures from two physical probes: Food 1-4 and Ambient for each probe, plus station temperature and the three battery values reported by GATT.

While connected, valid notifications are applied immediately and have been observed roughly every three seconds. The configurable `BLE fallback direct-read interval` does not throttle those notifications. It controls only the safety-net read of the temperature and battery characteristics when no fresh notification has arrived; the default is 10 seconds and the allowed range is 5-300 seconds.

The station has also been observed ending each connection after about 30 seconds with reason `0x13` (remote user terminated connection). This is device behavior, not a failed Home Assistant write. The integration reconnects automatically with bounded backoff, so a short unavailable gap between sessions is expected.

INT-12E-BW remains read-only. It does not expose LAN, cloud, settings writes or protocol-state entities. Food 4 has been physically confirmed as the tip channel on both probes; the exact physical order of Food 1-3 still needs a controlled mapping report.

## Experimental INT-14S unit write validation

`v0.2.6-beta.1` adds two disabled-by-default diagnostic buttons for INT-14S-BW only:

- `Validate BLE Write: Set Celsius`;
- `Validate BLE Write: Set Fahrenheit`.

These buttons do not enable the integration's normal write layer. Each run opens an authenticated BLE session, sends only the station-wide unit opcode, follows it with the already reviewed read/snapshot queries and records whether a unit readback was available. BLE accepting the command is not proof that the station changed, so the tester must still compare the station display before and after pressing the button.

For a reversible test, note the current unit, press the opposite-unit button, confirm the display changed, then press the original-unit button and confirm it was restored. Download fresh integration diagnostics after each press. Do not test target, alarm, timer, calibration, display or pairing writes with this prerelease; those remain blocked.

Do not post unredacted Home Assistant logs. Before sharing diagnostics or screenshots, verify that they contain no addresses, network names, device IDs, local keys, tokens, account data or private entity IDs.
