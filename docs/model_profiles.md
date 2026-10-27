# Model Profiles

This integration is local-first and profile based. INT-14-BW remains the fully tested baseline. INT-14S-BW and INT-12E-BW have community-validated read-only BLE parsers in stable `v0.2.6`. Other profiles are exposed so owners can validate related modern Inkbird INT food thermometers without creating separate forks.

Modern Inkbird probes are not always one probe equals one temperature. Some probes expose several food sensors plus an ambient sensor. The integration therefore tracks both physical probes and expected temperature channels.

## Exposed Profiles

| Profile | App model | Physical probes | Expected temp channels | Live mapped temp channels | BLE snapshot | Tuya LAN | Cloud history | Status |
| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |
| `int14_bw` | `INT-14-BW` | 4 | 8 | 8 | yes | yes | DP109 read-only | tested |
| `int14_bw_wh` | `INT-14-BW_WH` | 4 | 8 | 8 | yes | yes | DP109 read-only | experimental |
| `ing14` | `ING14` | 4 | 8 | 8 | yes | yes | DP109 read-only | experimental |
| `int14s_bw` | `INT-14S-BW` | 4 | 20 | 20 | yes | DP109/DP103/DP104 read-only | no | community validated, read-only |
| `int14p_bw` | `INT-14P-BW` | 4 | 8 | 8 | yes | yes | DP109 read-only | experimental |
| `int12_bw` | `INT-12-BW` | 2 | 3 | 3 | experimental in v0.2.11-beta.1 | unvalidated | unvalidated | experimental |
| `int12i_bw` | `INT-12I-BW` | 2 | 4 | 4 | yes | yes | DP109 read-only | experimental |
| `int12e_bw` | `INT-12E-BW` | 2 | 10 | 10 | yes | no | no | community validated, read-only |
| `int11i_b` | `INT-11I-B` | 1 | 1 | 1 | yes | no | no | experimental |
| `int11p_b` | `INT-11P-B` | 1 | 2 | 0 | no | no | no | cataloged |
| `int11s_b` | `INT-11S-B` | 1 | 5 | 0 | no | no | no | cataloged |
| `int31_bw` | `INT-31-BW` | 1 | 5 | 0 | no | no | no | cataloged |
| `int33_bw` | `INT-33-BW` | 3 | 13 | 0 | no | no | no | cataloged |

## Expected Layouts

| Profile | Expected physical layout |
| --- | --- |
| `int14_bw` | 4 probes, each with food/internal and ambient channels. |
| `int12_bw` | Probe 1 food/internal + ambient; probe 2 food/internal only in the app parser. Hardware confirmation of this layout is pending. |
| `int14s_bw` | 4 probes, each expected to expose `food_1`, `food_2`, `food_3`, `food_4` and `ambient`. |
| `int12e_bw` | 2 probes, each expected to expose `food_1`, `food_2`, `food_3`, `food_4` and `ambient`. |
| `int31_bw` | 1 probe expected to expose `food_1`, `food_2`, `food_3`, `food_4` and `ambient`. |
| `int33_bw` | 2 long probes expected to expose 4 food channels plus ambient; probe 3 mini expected to expose 3 food channels. |
| `int11s_b` | 1 probe expected to expose `food_1`, `food_2`, `food_3`, `food_4` and `ambient`. |

These layouts come from the vendor app model definitions, where the app initializes physical probe records and their per-probe sensor lists. That is enough to model the expected shape, but it is not enough to claim live support for every channel. Live support also needs validated BLE frames, Tuya LAN DP mapping or cloud history mapping.

## What The Profile Changes

- Physical probe count used by Home Assistant device diagnostics and service validation.
- Expected temperature channel count shown as a diagnostic.
- Which temperature channels can create live temperature entities.
- Device model shown in Home Assistant device info.
- Battery 100% plateau diagnostics based on the configured physical probe count.
- Whether BLE snapshot, Tuya LAN, cloud history and writes are enabled.

`probe_count` remains available internally as a compatibility property, but it now means physical probes only. Use `temperature_channel_count` to reason about the expected number of temperature channels.

## What Is Still INT-14 Derived

Most command builders and DP maps are still derived from the INT-14-BW baseline. Profiles with `0` live mapped temperature channels are intentionally cataloged only: they describe expected hardware layout, but they do not create live temperature entities, enable LAN/cloud transports or allow writes.

