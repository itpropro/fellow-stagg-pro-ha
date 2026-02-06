# Fellow Stagg Pro Home Assistant Integration

Custom Home Assistant integration (HACS) for local control of a Fellow Stagg EKG Pro/Pro Studio kettle that exposes the local `/cli?cmd=...` endpoint.

Suggested GitHub repository description:

`Local Home Assistant integration for Fellow Stagg EKG Pro kettles via the local CLI API, with safety-guarded controls.`

## Status

- Domain: `fellow_stagg_pro`
- Type: custom integration (`custom_components/fellow_stagg_pro`)
- Scope (v1 scaffold): `water_heater` + diagnostic `sensor` entities
- Transport: local HTTP polling (`iot_class: local_polling`)

## Reverse Engineering Reference (from live kettle)

Endpoint format:

```text
http://<kettle-ip>/cli?cmd=<command>
```

### Confirmed telemetry payloads

- `state` (`ret 0`): primary runtime state
  - Observed keys: `mode`, `tempr`, `temprT`, `temprB`, `units`, `clock`, `scrname`, `ble conn`, `ketl` flags
  - Example observed values: `mode=S_Off`, `tempr=75.254237 C`, `temprT=98.000000 C`, `temprB=100.000000 C`, `units=1`
- `prtsettings` (`ret 0`): persistent settings
  - Observed keys include: `settempr`, `hold`, `units`, `boil`, `schedon`, `wifimode`, `bledis`, `blesec`, `offset_temp`
  - Example: `settempr=196 2C (98.000000 C 208.399994 F)`
- `fwinfo` (`ret 0`): firmware and partition metadata
  - Observed: current version `1.1.75SSP`, boot/running partition `ota_0`
- `temp` (`ret 0`): statistics endpoint, but zero values unless `tstprd` is configured
- `read_adc` (`ret 0`): no explicit ADC value observed in current output

### Command inventory (from `help`)

- System/state: `help`, `reset`, `state`, `statesave`, `prtsaved`, `setstate`, `ss`, `shot`, `refresh`, `sleepms`
- Settings/clock/units: `setsetting`, `setsettingd`, `setsettings`, `setsettingb`, `clrsettings`, `prtsettings`, `prts`, `prtclock`, `setclock`, `incclock`, `incticks`, `setanalog`, `setdigital`, `setaltitudem`, `setaltitudef`, `setunitsc`, `setunitsf`
- Firmware/debug: `fwinfo`, `setpart`, `eraseotherpart`, `heapprt`, `lvglinfo`, `lvglpon`, `lvglpoff`, `logprt`
- GPIO/heating/PWM/temp: `gpioset`, `heaton`, `heatoff`, `warmon`, `warmoff`, `warmduty`, `rmtflt`, `pwmprt`, `temp`, `tstprd`, `buz`, `read_adc`, `temp_offset`, `adcsamples`, `set_period`, `max_duty`, `min_duty`
- Wi-Fi/BLE/network: `wifiprt`, `wifierase`, `wifisappw`, `wifistapw`, `wifistassid`, `wifioff`, `wifion`, `wifisap`, `wifista`, `provreset`, `mdns`, `blesec`, `bleen`, `bledis`, `iot`, `httpdwn`, `httpfw`, `httptest`
- UI input simulation: `1`, `1d`, `1u`, `2`, `2d`, `2u`, `q`, `left`, `w`, `right`, `bc`

### Safety classification

- Likely read-only / low risk: `state`, `prtsaved`, `prtsettings`, `prtclock`, `fwinfo`, `heapprt`, `lvglinfo`, `logprt`, `pwmprt`, `temp`, `wifiprt`, `httptest`, `bc`, `read_adc`, `temp_offset`, `adcsamples`, `shot`
- State-changing / high risk: all `set*`, `reset`, `clrsettings`, Wi-Fi/BLE provisioning toggles, OTA commands, GPIO/heat/PWM controls, simulated button/dial inputs
- Thermal-critical: `heaton`, `heatoff`, `warmon`, `warmoff`, `warmduty`, `setstate`, UI input simulation (`1/2/q/w/...`), PWM period/duty commands

## Safety Notice

This controls a real heating appliance. Any write command can change behavior, activate heat, or alter settings. Validate all control mappings on a supervised kettle before unattended use.

## Disclaimer

This integration relies on an undocumented local API. It may stop working at any time due to firmware or device-side changes. Using this integration is entirely at your own risk.

## Guardrails

- Risky controls are disabled by default.
- Two explicit feature flags gate writes:
  - `enable_heat_control` controls `turn_on` / `turn_off` behavior.
  - `enable_set_temperature` controls target-temperature writes.
- When disabled, the water heater entity hides the related feature support and raises a clear error if write calls are attempted.
- Temperature writes are validated to `40.0-100.0 C` and normalized to `0.5 C` steps.

## Installation (HACS)

1. Add this repository as a custom repository in HACS (`Integration` category).
2. Install **Fellow Stagg Pro**.
3. Restart Home Assistant.
4. Add integration from **Settings -> Devices & Services**.

## Installation (Manual)

1. Copy `custom_components/fellow_stagg_pro` into your Home Assistant config directory under `custom_components/`.
2. Restart Home Assistant.
3. Add integration from **Settings -> Devices & Services**.

## Publishing Readiness

- Root `hacs.json` included
- Integration in `custom_components/fellow_stagg_pro/`
- Required `manifest.json` keys included: `domain`, `name`, `version`, `documentation`, `issue_tracker`, `codeowners`
- CI workflows included:
  - HACS validation (`hacs/action`)
  - Home Assistant validation (`hassfest`)

Recommended before public listing:

- Add repository description + topics on GitHub
- Create GitHub releases/tags for clean versioning
- Add integration brand assets to `home-assistant/brands`
