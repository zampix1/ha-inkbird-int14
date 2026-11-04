# INT-11I-B: Reconnect Test

This test is for **v0.2.11-beta.3** and profile **int11i_b**. In
[issue #9](https://github.com/zampix1/ha-inkbird-int14/issues/9), @tolixx measured
much shorter gaps with continuous polling on both a local adapter and an
ESPHome proxy. This beta packages that same profile change. It does not change
the temperature or battery decoder, or enable settings writes.

## Install

Back up Home Assistant and do this while the thermometer is idle.

1. Open **Inkbird INT** in HACS and choose **Redownload**.
2. Select **v0.2.11-beta.3**. Enable prereleases if needed; use **Update information** if it is not listed yet.
3. Download, then restart Home Assistant. Check that the integration version is **0.2.11-beta.3**.

Keep the existing entry, **int11i_b** profile, **BLE only** transport and your
current fallback read interval. Note the interval in your report, but do not
change it or the proxy firmware during this comparison. The download includes
the profile fix, so there is no need to edit `models.py` again. Do not delete
the entry or reset/re-pair the thermometer.

For a manual install, use `inkbird-int14-v0.2.11-beta.3.zip` from the
[prerelease](https://github.com/zampix1/ha-inkbird-int14/releases/tag/v0.2.11-beta.3).
Replace `config/custom_components/inkbird_int14/` with the ZIP's
`custom_components/inkbird_int14/` directory, then restart HA. The ZIP contains
the integration, license notices and this guide, not dashboard or household settings.

## What To Expect

HA no longer deliberately ends INT-11I-B sessions after 20 seconds. It keeps
reading temperature and battery while connected; notifications still update
immediately, independently of the fallback read interval.

The station may still end sessions at around 31 seconds. After the loop detects
a normal disconnect it waits five seconds before reconnecting; a failed cycle
uses a minimum ten-second pause. Those are **retry pauses, not total downtime**:
the next scheduled read, discovery and connection attempts can add to the gap.
The generic connector retry policy is unchanged. This beta does not promise to
fix every long connection failure or keep the station awake indefinitely.

## Two Checks

Fully close the Inkbird app and keep the station near the same active proxy or
adapter used for your previous measurements. No heat source is needed.

1. **Leave the probe out and the station awake for 15-20 minutes.** Do not press Snapshot. Check that the temperature and both battery readings keep returning after disconnects. Record approximate session lengths, typical gaps and the longest gap. A steady temperature alone is not evidence that packets stopped.
2. **While idle, use the station's normal power control to switch it off and back on.** Check that readings return without Snapshot, an integration reload or a restart. Skip this if the model has no suitable normal power control; do not factory-reset it. If readings have not returned after two minutes, download diagnostics before pressing Snapshot and note whether Snapshot helps.

There is no need to repeat the hot-water test or change targets, alarms,
calibration or pairing. INT-11I-B stays read-only. This beta adds no Wi-Fi or
cloud support for it, and no base-temperature entity.

## Send Back

Reply in [issue #9](https://github.com/zampix1/ha-inkbird-int14/issues/9) with:

- Installed integration version, HA version, adapter/proxy and fallback read interval.
- Session lengths and typical/longest gaps with the station awake.
- Whether power-off/on recovered automatically, and how long it took.
- Redacted diagnostics collected during a long gap, if one happens, plus the nearby error lines and timestamps.

The detailed connection counters added for INT-12-BW are not new INT-11I-B
diagnostics in this beta. Existing integration/Bluetooth diagnostics and your
timed observations are useful; do not hunt for fields this profile does not expose.

Inspect attachments before posting. Remove real Bluetooth/IP addresses, device
IDs, keys, tokens, Wi-Fi names and personal details. No broad Bluetooth logging
or full Home Assistant log dump is needed for this first check.

## Roll Back

Select stable **v0.2.10** in HACS and restart HA to return to the previous
INT-11I-B session policy. Keep the existing entry and pairing. This is a beta
for follow-up testing, not a new claim that all reconnect failures are solved.
