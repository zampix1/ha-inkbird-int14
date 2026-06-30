# Experimental Cloud History

Cloud history is optional, disabled by default and read-only.

It polls Inkbird history DP109 and converts the latest history sample into the same temperature model used by local transports.

## Supported

- DP109 temperature history polling.
- User-supplied cloud history credentials.
- Poll interval configurable in Home Assistant options.

## Not Supported

- Cloud live subscriptions.
- Cloud writes.
- Cloud battery/state completeness guarantees.
- Any account bootstrap or credential extraction workflow.

## Required Values

The user must supply their own:

- API key;
- API secret;
- product ID;
- device ID;
- country code;
- base URL, if different from the default.

Do not publish real values in logs, issues or screenshots.

## When To Use

Use cloud history only as a fallback when local BLE/Tuya LAN cannot provide recent temperature values. Prefer local Tuya LAN for normal operation when the local key is available.
