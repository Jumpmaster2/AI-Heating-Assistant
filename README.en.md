# AI Heating Assistant

[Deutsche Version](README.md)

Custom integration for Home Assistant that controls underfloor heating with one switch per heating circuit (for example a relay that drives the valve actuator) locally, learns the behaviour of every room and lets Claude (Anthropic) review the parameters periodically. Home Assistant makes every switching decision itself. The AI never switches anything; it only adjusts parameters within configurable limits and is asked less often as the local model becomes more reliable.

It typically replaces: thermostat helpers (Generic Thermostat), Better Thermostat, automations for setpoint, weather, cold and vacation handling, and a humidity based ventilation recommendation.

The overview, the learned values and all settings are in the **AI Heating Assistant** dashboard in the sidebar (see [Dashboard](#dashboard)).

> Status: version 0.11.2. Please keep an eye on the logbook during the first weeks.

## How it works

### Local control per heating area

* **Target temperature** via the normal thermostat card. It is stored permanently until you change it. No schedules, no night setback (usually counterproductive with underfloor heating).
* **Predictive switch-on:** the circuit turns on when the temperature after the learned dead time (taking cooling rate, outdoor temperature and sun into account) would fall below target minus the switch-on hysteresis.
* **Sun ahead:** the cooling over the lead time uses the PV power expected in that time, not only the current value. If the sun is going to heat the room anyway, the circuit does not switch on in the morning; in the evening the control no longer counts on sun that is about to disappear. The source is an optional PV forecast sensor (e.g. Forecast.Solar) or, without it, the hourly weather forecast (cloud coverage) together with the sun position. For the latter the integration learns on nearly cloudless days how much PV power to expect under a clear sky. Only 70 % of the forecast is used, and 1 K below target the area heats regardless of any forecast. Without a PV power sensor nothing changes. If the sensor has no value by day, the PV power counts as unknown: nothing is calibrated or fed into the model, and the expected power is used instead (PV forecast sensor, or sun position and cloud coverage once the scale is learned, otherwise 0); with the sun low or hardly any power expected it counts as 0. A value missing for more than an hour by day is logged as a warning.
* **Predictive switch-off:** the circuit turns off when the current temperature plus the expected overshoot reaches target plus the switch-off hysteresis. The overshoot of the slow floor heating is learned (depending on the run time). After switching off, the heat still stored in the floor is taken into account before switching on again, until the temperature falls; otherwise the circuit would come back right after the minimum off time.
* **Windows:** if a window is open longer than the window delay, the heating demand pauses. After closing, the learned recovery time is awaited, because screed and walls often reheat the room themselves. Recovery ends early once the temperature before airing is reached again.
* **Short airing:** while a window is open, a circuit that is off does not switch on, even before the window delay is over. A running circuit is not interrupted. If the window was open for at least 2 minutes but shorter than the window delay, a shortened recovery follows: the share of the window delay the window was open, applied to the learned recovery time (3 of 5 minutes gives 60 %). It also ends early once the temperature before airing is reached again.
* **Minimum on and off times** are always respected.
* **Frost protection** always applies, also outside the heating period and with the thermostat switched off.
* **Outages:** if the temperature sensor has no value, the circuit stays off (status *Sensor error*) and frost protection cannot work either. If the switch is unavailable, the status shows *Actuator unavailable*. If such an outage (or one of the outdoor temperature sensor) lasts longer than 15 minutes, a repair appears under Settings > System > Repairs; it disappears by itself once the value is back. A switch that does not follow its commands is asked again after 1, 2, 4, 8 and then every 15 minutes instead of every minute; after three attempts a repair appears as well.
* **Heating period:** outside (e.g. 01.04. to 30.09.) all circuits stay off and the AI is not called.
* **Vacation:** freely selectable entities indicate vacation (e.g. `input_boolean.vacation_mode` or a calendar). Then the vacation temperature applies to all areas. With an optional return entity (e.g. `input_datetime.vacation_end`) preheating starts early enough, based on the learned heat-up rate, to reach the normal target on return. A return time in the past (e.g. vacation switched on manually) is ignored and the vacation temperature applies.

### Heating day decision (nightly run)

Once per night (time configurable) it is decided whether heating is needed today at all.

1. A **local rule** proposes: heat if the forecast maximum is below `theta` or an area is below target plus `puffer`.
2. The **AI** receives forecast, room values, learned values and the evaluated recent days (with heating minutes and overheating per day) and answers with structured JSON (schema validated). Comfort has priority, but it should avoid unnecessary heating days.
3. A **phase model** decides who leads: *AI leads* (start), *shared* (agreement wins, otherwise the rule if it is sure), *rule leads* (the AI is only asked when the rule is unsure, plus once a week as a control). The phase advances after enough days with high agreement and few rule errors and falls back after errors.
4. Every day is **evaluated** afterwards. While nothing heated, the real room temperature is the truth (minutes too cold outside airing phases). Once a circuit ran, the decision itself kept the room warm; then a virtual room that keeps cooling with the learned rate and no heating decides. Error A (no heating although needed) and error B (heating without need) adapt `theta` and `puffer`. Days under a manual override are not learned from.

On a no-heating day all circuits stay off except frost protection and the optional **emergency rule** (area below target and temperature expected after the lead time long and clearly below it, without airing). The select "Heating day override" overrides the day until the next decision.

### Learning per area

* **Thermal model** (recursive least squares): `dT/dt = a · valve − k · (T_in − T_out) + s · PV`. This yields heat-up rate, cooling rate, influence of the outdoor temperature (`k`) and of the sun (`s`, PV power as sunshine indicator).
* **Events:** dead time after switching on, overshoot after switching off, recovery time after airing. The dead time only counts once the rise is confirmed (a second sensor step, or one step lasting five minutes), so a single sensor jitter cannot distort it. The recovery time is also learned when heating cuts the wait short, provided the room was warming up by itself at the end of the wait; the thermal model forgets slowly (about three weeks).
* All values are stored permanently, exposed as sensors and can be exported, imported and reset.

### AI check (Claude)

* Only on heating days within the heating period. It receives a compact summary per area (actual, target, learned values, statistics since the last check) and returns parameter adjustments as JSON.
* **Goal:** as little heat as possible without any area falling below its target. Comfort is a hard limit, not something to trade. Besides the minutes too cold the AI therefore receives:
  * **Overheating** (`over_kh`): Kelvin hours more than 0.2 K above the target while the circuit runs and up to 4 hours after switch-off (heat the heating delivered in excess). Warmth from the sun alone on a day without heating does not count. The share with sun (`sun_over_kh`, PV from 0.3 kW) shows whether the sun factor is too low.
  * **Heating effort per demand** (`on_per_kh`): heating minutes per Kelvin hour of difference between target and outdoor temperature, so checks in different weather can be compared.
  * **Average run time** per switch-on.
  * **History of the last 6 checks** with their figures and the changes made. The AI can judge whether a change helped and otherwise undo it. Resetting an area or editing a learned value by hand deletes its history.
* Adjustable parameters: switch-on and switch-off hysteresis, overshoot factor, lead time factor, sun factor, window delay, recovery time correction, `puffer` and `theta`. Every value is clamped to minimum, maximum and a maximum change per check (all configurable).
* **Asking less often:** the check interval doubles after every check without relevant change and without comfort problems (up to the maximum interval). It returns to the base interval if it was too cold, an area was clearly overheated (more than 0.5 Kelvin hours per day, pro rata), the AI changed something significant, or you change the target or settings. A check already planned survives the nightly run; after a no-heating day the next check follows after the base interval, and if an area was too cold since the last check, the next check is brought forward.
* **Costs:** token usage times the configured prices. Every call is estimated beforehand; once the monthly budget is reached there are no calls until the month changes.
* **Failures:** on errors, timeouts or invalid answers the control continues with the last learned values. The API key never appears in the log and is redacted in diagnostics.

### Heat meter

Optional. With a heat meter the AI sees the heat actually used instead of only the run time of the circuits.

* Consumption is always taken **between two meter readings**, never between arbitrary points in time. With every reading the integration keeps the heating demand accumulated until then (Kelvin hours of target minus outdoor temperature, mean over the areas). Consumption and demand thus cover exactly the same span, even if the meter reports only every few hours and in coarse steps.
* **AI check:** `heat` with kWh, hours and `kwh_per_kh` (kWh per Kelvin hour of demand, the best efficiency measure) since the last check; spans under one hour are not reported. `kwh_per_kh` is also in the check history.
* **Nightly run:** kWh per past heating day in the history.
* **Dashboard:** card **Heat** with today, yesterday, this month and the time of the last meter reading. A day runs from the last reading before midnight to the last one before the next midnight; "yesterday" is missing after a skipped day.
* If the reading falls (new meter) or another meter is chosen, counting starts again.

### Ventilation recommendation

Per area (also without heating circuit) from the absolute humidity inside and outside (or of a reference room):
*Ventilate now* (humidity above threshold and outside air drier), *Ventilation useful* (cools while not heating; within the heating period only if the room is clearly above its target; never below the optional minimum temperature and never if the outside air would raise the relative humidity of the room above its threshold), *Do not ventilate*, *Close window* (open but useless), *Ventilation blocked* (block entity active, e.g. air conditioner) and *All fine*.

## Installation via HACS

1. Open HACS, choose **Custom repositories** in the top right menu.
2. Add repository `https://github.com/Jumpmaster2/AI-Heating-Assistant`, type **Integration**.
3. Download **AI Heating Assistant** and restart Home Assistant.
4. **Settings > Devices & services > Add integration > AI Heating Assistant**.

Requirements: Home Assistant 2026.10 or newer. For the AI an Anthropic API key (optional, without a key only the local control runs).

## Configuration

### Dashboard

After the setup the sidebar has the page **AI Heating Assistant** (administrators only). **Configure** under Settings > Devices & services leads straight there.

* **Overview:** heating day with phase and reason, manual heating day (automatic, heat today, no heating today), all areas with temperature, target, status and ventilation recommendation (click opens the thermostat), switch AI active, last and next AI check, next nightly run, last heating day decision with its source (AI, rule, both agree), AI costs this month, notes (missing entities, last AI error, budget reached) and a summary of the settings.
* **Heating areas:** all areas as a table; click to edit, add and delete.
* **Learned values:** a compact tile per area with a heating circuit with learning progress, heat-up and cooling rate, dead time, overshoot, recovery after airing, outdoor and sun influence; the control parameters the AI may adjust can be expanded. Plus the heating day rule (`theta`, evaluated days). The pencil opens the learned values for editing.
* **General, Emergency & ventilation, AI, Heating day decision:** all settings by topic in cards, each card is saved on its own. **AI** also holds the API key (checked before saving, the stored key is never shown) and the AI limits.

The setup itself is still a dialog.

### Setup (global)

Temperature sensors may report °C, °F or K; without a unit the unit system of Home Assistant applies. Internally everything is calculated in °C, and all temperatures in the settings (targets, frost protection, `theta`) are entered in °C. The thermostats show values in the unit system of Home Assistant.

| Option | Default | Meaning |
|---|---|---|
| Outdoor temperature sensor | | e.g. `sensor.outdoor_temperature` |
| Outdoor humidity sensor | | optional, for the ventilation recommendation |
| Weather entity | | optional, forecast for the nightly run and the expected sun |
| PV power sensor | | optional, sunshine indicator (W or kW) |
| PV forecast sensor | | optional, only with the PV power sensor: energy of the next hour (Wh or kWh) or power in one hour (W or kW); without it the weather forecast is used |
| Heat meter | | optional, meter reading of the circuits controlled here (Wh, kWh, MWh, MJ or GJ); seldom and coarse readings are fine, see [Heat meter](#heat-meter) |
| Heating period | 01.10. to 31.03. | format DD.MM. |
| Frost protection | 7 °C | always applies |
| Vacation entities | | "on" = vacation |
| Vacation temperature | 18 °C | for all areas |
| Return date/time | | optional, for preheating |
| Preheat reserve | 30 min | |
| Start value `theta` | 16 °C | heating day rule; only during setup, afterwards the learned value is edited |
| API key, model | Claude Opus 5.5 | changeable, custom model names possible |
| Nightly run | 03:00 | |
| Monthly budget | 5 € | |

### Settings

* **General:** sensors, heating period and frost protection, vacation as above.
* **Emergency rule:** on, 1 K below target (expected after the lead time, at least the switch-on hysteresis), 45 min, windows unchanged for 30 min.
* **Ventilation:** minimum drying advantage 0.8 g/m³, outside at most 4 K warmer, minimum cooling advantage 1 K, cooling within the heating period only from 1 K above target, optionally cooling only from a fixed room temperature (e.g. 23.5 °C, all year, off by default), night 20 to 8 h.
* **AI:** model, effort (default low), nightly run, check interval 4 h, maximum interval 48 h, budget, prices in €/million tokens (input, output, cache write, cache read; prefilled with the model's list price), maximum output tokens.
* **AI limits:** minimum, maximum and largest change per check for every parameter.
* **Heating day decision:** learned `theta` (editable), evaluation thresholds, learning steps, conditions for phase changes.

Change the API key in the dashboard under **AI** or via **Reconfigure**.

### Heating areas

In the dashboard under **Heating areas** (or under the integration with **Add heating area**). Per area:

| Option | Default |
|---|---|
| Name | |
| Temperature, humidity and window sensors | e.g. `sensor.living_room_temperature`, `binary_sensor.living_room_window` |
| Heating circuit switch | e.g. `switch.heating_circuit_1`; empty = ventilation recommendation only |
| Initial, minimum and maximum target | 21 / 16 / 24 °C |
| Minimum on and off time | 10 / 10 min (fixed) |
| Start values window delay, recovery time, dead time, puffer | 5 min, 30 min, 30 min, 0.7 K; only when the area is created |
| Humidity threshold | 60 % |
| Reference temperature and humidity | optional, instead of outdoor (room without its own window) |
| Ventilation block entity | optional |

Start values (including `theta`) are only set during setup or when an area is created and apply until something has been learned. They cannot be changed afterwards; instead an area shows the values the control currently uses under **Learned values** (window delay, recovery time, dead time, puffer), and the learned `theta` is under **Heating day decision**. A change there replaces the learned or AI-adjusted value, learning continues from there, and the logbook records it.

## Entities

Global (device "AI Heating Assistant"):

* Binary sensor **Heating day** (with source, reason, confidence, phase, time of the decision `decided_at` and next nightly run `next_decision`)
* Sensors **Decision phase**, **Last AI check** (with summary and last error), **Next AI check**, **AI costs this month**
* Sensor **Heat today** (only with a heat meter, kWh; attributes `yesterday`, `month`, `last_month`, `meter_reading_at`)
* Switch **AI enabled**
* Select **Heating day override** (automatic, heat today, no heating today)

Per heating area (own device):

* **Thermostat** (climate), attributes include `predicted_temperature`, `expected_peak` and `expected_pv_kw` (PV power expected over the lead time)
* Sensors **Status**, **Heat-up rate**, **Cooling rate**, **Overshoot after switch-off**, **Dead time**, **Recovery time after airing**, **Outdoor influence**, **Sun influence**, **Learning progress**
* Sensor **Ventilation recommendation** and binary sensor **Ventilation recommended** (also for areas without heating circuit)

All important decisions and every AI adjustment with its reason are written to the **logbook**. The integration does not send notifications.

## Services

| Service | Purpose |
|---|---|
| `ai_heating_assistant.export_parameters` | learned values and parameters as JSON (service response) |
| `ai_heating_assistant.import_parameters` | set learned values and parameters from JSON (e.g. start values) |
| `ai_heating_assistant.reset_learned` | reset learned values of areas to the start values, optionally the parameters too |
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

The dashboard texts (`frontend/labels.js`) are generated from the translation files. After changing `translations/*.json` run `python scripts/build_labels.py` once (a test checks this).

The control and learning logic in `custom_components/ai_heating_assistant/logic/` does not depend on Home Assistant and can be tested on its own. The Home Assistant tests need Linux or macOS (they also run in GitHub Actions).

## License

MIT, see [LICENSE](LICENSE).
