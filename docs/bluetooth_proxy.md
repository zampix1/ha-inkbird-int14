# Bluetooth Proxy

The integration uses Home Assistant's Bluetooth layer for BLE snapshots and BLE commands. An ESPHome Bluetooth Proxy is optional and acts only as a remote BLE radio.

Use it when:

- the Home Assistant host is far from the INT-14 station;
- the host Bluetooth adapter is unstable;
- BLE snapshots are unreliable because of range or placement.

The proxy does not decode INT-14 data, does not know the Tuya LAN local key and does not use Inkbird cloud credentials. It is not published as a separate project by this candidate.

Do not publish real Wi-Fi names, passwords, API keys, OTA passwords, MAC addresses or IP addresses. Keep those values in ESPHome `secrets.yaml`.

Minimal ESPHome shape:

```yaml
esphome:
  name: inkbird-ble-proxy
  friendly_name: Inkbird BLE Proxy

esp32:
  board: esp32dev
  framework:
    type: esp-idf

logger:

api:
  encryption:
    key: !secret inkbird_ble_proxy_api_key

ota:
  - platform: esphome
    password: !secret inkbird_ble_proxy_ota_password

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password

esp32_ble_tracker:

bluetooth_proxy:
  active: true
```

The proxy is not required for Tuya LAN or cloud-history modes. It only improves BLE reachability.

When Tuya LAN is configured for a supported profile, `Auto` mode normally keeps the station on LAN and avoids a continuous BLE connection. Select `BLE only` temporarily when you need a forced BLE snapshot or a supported BLE command. Switch back to `Auto` after the test if LAN should remain the steady-state transport.

## INT-12E-BW through a proxy

INT-12E-BW uses a read-only connected GATT loop. Notifications can update temperatures more often than the configured fallback direct-read interval; that setting is a safety net, not a notification throttle.

Real-device testing through an ESPHome Bluetooth Proxy showed that the station closes the connection after about 30 seconds with reason `0x13`. The integration reconnects automatically. Brief unavailable gaps are therefore expected, and an occasional slower reconnect is not by itself a proxy failure. Place the proxy close enough to the station before treating reconnect delays as a protocol problem.
