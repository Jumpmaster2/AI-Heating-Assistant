# AI Heating Assistant

[Deutsche Version](README.md)

Custom integration for Home Assistant that controls underfloor heating with one switch per heating circuit (for example a relay that drives the valve actuator) locally, learns the behaviour of every room and lets Claude (Anthropic) review the parameters periodically. Home Assistant makes every switching decision itself. The AI never switches anything; it only adjusts parameters within configurable limits and is asked less often as the local model becomes more reliable.

It typically replaces: thermostat helpers (Generic Thermostat), Better Thermostat, automations for setpoint, weather, cold and vacation handling, and a humidity based ventilation recommendation.

> Status: version 0.1.0, first public release. Please keep an eye on the logbook during the first weeks.

## How it works

### Local control per heating area

* **Target temperature** via the normal thermostat card. It is stored permanently until you change it. No schedules, no night setback (usually counterproductive with underfloor heating).
* **Predictive switch-on:** the circuit turns on when the temperature after the learned dead time (taking cooling rate, outdoor temperature and sun into account) would fall below target minus the switch-on hysteresis.
* **Predictive switch-off:** the circuit turns off when the current temperature plus the expected overshoot reaches target plus the switch-off hysteresis. The overshoot of the slow floor heating is learned (depending on the run time).
* **Windows:** if a window is open longer than the window delay, the heating demand pauses. After closing, the learned recovery time is awaited, because screed and walls often reheat the room themselves. Recovery ends early once the temperature before airing is reached again.
* **Minimum on and off times** are always respected.
* **Frost protection** always applies, also outside the heating period and with the thermostat switched off.
* **Heating period:** outside (e.g. 01.04. to 30.09.) all circuits stay off and the AI is not called.
* **Vacation:** freely selectable entities indicate vacation (e.g. `input_boolean.vacation_mode` or a calendar). Then the vacation temperature applies to all areas. With an optional return entity (e.g. `input_datetime.vacation_end`) preheating starts early enough, based on the learned heat-up rate, to reach the normal target on return.

### Heating day decision (nightly run)

Once per night (time configurable) it is decided whether heating is needed today at all.

1. A **local rule** proposes: heat if the forecast maximum is below `theta` or an area is below target plus `puffer`.
2. The **AI** receives forecast, room values, learned values and the evaluated recent days and answers with structured JSON (schema validated).
3. A **phase model** decides who leads: *AI leads* (start), *shared* (agreement wins, otherwise the rule if it is sure), *rule leads* (the AI is only asked when the rule is unsure, plus once a week as a control). The phase advances after enough days with high agreement and few rule errors and falls back after errors.
4. Every day is **evaluated** afterwards (minutes too cold outside airing phases, heating minutes). Error A (no heating although needed) and error B (heating without need) adapt `theta` and `puffer`.

On a no-heating day all circuits stay off except frost protection and the optional **emergency rule** (area long and clearly below target without airing). The select "Heating day override" overrides the day until the next decision.

### Learning per area

* **Thermal model** (recursive least squares): `dT/dt = a · valve − k · (T_in − T_out) + s · PV`. This yields heat-up rate, cooling rate, influence of the outdoor temperature (`k`) and of the sun (`s`, PV power as sunshine indicator).
* **Events:** dead time after switching on, overshoot after switching off, recovery time after airing.
* All values are stored permanently, exposed as sensors and can be exported, imported and reset.

### AI check (Claude)

* Only on heating days within the heating period. It receives a compact summary per area (actual, target, learned values, statistics since the last check) and returns parameter adjustments as JSON.
* Adjustable parameters: switch-on and switch-off hysteresis, overshoot factor, lead time factor, sun factor, window delay, recovery time correction, `puffer` and `theta`. Every value is clamped to minimum, maximum and a maximum change per check (all configurable).
* **Asking less often:** the check interval doubles after every check without relevant change and without comfort problems (up to the maximum interval). It returns to the base interval if it was too cold, the AI changed something significant, or you change the target or settings.
* **Costs:** token usage times the configured prices. Every call is estimated beforehand; once the monthly budget is reached there are no calls until the month changes.
* **Failures:** on errors, timeouts or invalid answers the control continues with the last learned values. The API key never appears in the log and is redacted in diagnostics.

### Ventilation recommendation

Per area (also without heating circuit) from the absolute humidity inside and outside (or of a reference room):
*Ventilate now* (humidity above threshold and outside air drier), *Ventilation useful* (cools while not heating), *Do not ventilate*, *Close window* (open but useless), *Ventilation blocked* (block entity active, e.g. air conditioner) and *All fine*.

## Installation via HACS