Cloud live data and cloud writes are not supported for any profile. Cloud history remains optional, disabled by default and read-only.

## Cataloged Profiles

Cataloged profiles are selectable only so owners can report the exact model and so Home Assistant creates the right device identity while testing. They do not enable live BLE parsing, Tuya LAN, cloud history or writes yet.

`INT-11S-B`, `INT-31-BW` and `INT-33-BW` remain in this conservative state because the vendor app contains dedicated product/model definitions for them. That is useful evidence for naming and expected channel layout, but not enough to reuse another model's parser safely.

## INT-12-BW BLE Fix In Testing

[Issue #7](https://github.com/zampix1/ha-inkbird-int14/issues/7) exposed a real gap in the experimental profile: authentication worked, but the decoder expected the INT-14-BW's 18-byte temperatures and five-byte battery. The INT-12-BW reports ten and three bytes respectively. This correction is available for testing in `v0.2.11-beta.1`, not in stable `v0.2.10`. See the [BLE test guide](int12_bw_beta_test.md).

The app's INT-12-BW decoder explains the unusual temperature packet. Probe 1 food and ambient occupy bytes 0-3; probe 2 food occupies bytes 5-6. These are signed little-endian Celsius tenths. Bytes 8-9 hold station temperature in Fahrenheit tenths. The app skips bytes 4 and 7 and marks probe 2 ambient as absent, so this integration does not turn those bytes into extra temperatures. Missing/docked values stay unavailable.

The beta maps three probe temperature entities, plus station temperature. Existing IDs for those readings are preserved; setup removes only the obsolete probe 2 ambient temperature entity. Battery order is station, probe 1, probe 2. The reported `50 64 64` therefore means 80%, 100%, 100%, not the bogus percentages previously produced by misreading a status reply.

Packets are now routed by their GATT characteristic. Seven-byte FF03 basic connection/charging/pairing status cannot overwrite the battery, and FF02 settings replies are checked as length-prefixed frames rather than guessed from their total length. Malformed replies are discarded. A 100% report is still a device report, not proof of actual remaining capacity.

Replay tests cover the submitted room-temperature and docked/hand-warmed captures. The fixed build still needs testing on the owner's station, including comparing both probe screens in the official app. Please use `int12_bw`, not `int12e_bw`: the latter is a different multisensor format. There is no new claim of LAN, cloud-history, alarm-bit or write validation here, and no change to connection timing or write commands. Those experimental paths have not been validated on this model; keep this test BLE-only and do not test settings writes yet.

## INT-12E-BW Community-Validated BLE

A community capture from @Nexus1212 confirmed the same multisensor FF01 structure used by INT-14S-BW, with two probes instead of four. The 28-byte value contains two 13-byte probe blocks followed by station temperature. Each probe block exposes an Internal aggregate, `Food 1-4`, `Ambient` and a status byte. Home Assistant exposes the ten physical channels and retains the Internal aggregate only as runtime diagnostics.

The capture also confirmed a three-byte 2A19 battery value: station, probe 1 and probe 2. Direct characteristic reads completed successfully through an ESPHome Bluetooth Proxy even though notification subscriptions failed, so this profile uses GATT polling and does not require notification delivery for snapshots.

Community hardware testing confirms that all ten entities populate with plausible values and that `Food 4` is the tip sensor on both probes. Mapping of `Food 1-3` to the remaining physical sections is still pending.

While connected, valid FF01 notifications update Home Assistant immediately and were observed at roughly three-second intervals. The runtime also reads FF01 and 2A19 directly every 10 seconds by default as a fallback; that interval can be changed from 5 to 300 seconds in the integration options and does not throttle notifications. Community testing shows that the station closes the connection itself after approximately 30 seconds with BLE reason `0x13`; the integration waits 5 seconds, reconnects and resumes both paths. Actual connection failures retain a longer backoff. Transient ESPHome `status=133` connection errors can still occur and are retried.

The BLE temperature/battery transport is community validated. Mapping of `Food 1-3` to exact physical positions is still incomplete, but it does not affect parsing or transport reliability. Tuya LAN, cloud history, every write control and unvalidated protocol-state entities remain disabled.

## INT-14S-BW Community-Validated BLE

A community beta.2 capture confirmed the INT-14S-BW FF00 GATT family, successful challenge/response authentication and a 54-byte FF01 temperature frame. Each physical probe contributes a 13-byte block:

1. Internal aggregate, Fahrenheit hundredths;
2. Food 1, Fahrenheit hundredths;
3. Food 2, Fahrenheit hundredths;
4. Food 3, Fahrenheit hundredths;
5. Food 4, Fahrenheit hundredths;
6. Ambient, Fahrenheit tenths;
7. one status byte.

The four blocks are followed by station temperature in Fahrenheit tenths. Home Assistant exposes the 20 physical temperature channels (`Food 1-4` and `Ambient` per probe). The separate Internal value is retained as diagnostic runtime data and is not counted as a sixth physical sensor.

This profile is community validated and read-only in normal use. Stable `v0.2.6` enables BLE temperature/battery snapshots plus experimental read-only Tuya LAN temperatures from DP109, station/probe batteries from DP103 and display brightness from DP104. Cloud history and all normal setting controls remain disabled. Charging, connected, paired, timer, alarm, Wi-Fi, sound and mute entities are also hidden because the INT-14S protocol-state fields are not mapped yet. Its BLE snapshot path omits clock synchronization and sends only authentication plus read queries. The passive and authenticated BLE diagnostic buttons remain available for follow-up captures.

A real beta.7 Home Assistant report confirmed that LAN polling populates station temperature and the five channels of an undocked probe. It also revealed stale INT-14-BW entities left in Home Assistant's entity registry after an earlier profile change. From beta.8, setup removes only known entities that are incompatible with the selected profile; the 20 INT-14S temperatures, batteries, transport selector and valid diagnostics keep their IDs.

The beta.6 diagnostic established that INT-14S DP109 contains the same 54-byte multisensor layout as the validated BLE FF01 value, followed by CRC-8/ATM. The LAN and BLE temperatures in the submitted Home Assistant diagnostics matched value for value. Beta.7 therefore routes INT-14S through a dedicated parser, verifies the CRC and only then updates the 20 temperature entities. It does not reuse the INT-14-BW parser. Selecting the INT-14-BW profile for an INT-14S can otherwise produce plausible-looking battery data alongside impossible temperatures.

DP109 temperatures, DP103 battery percentages and DP104 display brightness are mapped read-only. The app parser confirms DP103 order as station first, followed by Probes 1-4; DP103 and DP109 carry a trailing CRC-8/ATM byte. A real LAN diagnostic confirmed DP104 as an integer percentage matching the station's configured 85% brightness. DP102 is an online/data-update flag rather than sound. A real hardware test confirmed the opt-in Probe 1 food-high target write on DP122: the station displayed `H` and sounded the alarm. Stable `v0.2.6` retains serialized food high/low and ambient high/low validation controls for DP122-125, disabled by default. Normal target controls and all unrelated writes remain blocked.

`INT-11I-B` is different from the INT-14-BW station profile. A community report from Dmitry/dskudrin validated it as a connectable GATT-poll device: `ff01` exposes one probe temperature as little-endian Fahrenheit hundredths, and `2a19` exposes two battery bytes, base/booster first and probe second. Writes remain disabled for this profile until command behavior is validated on hardware.

## Seen In The App But Not Exposed Yet

The vendor app also contains modern INT-22, INT-54, ING22, GB22 and additional INT-31/INT-33 variants. They are not exposed in this integration yet because they use separate app screens and storage models. They need their own physical-probe count, temperature-channel layout, frame-length, state/battery and write validation before they can be offered honestly in Home Assistant.

## Reporting Test Results

For early results or "does this profile fit my model?" reports, open a GitHub Discussion with the model validation form:

<https://github.com/zampix1/ha-inkbird-int14/discussions/new?category=q-a>

For reproducible failures, open the model validation issue form:

<https://github.com/zampix1/ha-inkbird-int14/issues/new?template=model_validation_report.yml>

Include:

- profile key;
- Home Assistant version;
- physical probe count shown by the Inkbird app;
- number of temperature channels shown by the Inkbird app;
- which channel changes when you heat the tip, middle and ambient section of a probe;
- redacted screenshots of the app screen if useful;
- whether transport is BLE, Tuya LAN or cloud history;
- redacted logs with private values replaced by placeholders;
- which readings or writes work.

Do not include real BLE addresses, LAN IP addresses, device IDs, local keys, cloud credentials, Wi-Fi names, screenshots with private data or Home Assistant entity IDs.
