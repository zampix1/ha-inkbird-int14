# Model Profiles

This integration is local-first and profile based. The INT-14-BW profile is the only profile validated with live hardware captures in this repository. Other profiles are exposed so testers can help validate related modern Inkbird INT food thermometers without creating separate forks.

## Exposed Profiles

| Profile | App model | Probes | BLE snapshot | Tuya LAN | Cloud history | Status |
| --- | --- | ---: | --- | --- | --- | --- |
| `int14_bw` | `INT-14-BW` | 4 | yes | yes | DP109 read-only | tested |
| `int14_bw_wh` | `INT-14-BW_WH` | 4 | yes | yes | DP109 read-only | experimental |
| `ing14` | `ING14` | 4 | yes | yes | DP109 read-only | experimental |
| `int14s_bw` | `INT-14S-BW` | 4 | yes | yes | DP109 read-only | experimental |
| `int14p_bw` | `INT-14P-BW` | 4 | yes | yes | DP109 read-only | experimental |
| `int12_bw` | `INT-12-BW` | 2 | yes | yes | DP109 read-only | experimental |
| `int12i_bw` | `INT-12I-BW` | 2 | yes | yes | DP109 read-only | experimental |
| `int12e_bw` | `INT-12E-BW` | 2 | yes | yes | DP109 read-only | experimental |
| `int11i_b` | `INT-11I-B` | 1 | yes | no | no | experimental |
| `int11p_b` | `INT-11P-B` | 1 | no | no | no | cataloged |

## What The Profile Changes

- Number of probe entities created by Home Assistant.
- Device model shown in Home Assistant device info.
- Probe validation for services and number entities.
- Battery 100% plateau diagnostics based on the configured probe count.
- Diagnostic entities for configured model, profile key, support status and probe count.

## What Is Still INT-14 Derived

The command builders, DP maps and parser grammar are still derived from the INT-14 family. This is why non-INT-14 profiles are marked experimental until users provide hardware feedback.

Cloud live data and cloud writes are not supported for any profile. Cloud history remains optional, disabled by default and read-only.

## Cataloged But Not Exposed Yet

The vendor app also contains modern INT-22, INT-31, INT-33, INT-54, ING22 and GB22 families. They are not exposed in this integration yet because they use separate app screens and storage models. They need their own probe-count, frame-length, state/battery and write validation before they can be offered honestly in Home Assistant.

## Reporting Test Results

When opening issues for experimental profiles, include:

- profile key;
- Home Assistant version;
- whether transport is BLE, Tuya LAN or cloud history;
- redacted logs with private values replaced by placeholders;
- which readings or writes work.

Do not include real BLE addresses, LAN IP addresses, device IDs, local keys, cloud credentials or Home Assistant entity IDs.