1. Open HACS, choose **Custom repositories** in the top right menu.
2. Add repository `https://github.com/Jumpmaster2/AI-Heating-Assistant`, type **Integration**.
3. Download **AI Heating Assistant** and restart Home Assistant.
4. **Settings > Devices & services > Add integration > AI Heating Assistant**.

Requirements: Home Assistant 2026.10 or newer. For the AI an Anthropic API key (optional, without a key only the local control runs).

## Configuration

### Setup (global)

| Option | Default | Meaning |
|---|---|---|
| Outdoor temperature sensor | | e.g. `sensor.outdoor_temperature` |
| Outdoor humidity sensor | | optional, for the ventilation recommendation |
| Weather entity | | optional, forecast for the nightly run |
| PV power sensor | | optional, sunshine indicator (W or kW) |
| Heating period | 01.10. to 31.03. | format DD.MM. |
| Frost protection | 7 °C | always applies |
| Vacation entities | | "on" = vacation |
| Vacation temperature | 18 °C | for all areas |
| Return date/time | | optional, for preheating |
| Preheat reserve | 30 min | |
| API key, model | Claude Opus 5.5 | changeable, custom model names possible |
| Nightly run | 03:00 | |
| Monthly budget | 5 € | |

### Options (menu)

* **General, Vacation:** as above.
* **Emergency rule:** on, 1 K below target, 45 min, windows unchanged for 30 min.
* **Ventilation:** minimum drying advantage 0.8 g/m³, outside at most 4 K warmer, minimum cooling advantage 1 K, night 20 to 8 h.
* **AI:** model, effort (default low), nightly run, check interval 4 h, maximum interval 48 h, budget, prices in €/million tokens (input, output, cache write, cache read; prefilled with the model's list price), maximum output tokens.
* **AI limits:** minimum, maximum and largest change per check for every parameter.
* **Heating day decision:** start value `theta` (16 °C), evaluation thresholds, learning steps, conditions for phase changes.

Change the API key via **Reconfigure**.

### Heating areas

Under the integration choose **Add heating area**. Per area:

| Option | Default |
|---|---|
| Name | |
| Temperature, humidity and window sensors | e.g. `sensor.living_room_temperature`, `binary_sensor.living_room_window` |
| Heating circuit switch | e.g. `switch.heating_circuit_1`; empty = ventilation recommendation only |
| Initial, minimum and maximum target | 21 / 16 / 24 °C |
| Minimum on and off time | 10 / 10 min (fixed) |
| Start values window delay, recovery time, dead time, puffer | 5 min, 30 min, 30 min, 0.7 K |
| Humidity threshold | 60 % |
| Reference temperature and humidity | optional, instead of outdoor (room without its own window) |
| Ventilation block entity | optional |

## Entities

Global (device "AI Heating Assistant"):

* Binary sensor **Heating day** (with source, reason, confidence, phase)
* Sensors **Decision phase**, **Last AI check** (with summary and last error), **Next AI check**, **AI costs this month**
* Switch **AI enabled**
* Select **Heating day override** (automatic, heat today, no heating today)

Per heating area (own device):

* **Thermostat** (climate)
* Sensors **Status**, **Heat-up rate**, **Cooling rate**, **Overshoot after switch-off**, **Dead time**, **Recovery time after airing**, **Outdoor influence**, **Sun influence**, **Learning progress**
* Sensor **Ventilation recommendation** and binary sensor **Ventilation recommended** (also for areas without heating circuit)

All important decisions and every AI adjustment with its reason are written to the **logbook**. The integration does not send notifications.

## Services

| Service | Purpose |
|---|---|
| `ai_heating_assistant.export_parameters` | learned values and parameters as JSON (service response) |
| `ai_heating_assistant.import_parameters` | set learned values and parameters from JSON (e.g. start values) |
| `ai_heating_assistant.reset_learned` | reset learned values of areas, optionally the parameters too |
| `ai_heating_assistant.run_ai_check` | run the AI check now |
| `ai_heating_assistant.decide_heating_day` | run the heating day decision now, optionally without AI |

Import example:

```yaml
action: ai_heating_assistant.import_parameters
data:
  data:
    areas:
      Living room:
        learned:
          dead_time_min: 45
          recovery_min: 40
          loss_per_h: 0.004
        params:
          hysteresis_on: 0.2
```

## Development

```bash
pip install -r requirements_test.txt
pytest
```

The control and learning logic in `custom_components/ai_heating_assistant/logic/` does not depend on Home Assistant and can be tested on its own. The Home Assistant tests need Linux or macOS (they also run in GitHub Actions).

## License

MIT, see [LICENSE](LICENSE).
