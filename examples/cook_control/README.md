# Inkbird Cook Control

One station, two handhelds, three different cooks. Each keeps its own targets and
alerts. Switching thermometer only changes what you see.

**[Download Cook Control 1.2.0](https://github.com/zampix1/ha-inkbird-int14/releases/download/v0.2.11-beta.5/inkbird-cook-control-1.2.0.zip)**.
This preview bundle is attached to the integration prerelease, but works with the
stable thermometer drivers too. The older 1.1.0 ZIP has the single-cook design.
[Guida in italiano](README.it.md).

## Install

First install Inkbird INT for an INT-14-BW, or the separate
[IHT-2PB integration](https://github.com/zampix1/ha-inkbird-iht2pb-local).
Their temperature entities must already exist. You can use multiple IHT devices.
Cook Control reads those entities; it does not connect to the thermometers itself.

On HA 2026.11 or newer, HACS lives under **Settings > Marketplace**. It is already
built in; do not reinstall the old HACS custom integration. This does not change
the separate Cook Control bundle installation below.

1. Back up Home Assistant. Finish active cooks before upgrading from 1.1.0.
2. Copy these folders from the matching bundle into the HA configuration folder:
   `custom_components`, `packages`, and `www`. Merge folders; do not replace your
   entire existing `custom_components` directory. There must be only one BBQ package.
3. If packages are not enabled, add this under your existing `homeassistant:` key:

   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

4. Check the HA configuration and restart. The package loads the small optional
   `inkbird_cook_control` backend. INT and IHT driver folders are unchanged.
5. Update the existing JavaScript module resource to
   `/local/inkbird-int/inkbird-int-cook-control.js?v=1.2.0` and reload the browser.
6. In your existing dashboard's raw configuration, use [dashboard.yaml](dashboard.yaml):

   ```yaml
   strategy:
     type: custom:inkbird-cook-control
   views: []
   ```

   Set its display name to **Cook Control**. The new strategy name prevents a
   cached single-cook strategy from showing the former reset-on-switch dialog.
   Completely reload the browser or reopen the Companion app after upgrading.

The new cards do not need button-card, card-mod or mini-graph-card. Those can stay
installed for other dashboards. The old presentation files remain in the bundle
for compatibility and attribution, but are not loaded by the new strategy.

The backend currently requires an **administrator HA account** for its controls
and archives. No extra account, cloud service or database is required.

### Still Seeing "Switch Thermometer?"

That reset warning belongs to 1.1.0, not this version. Check that there is only
one Cook Control module resource, its URL ends in `?v=1.2.0`, and the dashboard
strategy is `custom:inkbird-cook-control`. Close old HA tabs and reload the app.
Do not reinstall or pair the thermometer, and do not reset your cook to fix a
cached frontend. Changing view in 1.2.0 never clears targets or disarms alerts.

## Cooks And Names

Choose a thermometer at the top. Use the pencil to call it something useful,
such as "Smoker" or "Kitchen thermometer". Each channel also has a food/probe name:
"Brisket", "Chicken", or whatever is on that probe.

Those are the names used in announcements. Alexa says "Brisket has reached
85 degrees", not a device code or an entity ID. A channel without a food name
uses its physical probe label and the thermometer's friendly name.

Set the HA target, then enable its alert. This also starts recording if that
thermometer has no active cook. You can instead name a cook and start recording
before enabling any alert. Targets are in Celsius, including when HA displays
the source sensor in Fahrenheit.

INT-14-BW has four food channels plus their ambient readings. IHT-2PB has its
built-in tip and two external channels, not an invented ambient sensor.
An unplugged probe remains without a reading. Changing view never changes
another cook, including from a second browser.

The target must be reached for 30 continuous seconds with recent local readings.
Each channel announces once per target/name/arming generation. Editing one
channel cancels only its own pending reminders and allows a new target alert.
Snooze and rest reminders belong to that cook and channel, not the visible card.

**Finish cook** archives that thermometer's session and disarms only its alerts.
Targets and names remain available for next time. Nothing writes settings to the
physical thermometer.

## Echo, TV And Phones

Open Settings. Echo speech uses **Alexa (native)** and your existing Alexa Media
Player integration. OpenAI is not involved. A single Echo can be selected directly.
For several Echos, fill in an announcement group name and a comma-separated list
of their media-player entities, refresh the page/device list, and select that group.
This is an announcement destination list, not an Amazon multi-room music group.

TV alerts are separate, **silent on-screen text**. Configure the TV media-player
entity and its notify service name without `notify.`. The TV is not an Alexa
speaker. Cook Control never turns it on, changes inputs or adjusts any volume.

HA persistent notifications are created first. Optional phone, TV and speech
outputs follow. Test the outputs in Settings: an accepted HA call alone does not
prove that someone heard the Echo or saw the TV popup.

## History

The History tab shows active and finished cooks, their temperature graph, target
changes and notification results. Download CSV for readings or JSON for the full
session. Samples are recorded every 30 seconds while a cook is active; missing
or stale readings produce gaps, not zero-degree samples.

Archives live privately in HA `.storage`, independently of Recorder retention.
Include them in HA backups. They contain names, times, internal device references
and readings; review exports before sharing them. Old cooks cannot be reconstructed
from the former shared helpers, so this archive starts with the upgrade.

On the first start, only the formerly selected thermometer's settings are migrated.
Other thermometers start with zero targets and alerts off. Existing Echo/TV
preferences and legacy helper values are retained. The old shared alarm automations
are disabled; do not re-enable them alongside the backend.

Targets, completed-alert latches and reminder deadlines survive a restart. A
partly completed 30-second wait starts again. HA cannot send alerts while it is
down, and it does not replay completed target alerts after reconnecting.

Local packets older than 120 seconds do not qualify for alarms. Unknown values
and cloud history are not live cooking data. Optional battery warnings respect
suspect-report flags; IHT raw battery levels are never treated as percentages.
Optional stall warnings use a 12-minute trend and a further 45-minute stable period.

## Sources And Rollback

The INT and IHT integrations provide all thermometer communication. Cook Control
adds the dashboard, independent cooks, archive and notification routing.
The earlier presentation builds on Remco's MIT-licensed dashboard v1.4.3;
see [third-party notices](THIRD_PARTY_NOTICES.md). Design credits do not imply
that another project supplied this integration's device protocol.

To roll back, restore the previous package, resource URL and frontend files, remove
the `inkbird_cook_control:` package entry, then check configuration and restart.
Keep the archives and backend storage in your backup. Settings changed in 1.2.0
are not automatically copied back into the old single-cook helpers.
