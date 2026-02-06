# Fellow Stagg Pro Home Assistant Integration

A Home Assistant custom integration for Fellow Stagg EKG Pro kettles using the local HTTP CLI endpoint (`/cli?cmd=...`).

## Disclaimer

This integration relies on an undocumented local API. It can stop working at any time due to firmware or device-side changes. Using it is entirely at your own risk.

## Features

- Local polling integration (`iot_class: local_polling`)
- `water_heater` entity for kettle control
- Dedicated `switch` entity for explicit on/off control
- Diagnostic `sensor` entities for mode, firmware, and runtime values
- Safety guardrails for on/off and target writes
- Compatible with Home Assistant `2026.1.3` (minimum declared for HACS: `2026.1.0`)

## Known Limitations

- Command semantics are reverse-engineered and may change with firmware updates
- Some endpoints are incomplete/unclear (`read_adc` currently returns no usable value)
- `temp` statistics are zero unless the kettle-side stats period is enabled

## Installation

### Option 1: HACS (Recommended)

#### Via My Home Assistant Link

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=itpropro&repository=fellow-stagg-pro-ha)

#### Via HACS UI

1. Make sure [HACS](https://hacs.xyz) is installed.
2. In HACS, open the menu in the top-right and select **Custom repositories**.
3. Add `https://github.com/itpropro/fellow-stagg-pro-ha` as category **Integration**.
4. Install **Fellow Stagg Pro**.
5. Restart Home Assistant.
6. Go to **Settings -> Devices & Services -> Add Integration**.
7. Search for **Fellow Stagg Pro** and complete setup.

### Option 2: Manual Installation

1. Copy `custom_components/fellow_stagg_pro` to your Home Assistant config `custom_components/` folder.
2. Restart Home Assistant.
3. Go to **Settings -> Devices & Services -> Add Integration**.
4. Search for **Fellow Stagg Pro** and complete setup.

## Configuration

During setup, provide:

- Kettle host/IP
- Kettle port (default `80`)
- Poll interval (`scan_interval`)
- Optional controls:
  - `enable_heat_control`
  - `enable_set_temperature`

## Guardrails and Safety

- On/off controls are enabled by default (`enable_heat_control`).
- Target temperature writes are disabled by default (`enable_set_temperature`).
- `enable_set_temperature` gates target temperature writes.
- On/off control uses button-2 state-machine toggling (`cmd=2`) to keep the UI/display behavior aligned.
- Low-level heater commands (`heaton`/`heatoff`) are intentionally avoided by the integration because they can desync UI/display state and are riskier.
- Clock sensor is intentionally omitted to avoid minute-level activity log noise.
- Temperature writes are validated to `40.0-100.0 C` and normalized to `0.5 C`.
- This controls a real heating appliance; validate all control behavior supervised.

## Entities

### Water Heater

| Entity | Description |
|--------|-------------|
| Kettle | Main control entity for on/off and target temperature (when enabled) |
| Power | Explicit on/off switch entity |

### Sensors

| Sensor | Description |
|--------|-------------|
| Current Temperature | Current measured kettle temperature |
| Target Temperature | Current target temperature |
| Mode | Parsed kettle mode string |
| Firmware Version | Parsed value from `fwinfo` |
| BLE Connected | BLE connection flag from state |

## Reverse Engineering Reference

Endpoint format:

```text
http://<kettle-ip>/cli?cmd=<command>
```

Confirmed telemetry endpoints:

- `state` (`ret 0`): runtime state (`mode`, `tempr`, `temprT`, `temprB`, `units`, `clock`, `ble conn`, `ketl` flags)
- `prtsettings` (`ret 0`): persistent settings (`settempr`, `hold`, `units`, schedule and connectivity fields)
- `fwinfo` (`ret 0`): firmware and partition metadata
- `temp` (`ret 0`): stats endpoint (zero until stats period is enabled)
- `read_adc` (`ret 0`): currently no explicit usable value observed

Safety classification:

- Likely read-only: `state`, `prtsettings`, `prtclock`, `fwinfo`, `temp`, `wifiprt`, `logprt`, `heapprt`, `lvglinfo`, `shot`
- High-risk writes: all `set*`, `reset`, provisioning/network toggles, OTA commands, GPIO/heat/PWM commands, UI input simulation
- Thermal-critical: `heaton`, `heatoff`, `warmon`, `warmoff`, `warmduty`, `setstate`, simulated dial/button input

## Publishing Notes

- Domain: `fellow_stagg_pro`
- Integration path: `custom_components/fellow_stagg_pro`
- CI included: HACS validation + Hassfest
