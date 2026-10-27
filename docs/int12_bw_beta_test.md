# INT-12-BW: First BLE Test

This is for **v0.2.11-beta.1** and the **INT-12-BW**, not the INT-12E-BW. It fixes the missing temperatures and incorrect battery decoding reported in [issue #7](https://github.com/zampix1/ha-inkbird-int14/issues/7). The packets now pass replay tests, but we still need the readings checked on a real station. The profile stays experimental.

## Install

Make a Home Assistant backup first. Do this with the thermometer idle, not during a cook you are relying on.

In HACS, open **Inkbird INT**, choose **Redownload**, and select **v0.2.11-beta.1** in the version selector. Enable beta/prerelease versions if your HACS view requires it. If the version is missing, use **Update information** first. Restart Home Assistant after downloading.

Keep your existing entry, select profile **int12_bw** and transport **BLE only**. There is no need to delete the integration, reset the station, pair it again or enter Wi-Fi credentials. Do not use int12e_bw for this test.

For a manual install, download `inkbird-int14-v0.2.11-beta.1.zip` from the [prerelease](https://github.com/zampix1/ha-inkbird-int14/releases/tag/v0.2.11-beta.1). It contains `custom_components/inkbird_int14/`, license notices and this guide. Copy that component directory into your Home Assistant `config/custom_components/` directory, replacing the previous component files, then restart. The ZIP does not contain your configuration or a dashboard.

## What Should Appear

The app decoder we examined maps these readings:

| Reading | Expected in this beta |
| --- | --- |
| Probe 1 food/internal | Temperature when the probe reports a reading |
| Probe 1 ambient | Temperature when the probe reports a reading |
| Probe 2 food/internal | Temperature when the probe reports a reading |
| Probe 2 ambient | Not exposed: the app decoder marks it absent |
| Base/station | Temperature |
| Battery | Station, probe 1, probe 2, in that order |

The layout diagnostics should show **2 physical probes and 3 mapped probe temperature channels**. Station temperature is additional. The old, unmapped probe 2 ambient temperature entity is removed on setup; the other valid temperature IDs remain unchanged.

Please check both probe pages in the official app as well. If your app shows an ambient reading for probe 2, that is important: send a redacted screenshot rather than assuming the table above must fit your firmware. We deliberately do not interpret the two unidentified bytes as extra temperatures.

## Three Short Checks

Fully close the official app before each HA check, keep the station awake and nearby, and press **Snapshot** if needed. If you open the app for comparison, note the reading and time, close it again, then allow HA to reconnect. The app and HA may compete for the BLE connection.

1. **Both probes out at room temperature.** Check that the three probe temperatures, station temperature and batteries populate. Compare with the app. The percentages need not match the old capture; they should reflect what the station reports now.
2. **Black probe 1 docked, white probe 2 in your hand.** Warm the metal tip gently with your hand for about a minute. Check that probe 2 internal rises and probe 1 does not keep a false live temperature when the station reports the docked sentinel.
3. **Swap them.** Dock the white probe and gently warm the black probe. Check which HA and app readings change. This is the missing cross-check for the asymmetric layout and probe numbering.

No flame, boiling water, alarms, calibration, target changes or pairing tests are needed. Existing experimental setting controls are not newly validated by this beta; leave them alone. This is a reading test only, although the existing BLE session still uses its normal authentication and snapshot exchange. Connection timing is unchanged, so the beta does not promise to eliminate the station's short BLE sessions.

## Send Back

Reply in [issue #7](https://github.com/zampix1/ha-inkbird-int14/issues/7) with the installed version, a small table of HA/app readings for the three checks, and whether readings resume after a reconnect. Include one sanitized diagnostics file and redacted app screenshots showing both probe pages if possible. Note which probe was docked at capture time.

Do not post real BLE addresses, device IDs, local keys, tokens, Wi-Fi names or personal information. There is no need to enable broad Bluetooth logging unless a reading still fails.

We will validate the read path after those results agree. LAN, cloud history, device alarms and settings writes are separate work, not part of this test.

## Roll Back

Select **v0.2.10** in HACS and restart Home Assistant. Keep the integration entry and pairing. Its old INT-12-BW temperature/battery limitations will return; this is a software rollback, not a reset of the thermometer. The tested INT-14-BW baseline is unchanged by this beta.
