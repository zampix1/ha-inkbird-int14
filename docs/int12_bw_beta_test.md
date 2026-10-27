# INT-12-BW: Reconnect Test

This is for **v0.2.11-beta.2** and the **INT-12-BW**, not INT-12E-BW. In [issue #7](https://github.com/zampix1/ha-inkbird-int14/issues/7#issuecomment-6447166597), @gilgamezh confirmed the beta.1 temperatures, batteries and docking state on a real station. The app also confirmed that only the black probe has an ambient reading. There is no need to repeat that whole mapping exercise.

What remains is recovery: the reporter saw gaps of up to two minutes and one roughly five-minute gap that ended after pressing Snapshot. This beta changes connection handling, not the parser. The profile stays experimental until the wake-up/reconnect checks pass on hardware.

## Install

Make a Home Assistant backup first. Do this with the thermometer idle, not during a cook you are relying on.

In HACS, open **Inkbird INT**, choose **Redownload**, and select **v0.2.11-beta.2**. Enable prerelease versions if your HACS view requires it. If the version is missing, use **Update information** first. Restart Home Assistant after downloading.

Keep your existing entry, profile **int12_bw** and transport **BLE only**. Leave **BLE fallback direct-read interval** at **10 seconds** in the integration options. Do not delete the entry, reset/re-pair the station or use the int12e_bw profile.

For manual installation, download `inkbird-int14-v0.2.11-beta.2.zip` from the [prerelease](https://github.com/zampix1/ha-inkbird-int14/releases/tag/v0.2.11-beta.2). Copy its `custom_components/inkbird_int14/` directory into your Home Assistant `config/custom_components/`, replacing the previous component files, then restart. The ZIP also contains license notices and this guide, not a dashboard or home configuration.

## What Changed

- HA no longer deliberately ends this model's connection after 20 seconds.
- Notifications update readings immediately. Direct reads of temperatures, basic state and batteries run at the configured fallback interval while connected; 10 seconds is not a throttle on notifications.
- A disconnect wakes the loop without waiting for the next scheduled read. It waits five seconds before starting another connection cycle.
- After a failed connection cycle it waits ten seconds, then asks HA for the current Bluetooth scanner device again. There is no fabricated scanner device fallback when HA cannot see the station. The connector is configured for one ordinary error/timeout attempt per cycle, but can still retry lower-level transient failures.
- Subscription setup, a fallback-read batch and disconnect cleanup have limits of 30, 10 and 10 seconds respectively. A stalled operation returns control to recovery instead of holding the session indefinitely.

Those pauses are **not promises of five- or ten-second total downtime**. Discovery, proxy connection slots, connection attempts and firmware behavior add their own delays. This build cannot keep an unreachable or sleeping station connected, and the station may still close a session itself.

## Three Checks

Keep the station close to the same proxy and fully close the Inkbird app. Start with the usual two-proxy setup; do not change proxy firmware, radio settings or the poll interval at the same time.

1. **Both probes out, station awake, for 10-15 minutes.** Let HA run without pressing Snapshot. Check that temperatures and batteries keep updating. If connections still end around 30 seconds, note that, along with the longest gap before readings return. A stable temperature alone does not mean updates stopped.
2. **Both probes docked for about five minutes, then remove one and wake the station normally.** Note the wake-up time and the time the first valid temperature returns. Do not press Snapshot for the first two minutes: that is the automatic recovery test. If it still has not returned, download diagnostics before pressing Snapshot, then note whether Snapshot helps.
3. **Switch the station off and back on using its normal power control, with one probe out.** Check that HA recovers without a reload, restart, re-pair or Snapshot. Skip this if you cannot safely do it while idle; do not reset the station.

No heat source, target changes, device alarms, calibration or pairing tests are needed. Existing experimental write controls remain unvalidated: leave them alone. Normal BLE authentication still happens; this beta adds no settings-write commands.

## Readings To Keep An Eye On

| Reading | Expected |
| --- | --- |
| Black probe 1 | Food/internal and ambient when reporting |
| White probe 2 | Food/internal only; no ambient entity |
| Base/station | Separate temperature |
| Battery | Station, probe 1, probe 2 |
| Docking | Probe temperatures clear when the station sends the absence sentinel; charging state follows the station |

Diagnostics still show **2 physical probes and 3 mapped probe temperature channels**. Valid entity IDs and the beta.1 decoder are unchanged. A device-reported 100% battery is not a measured capacity estimate.

## Send Back

Reply in [issue #7](https://github.com/zampix1/ha-inkbird-int14/issues/7) with the installed version, results of the three checks, approximate session lengths and the longest reconnect gap. One sanitized diagnostics file after a gap is more useful than another large log dump. If a gap persists, include the nearby error lines and timestamps, not your entire HA log.

The new runtime fields include `ble_connection_count`, `ble_connect_failure_count`, `ble_last_connect_attempt_epoch_s`, `ble_last_connected_epoch_s`, `ble_last_disconnected_epoch_s`, `ble_last_session_seconds` and `ble_last_connect_error`. Counters reset when the integration reloads; Snapshot also uses a connection, so note any manual presses. Error diagnostics contain an error type or `device_not_seen`, not the raw backend message. The session length includes setup and cleanup, not just temperature listening. Disconnect timestamps record HA's cleanup, not an exact over-the-air termination time.

Inspect diagnostics before posting. Remove real addresses, device IDs, local keys, tokens, Wi-Fi names and personal details. No need to enable broad Bluetooth logging unless we need a narrower follow-up.

Once recovery is confirmed, we can add INT-12-BW to the community-validated **BLE read** models. That does not validate Wi-Fi, cloud, device alarm semantics or settings writes.

## Roll Back

Select **v0.2.11-beta.1** in HACS and restart HA to retain the fixed decoding with the previous session behavior. Or select stable **v0.2.10**, whose old INT-12-BW temperature/battery limitations will return. Keep the entry and pairing. Other models, including the tested INT-14-BW baseline, retain their connection policy.
