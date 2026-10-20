// Generated from the translation files by scripts/build_labels.py, do not edit by hand.
export const LABELS = {
 "de": {
  "fields": {
   "outdoor_temperature": [
    "Außentemperatursensor",
    "Sensor für die Außentemperatur (z. B. ein Helfer, der mehrere Sensoren zusammenfasst). Ohne ihn gilt die aktuelle Temperatur der Wetter-Entität."
   ],
   "outdoor_humidity": [
    "Außenfeuchtesensor",
    "Optional. Für die Lüftungsempfehlung; ohne Sensor wird die Luftfeuchte der Wetter-Entität genutzt."
   ],
   "weather": [
    "Wetter-Entität",
    "Optional, aber empfohlen. Die Vorhersage wird für die nächtliche Heiztag-Entscheidung und die Sonnenprognose genutzt. Ohne Außensensor gilt ihre aktuelle Temperatur als Außentemperatur."
   ],
   "pv_power": [
    "PV-Leistungssensor",
    "Optional. PV-Leistung (W oder kW) als Indikator für Sonne. Daraus wird der Sonneneinfluss je Bereich gelernt."
   ],
   "pv_forecast": [
    "PV-Prognosesensor",
    "Optional, nur zusammen mit dem PV-Leistungssensor. Erwartete PV-Energie der nächsten Stunde (Wh oder kWh, z. B. Forecast.Solar) oder erwartete Leistung in einer Stunde (W oder kW). Ohne diesen Sensor wird die Sonne aus der stündlichen Wettervorhersage und dem Sonnenstand geschätzt."
   ],
   "heat_meter": [
    "Wärmezähler",
    "Optional. Zählerstand des Wärmezählers der hier geregelten Heizkreise (Wh, kWh, MWh, MJ oder GJ, z. B. total_increasing). Die KI sieht dann die gemessene Wärme, außerdem steht sie im Dashboard. Seltene und grobe Werte sind kein Problem."
   ],
   "season_start": [
    "Beginn der Heizperiode (TT.MM.)",
    "Außerhalb der Heizperiode bleiben alle Kreise aus (nur Frostschutz) und die KI wird nicht gefragt."
   ],
   "season_end": [
    "Ende der Heizperiode (TT.MM.)",
    "Letzter Tag der Heizperiode, darf im Folgejahr liegen (z. B. 31.03.)."
   ],
   "frost_temperature": [
    "Frostschutz-Mindesttemperatur",
    "Gilt immer, auch außerhalb der Heizperiode und bei ausgeschaltetem Thermostat."
   ],
   "forecast_trust": [
    "Vertrauen in die Sonnenprognose",
    "Anteil der erwarteten PV-Leistung, auf den sich die Regelung beim Zurückhalten verlässt (100 % = volle Prognose, 0 % = nur die aktuelle PV-Leistung zählt)."
   ],
   "season_start_day": [
    "Heizperiode beginnt: Tag",
    "Ab diesem Datum darf geheizt werden (z. B. 1. Oktober)."
   ],
   "season_start_month": [
    "Heizperiode beginnt: Monat",
    ""
   ],
   "season_end_day": [
    "Heizperiode endet: Tag",
    "Letzter Tag der Heizperiode (z. B. 31. März); die Periode darf über den Jahreswechsel gehen."
   ],
   "season_end_month": [
    "Heizperiode endet: Monat",
    ""
   ],
   "vacation_entities": [
    "Urlaubs-Entitäten",
    "Ist eine dieser Entitäten 'an', gilt Urlaub (z. B. ein input_boolean oder ein Kalender)."
   ],
   "vacation_temperature": [
    "Urlaubstemperatur",
    "Sollwert für alle Bereiche im Urlaub (z. B. 17 °C)."
   ],
   "return_entity": [
    "Rückkehr Datum/Uhrzeit",
    "Optional: input_datetime, Zeitstempel-Sensor oder datetime-Entität. Es wird so rechtzeitig vorgeheizt (gelernte Aufheizzeit), dass bei Rückkehr der normale Sollwert erreicht ist."
   ],
   "preheat_reserve": [
    "Vorheiz-Reserve",
    "Zusätzliche Zeit zur berechneten Vorheizzeit (z. B. 30 min)."
   ],
   "emergency_enabled": [
    "Notfallregel",
    "An Tagen ohne Heizbetrieb darf ein Bereich trotzdem heizen, wenn die nach der Vorlaufzeit erwartete Temperatur lange und deutlich unter dem Sollwert liegt, ohne dass gelüftet wurde."
   ],
   "emergency_delta": [
    "Notfall: unter Sollwert um",
    "Wie weit die nach der Vorlaufzeit erwartete Temperatur unter dem Sollwert liegen muss (mindestens die Einschalthysterese)."
   ],
   "emergency_duration": [
    "Notfall: Dauer",
    "Wie lange die erwartete Temperatur so tief bleiben muss (z. B. 45 min)."
   ],
   "emergency_window_quiet": [
    "Notfall: keine Fensteränderung seit",
    "Lüften zählt nicht: die Fenster dürfen sich so lange nicht verändert haben."
   ],
   "force_on_below": [
    "Immer heizen unter Sollwert um",
    "So weit unter dem Sollwert heizt der Kreis unabhängig von jeder Vorhersage und der erwarteten Sonne."
   ],
   "ventilation_min_ah_advantage": [
    "Mindestvorteil absolute Feuchte",
    "Absolute Feuchte ist der Wassergehalt der Luft in g/m³, unabhängig von der Temperatur. Die Außenluft muss mindestens so viel weniger Wasser enthalten für 'Jetzt lüften' (z. B. 0,8 g/m³)."
   ],
   "ventilation_max_reference_excess": [
    "Außen höchstens wärmer um",
    "Trocknen wird nicht empfohlen, wenn es außen um mehr als diesen Wert wärmer ist als innen."
   ],
   "ventilation_min_cooling_advantage": [
    "Mindest-Kühlvorteil",
    "'Lüften sinnvoll', wenn es innen mindestens so viel wärmer ist als außen (nicht während Heizbetrieb)."
   ],
   "ventilation_cooling_margin": [
    "Mindestabstand über Sollwert für Kühlen",
    "In der Heizperiode wird 'Lüften sinnvoll' (Kühlen) nur empfohlen, wenn der Raum mindestens so viel wärmer ist als sein Sollwert. Außerhalb der Heizperiode gilt das nicht. Bereiche ohne Heizkreis nutzen ihren Start-Sollwert."
   ],
   "ventilation_cooling_min_temp": [
    "Kühlen erst ab Raumtemperatur",
    "'Lüften sinnvoll' (Kühlen) erst ab dieser Raumtemperatur, ganzjährig. 0 = aus. Zusätzlich wird Kühlen nie empfohlen, wenn die Außenluft die relative Feuchte des Raums über seine Feuchte-Schwelle bringen würde."
   ],
   "night_start_hour": [
    "Nacht beginnt um",
    "Bei einem anderen Raum als Referenz zählt der Kühlvorteil nur nachts."
   ],
   "night_end_hour": [
    "Nacht endet um",
    "Ende der Nacht (Uhrzeit, z. B. 08:00)."
   ],
   "model": [
    "Claude-Modell",
    "Modell für alle KI-Abfragen. Die Preise sind Vorschläge für das gewählte Modell und änderbar."
   ],
   "effort": [
    "Denkaufwand",
    "Claude denkt vor der Antwort nach. Mehr Aufwand kann bessere Antworten geben, braucht aber mehr Tokens, die als Ausgabe abgerechnet werden. 'auto' überlässt es dem Modell."
   ],
   "nightly_time": [
    "Uhrzeit des Nachtlaufs",
    "Tägliche Entscheidung, ob heute geheizt wird (zugleich Beginn des bewerteten Tages)."
   ],
   "check_interval": [
    "Prüfintervall",
    "Grundintervall der periodischen KI-Prüfung an Heiztagen (z. B. 4 h). Es verdoppelt sich nach jeder Prüfung ohne relevante Änderung."
   ],
   "check_max_interval": [
    "Maximales Prüfintervall",
    "Obergrenze für das verdoppelte Intervall (z. B. 48 h)."
   ],
   "monthly_budget": [
    "Monatsbudget",
    "In US-Dollar, wie Anthropic abrechnet. Keine KI-Abfragen mehr, sobald die Kosten des Monats diesen Wert erreichen (bis zum Monatswechsel). Eine Prüfung kostet meist wenige Cent, 5 USD reichen also für etwa 100 bis 200 Abfragen."
   ],
   "price_input": [
    "Preis Eingabe-Tokens",
    "US-Dollar pro Million Tokens, wie Anthropic abrechnet."
   ],
   "price_output": [
    "Preis Ausgabe-Tokens",
    "US-Dollar pro Million Tokens, wie Anthropic abrechnet (Denken zählt als Ausgabe)."
   ],
   "price_cache_write": [
    "Preis Cache schreiben",
    "US-Dollar pro Million Tokens, wie Anthropic abrechnet."
   ],
   "price_cache_read": [
    "Preis Cache lesen",
    "US-Dollar pro Million Tokens, wie Anthropic abrechnet."
   ],
   "max_output_tokens": [
    "Maximale Ausgabe-Tokens",
    "Obergrenze je Antwort, Denken eingeschlossen (zu niedrig schneidet Antworten ab; sie sind bezahlt, werden aber verworfen). Auch Obergrenze der Kostenschätzung vor einer Abfrage."
   ],
   "theta": [
    "Heizgrenze theta (gelernt)",
    "Aktuelle Schwelle der Heiztag-Regel: liegt die Prognose-Höchsttemperatur darunter, wird geheizt. Eine Änderung ersetzt den gelernten Wert; danach wird von hier aus weiter gelernt."
   ],
   "too_cold_margin": [
    "Zu kalt unter Sollwert um",
    "Bewertung: ein Bereich gilt als zu kalt unter Sollwert minus diesem Wert (Lüften ausgenommen)."
   ],
   "too_cold_minutes": [
    "Minuten zu kalt für Heizbedarf",
    "Bewertung: so viele Minuten zu kalt bedeuten Heizbedarf."
   ],
   "theta_step_up": [
    "Heizgrenze: Schritt nach oben",
    "Nach Fehler A, also wenn es an einem Tag ohne Heizen zu kalt wurde (z. B. 1,0 K)."
   ],
   "theta_step_down": [
    "Heizgrenze: Schritt nach unten",
    "Nach Fehler B, also wenn geheizt wurde, obwohl es nicht nötig war (z. B. 1,0 K)."
   ],
   "puffer_step_up": [
    "Reserve über Sollwert: Schritt nach oben",
    "Nach Fehler A für den kalten Bereich."
   ],
   "puffer_step_down": [
    "Reserve über Sollwert: Schritt nach unten",
    "Nach Fehler B."
   ],
   "phase_shared_min_days": [
    "Tage bis gemeinsame Entscheidung",
    "Wer über den Heiztag entscheidet: zuerst führt die KI, dann entscheiden KI und Regel gemeinsam, zuletzt führt die Regel. 'KI führt' -> 'gemeinsam' nach so vielen bewerteten Tagen (z. B. 14)."
   ],
   "phase_shared_min_agreement": [
    "Übereinstimmung für gemeinsam",
    "Mindest-Übereinstimmung von Regel und KI."
   ],
   "phase_rule_min_days": [
    "Tage bis Regel führt",
    "Phase 'gemeinsam' -> 'Regel führt' nach so vielen Tagen in 'gemeinsam'."
   ],
   "phase_rule_min_agreement": [
    "Übereinstimmung für Regel führt",
    "Mindest-Übereinstimmung von Regel und KI."
   ],
   "phase_max_rule_errors": [
    "Erlaubte Regelfehler",
    "Höchstens so viele Regelfehler im Zeitraum für einen Phasenwechsel."
   ],
   "phase_fallback_errors_7d": [
    "Regelfehler in 7 Tagen für Rückfall",
    "So viele Regelfehler in 7 Tagen führen eine Phase zurück."
   ],
   "phase_ai_check_every_days": [
    "KI-Kontrolle alle",
    "Wenn die Regel führt und sicher ist, wird die KI trotzdem alle so viele Tage gefragt."
   ],
   "api_key": [
    "Anthropic API-Key",
    "Optional. Ohne Key läuft nur die lokale Regelung. Der Key wird nur in Home Assistant gespeichert und nie protokolliert."
   ],
   "name": [
    "Name",
    "Name des Bereichs, auch für das Gerät und seine Entitäten."
   ],
   "temperature_sensor": [
    "Temperatursensor",
    "Raumtemperatur des Bereichs."
   ],
   "humidity_sensor": [
    "Feuchtesensor",
    "Relative Luftfeuchte, nötig für die Lüftungsempfehlung."
   ],
   "window_sensors": [
    "Fenstersensoren",
    "Ein oder mehrere Fenster-/Türkontakte ('an' = offen)."
   ],
   "heater_switch": [
    "Heizkreis-Schalter",
    "Schalter des Stellantriebs (z. B. ein Relais). Leer lassen für einen Bereich nur mit Lüftungsempfehlung."
   ],
   "default_target": [
    "Start-Sollwert",
    "Sollwert, bis du ihn an der Thermostatkarte änderst."
   ],
   "min_target": [
    "Kleinster Sollwert",
    "Kleinster Wert der Thermostatkarte."
   ],
   "max_target": [
    "Größter Sollwert",
    "Größter Wert der Thermostatkarte."
   ],
   "min_on_time": [
    "Mindest-Einschaltzeit",
    "Wird immer eingehalten (schont den Stellantrieb). Wird nicht gelernt."
   ],
   "min_off_time": [
    "Mindest-Ausschaltzeit",
    "Wird immer eingehalten. Wird nicht gelernt."
   ],
   "heating_type": [
    "Heizungsart",
    "Wie der Kreis heizt. Ein Fußboden speichert Wärme über Stunden, Heizkörper reagieren in Minuten; die KI beurteilt die gelernten Werte entsprechend."
   ],
   "window_delay": [
    "Fensterverzögerung (Startwert)",
    "So lange offen pausiert die Heizung. Die KI darf den Wert anpassen."
   ],
   "recovery_time": [
    "Erholungszeit nach Lüften (Startwert)",
    "Nach dem Schließen wird so lange gewartet, weil Estrich und Wände den Raum oft selbst aufheizen. Wird danach gelernt."
   ],
   "dead_time": [
    "Totzeit bis der Raum wärmer wird (Startwert)",
    "Zeit vom Einschalten, bis der Raum wärmer wird; bei Fußbodenheizung oft 30-90 min, bei Heizkörpern 5-20 min. Wird danach gelernt."
   ],
   "puffer": [
    "Reserve über Sollwert (Startwert)",
    "Heiztag-Regel: wie weit ein Bereich beim Nachtlauf über dem Sollwert liegen muss, um einen Tag ohne Heizen zu überstehen (z. B. 0,7 K). Wird danach gelernt."
   ],
   "ventilation_rh_threshold": [
    "Feuchte-Schwelle",
    "Relative Feuchte, ab der Lüften empfohlen wird (z. B. 65 % für Bäder)."
   ],
   "reference_temperature": [
    "Referenz-Temperatur statt außen",
    "Optional, für Räume, die über einen anderen Raum gelüftet werden."
   ],
   "reference_humidity": [
    "Referenz-Feuchte statt außen",
    "Zusammen mit der Referenz-Temperatur nötig."
   ],
   "ventilation_block_entity": [
    "Lüftungs-Sperr-Entität",
    "Optional. Solange sie sperrt, wird kein Lüften empfohlen: eine Abdeckung (cover), solange sie geschlossen ist (z. B. Beschattung unten), eine Klima-Entität oder ein Warmwasserbereiter, solange nicht aus (z. B. Klimaanlage läuft), ein Schalter, Binärsensor, Ventilator o. Ä., solange an."
   ]
  },
  "learned": {
   "window_delay": [
    "Fensterverzögerung",
    "So lange offen pausiert die Heizung. Die KI darf den Wert anpassen."
   ],
   "recovery_time": [
    "Erholungszeit nach Lüften",
    "Gelernte Wartezeit nach dem Schließen der Fenster."
   ],
   "dead_time": [
    "Totzeit bis der Raum wärmer wird",
    "Gelernte Zeit, bis der Raum nach dem Einschalten wärmer wird."
   ],
   "puffer": [
    "Reserve über Sollwert",
    "Heiztag-Regel: nötiger Abstand über dem Sollwert beim Nachtlauf (gelernt)."
   ]
  },
  "sections": {
   "sensors": [
    "Sensoren",
    ""
   ],
   "heating": [
    "Heizkreis",
    ""
   ],
   "start_values": [
    "Startwerte (werden gelernt)",
    "Nur beim Anlegen des Bereichs. Danach werden die gelernten Werte bearbeitet."
   ],
   "ventilation": [
    "Lüftung",
    ""
   ],
   "learned_values": [
    "Gelernte Werte",
    "Werte, mit denen gerade geregelt wird. Eine Änderung ersetzt den gelernten bzw. von der KI angepassten Wert; danach wird von hier aus weiter gelernt."
   ]
  },
  "limits": {
   "hysteresis_on": "Einschalt-Hysterese",
   "hysteresis_off": "Ausschalt-Hysterese",
   "overshoot_factor": "Faktor Überschwingen",
   "lead_factor": "Faktor Vorlauf",
   "sun_factor": "Sonnenfaktor",
   "window_delay_min": "Fensterverzögerung",
   "recovery_bias_min": "Korrektur Erholungszeit",
   "puffer": "Reserve über Sollwert (puffer)",
   "theta": "Heizgrenze (theta)"
  },
  "limit_columns": {
   "min": "Minimum",
   "max": "Maximum",
   "step": "Max. Änderung je Prüfung"
  },
  "errors": {
   "invalid_day_month": "Bitte ein gültiges Datum angeben (TT.MM., z. B. 01.10.); einen Tag wie den 31.02. gibt es nicht.",
   "invalid_auth": "Anthropic hat den API-Key abgelehnt. Prüfe ihn unter console.anthropic.com > API Keys und füge ihn ohne Leerzeichen ein. Ohne Key läuft die lokale Regelung weiter.",
   "cannot_connect": "Anthropic ist nicht erreichbar. Prüfe Internetverbindung, Proxy und Firewall. Der Key wurde nicht gespeichert.",
   "max_below_base": "Das maximale Intervall muss mindestens so groß sein wie das Prüfintervall (z. B. alle 4 h prüfen, höchstens alle 48 h).",
   "min_above_max": "Bei jedem Parameter darf das Minimum nicht über dem Maximum liegen. Bitte die Grenzen des betroffenen Parameters korrigieren.",
   "outdoor_required": "Bitte einen Außentemperatursensor oder eine Wetter-Entität wählen."
  },
  "area_errors": {
   "name_required": "Bitte einen Namen angeben.",
   "name_in_use": "Ein anderer Bereich heißt schon so. Bitte einen eindeutigen Namen wählen (Export und Import finden Bereiche über den Namen).",
   "switch_in_use": "Dieser Schalter steuert bereits einen anderen Heizbereich. Jeder Heizkreis gehört zu genau einem Bereich: wähle einen anderen Schalter oder entferne ihn zuerst aus dem anderen Bereich.",
   "min_above_max": "Der kleinste Sollwert muss kleiner sein als der größte. Bitte einen der beiden Werte ändern (beide in °C).",
   "target_out_of_range": "Der Start-Sollwert muss zwischen dem kleinsten und dem größten Sollwert liegen. Bitte ihn oder die Grenzen anpassen.",
   "reference_incomplete": "Referenztemperatur und Referenzfeuchte gehen nur zusammen: beide Sensoren wählen oder keinen."
  },
  "states": {
   "status": {
    "off": "Aus",
    "out_of_season": "Außerhalb Heizperiode",
    "no_heating_day": "Kein Heiztag",
    "idle": "Bereit",
    "heating": "Heizt",
    "window_open": "Fenster offen",
    "recovery": "Erholung nach Lüften",
    "frost_protection": "Frostschutz",
    "vacation": "Urlaub",
    "preheat": "Vorheizen zur Rückkehr",
    "emergency": "Notfallregel",
    "sensor_error": "Sensorfehler",
    "actuator_unavailable": "Aktor nicht erreichbar",
    "no_circuit": "Kein Heizkreis"
   },
   "ventilation": {
    "unknown": "Unbekannt",
    "close_window": "Fenster schließen",
    "ventilate_now": "Jetzt lüften",
    "ventilation_useful": "Lüften sinnvoll",
    "do_not_ventilate": "Nicht lüften",
    "blocked": "Lüften blockiert",
    "optimal": "Alles optimal"
   },
   "phase": {
    "ai_leads": "KI führt",
    "shared": "Gemeinsam",
    "rule_leads": "Regel führt"
   },
   "override": {
    "auto": "Automatik",
    "heat_today": "Heute heizen",
    "off_today": "Heute nicht heizen"
   }
  },
  "effort": {
   "auto": "Auto (Modell-Standard)",
   "low": "Niedrig",
   "medium": "Mittel",
   "high": "Hoch"
  },
  "heating_type": {
   "underfloor": "Fußbodenheizung",
   "radiator": "Heizkörper",
   "other": "Andere (z. B. Wandheizung)"
  }
 },
 "en": {
  "fields": {
   "outdoor_temperature": [
    "Outdoor temperature sensor",
    "Sensor for the outdoor temperature (e.g. a helper combining several sensors). Without it the current temperature of the weather entity is used."
   ],
   "outdoor_humidity": [
    "Outdoor humidity sensor",
    "Optional. Needed for the ventilation recommendation; without it the humidity of the weather entity is used."
   ],
   "weather": [
    "Weather entity",
    "Optional but recommended. Its forecast is used for the nightly heating day decision and the expected sun. Without an outdoor sensor its current temperature is the outdoor temperature."
   ],
   "pv_power": [
    "PV power sensor",
    "Optional. PV power (W or kW) as an indicator for sunshine. The solar gain per area is learned from it."
   ],
   "pv_forecast": [
    "PV forecast sensor",
    "Optional, only together with the PV power sensor. Expected PV energy of the next hour (Wh or kWh, e.g. Forecast.Solar) or expected power in one hour (W or kW). Without it the sun is estimated from the hourly weather forecast and the sun position."
   ],
   "heat_meter": [
    "Heat meter",
    "Optional. Meter reading of the heat meter of the circuits controlled here (Wh, kWh, MWh, MJ or GJ, e.g. total_increasing). The AI then sees the measured heat; it is also shown in the dashboard. Seldom and coarse readings are fine."
   ],
   "season_start": [
    "Heating period start (DD.MM.)",
    "Outside the heating period all circuits stay off (frost protection only) and the AI is not asked."
   ],
   "season_end": [
    "Heating period end (DD.MM.)",
    "Last day of the heating period, may be in the next year (e.g. 31.03.)."
   ],
   "frost_temperature": [
    "Frost protection temperature",
    "Always applies, also outside the heating period and with a switched-off thermostat."
   ],
   "forecast_trust": [
    "Trust in the sun forecast",
    "Share of the expected PV power the control relies on when it holds back heating (100 % = full forecast, 0 % = only the current PV power counts)."
   ],
   "season_start_day": [
    "Heating period starts: day",
    "Heating is possible from this date (e.g. 1 October)."
   ],
   "season_start_month": [
    "Heating period starts: month",
    ""
   ],
   "season_end_day": [
    "Heating period ends: day",
    "Last day of the heating period (e.g. 31 March); the period may span the turn of the year."
   ],
   "season_end_month": [
    "Heating period ends: month",
    ""
   ],
   "vacation_entities": [
    "Vacation entities",
    "Any of these entities being 'on' means vacation (e.g. an input_boolean or a calendar)."
   ],
   "vacation_temperature": [
    "Vacation temperature",
    "Target for all areas during vacation (e.g. 17 °C)."
   ],
   "return_entity": [
    "Return date/time",
    "Optional input_datetime, timestamp sensor or datetime entity. Heating starts early enough (learned heat-up time) to reach the normal target on return."
   ],
   "preheat_reserve": [
    "Preheat reserve",
    "Additional time added to the calculated preheating time (e.g. 30 min)."
   ],
   "emergency_enabled": [
    "Emergency rule",
    "On days without heating, an area may still heat if the temperature expected after the lead time is long and clearly below its target, without airing."
   ],
   "emergency_delta": [
    "Emergency: below target by",
    "How far below the target the temperature expected after the lead time has to be (at least the switch-on hysteresis)."
   ],
   "emergency_duration": [
    "Emergency: duration",
    "How long the expected temperature has to stay that low (e.g. 45 min)."
   ],
   "emergency_window_quiet": [
    "Emergency: no window change for",
    "Airing does not count: windows must not have changed for this time."
   ],
   "force_on_below": [
    "Always heat below target by",
    "Below target by this much the circuit heats regardless of every prediction and the expected sun."
   ],
   "ventilation_min_ah_advantage": [
    "Minimum drying advantage",
    "Absolute humidity is the water content of the air in g/m³, independent of temperature. Outside air must contain at least this much less water for 'ventilate now' (e.g. 0.8 g/m³)."
   ],
   "ventilation_max_reference_excess": [
    "Maximum outside warmer by",
    "Drying is not recommended if outside is warmer than inside by more than this."
   ],
   "ventilation_min_cooling_advantage": [
    "Minimum cooling advantage",
    "'Ventilation useful' if inside is warmer than outside by at least this (not while heating)."
   ],
   "ventilation_cooling_margin": [
    "Minimum distance above target for cooling",
    "Within the heating period 'ventilation useful' (cooling) is only recommended if the room is at least this much warmer than its target. Not used outside the heating period. Areas without a heating circuit use their initial target."
   ],
   "ventilation_cooling_min_temp": [
    "Cool only from room temperature",
    "'Ventilation useful' (cooling) only from this room temperature on, all year. 0 = off. In addition cooling is never recommended if the outside air would raise the relative humidity of the room above its humidity threshold."
   ],
   "night_start_hour": [
    "Night starts at",
    "Used when the reference is another room: cooling advantage only counts at night."
   ],
   "night_end_hour": [
    "Night ends at",
    "End of the night (time, e.g. 08:00)."
   ],
   "model": [
    "Claude model",
    "Model for all AI calls. Prices below are suggestions for the selected model and can be changed."
   ],
   "effort": [
    "Thinking effort",
    "Claude thinks before it answers. More effort can give better answers but uses more tokens, which are billed as output. 'auto' leaves it to the model."
   ],
   "nightly_time": [
    "Time of the nightly run",
    "Daily decision whether heating is needed today (also the start of the evaluated day)."
   ],
   "check_interval": [
    "Check interval",
    "Base interval of the periodic AI check on heating days (e.g. 4 h). It doubles after every check without relevant change."
   ],
   "check_max_interval": [
    "Maximum check interval",
    "Upper limit for the doubled interval (e.g. 48 h)."
   ],
   "monthly_budget": [
    "Monthly budget",
    "In US dollars, as Anthropic bills. No AI calls once the costs of the month reach this value (until the month changes). A check usually costs a few cents, so 5 USD allow about 100 to 200 calls."
   ],
   "price_input": [
    "Price input tokens",
    "US dollars per million tokens, as Anthropic bills."
   ],
   "price_output": [
    "Price output tokens",
    "US dollars per million tokens, as Anthropic bills (thinking counts as output)."
   ],
   "price_cache_write": [
    "Price cache write",
    "US dollars per million tokens, as Anthropic bills."
   ],
   "price_cache_read": [
    "Price cache read",
    "US dollars per million tokens, as Anthropic bills."
   ],
   "max_output_tokens": [
    "Maximum output tokens",
    "Upper limit per answer, thinking included (too low cuts answers off, they are paid but discarded). Also the upper bound of the cost estimate before a call."
   ],
   "theta": [
    "Heating threshold theta (learned)",
    "Current threshold of the heating day rule: if the forecast maximum is below it, heating is needed. A change replaces the learned value; learning continues from there."
   ],
   "too_cold_margin": [
    "Too cold below target by",
    "Evaluation: an area counts as too cold below target minus this (airing excluded)."
   ],
   "too_cold_minutes": [
    "Too cold minutes for heating need",
    "Evaluation: this many minutes too cold mean heating was needed."
   ],
   "theta_step_up": [
    "Heating threshold: step up",
    "After error A, i.e. it got too cold on a day without heating (e.g. 1.0 K)."
   ],
   "theta_step_down": [
    "Heating threshold: step down",
    "After error B, i.e. heating ran although it was not needed (e.g. 1.0 K)."
   ],
   "puffer_step_up": [
    "Margin above target: step up",
    "After error A for the cold area."
   ],
   "puffer_step_down": [
    "Margin above target: step down",
    "After error B."
   ],
   "phase_shared_min_days": [
    "Days until shared decision",
    "Who decides the heating day: first the AI leads, then AI and rule decide together, finally the rule leads. 'AI leads' -> 'shared' after this many evaluated days (e.g. 14)."
   ],
   "phase_shared_min_agreement": [
    "Agreement for shared decision",
    "Minimum agreement of rule and AI."
   ],
   "phase_rule_min_days": [
    "Days until rule leads",
    "Phase 'shared' -> 'rule leads' after this many days in phase 'shared'."
   ],
   "phase_rule_min_agreement": [
    "Agreement for rule leads",
    "Minimum agreement of rule and AI."
   ],
   "phase_max_rule_errors": [
    "Allowed rule errors",
    "Maximum rule errors within the period for a phase change."
   ],
   "phase_fallback_errors_7d": [
    "Rule errors in 7 days for fallback",
    "This many rule errors within 7 days move back one phase."
   ],
   "phase_ai_check_every_days": [
    "AI control check every",
    "When the rule leads and is sure, the AI is still asked every this many days."
   ],
   "api_key": [
    "Anthropic API key",
    "Optional. Without a key the local control runs alone. The key is only stored in Home Assistant and never logged."
   ],
   "name": [
    "Name",
    "Name of the area, also used for the device and its entities."
   ],
   "temperature_sensor": [
    "Temperature sensor",
    "Room temperature of the area."
   ],
   "humidity_sensor": [
    "Humidity sensor",
    "Relative humidity, needed for the ventilation recommendation."
   ],
   "window_sensors": [
    "Window sensors",
    "One or more window/door contacts ('on' = open)."
   ],
   "heater_switch": [
    "Heating circuit switch",
    "Switch of the actuator (e.g. a relay). Leave empty for an area with ventilation recommendation only."
   ],
   "default_target": [
    "Initial target temperature",
    "Target until you change it on the thermostat card."
   ],
   "min_target": [
    "Minimum target",
    "Lowest value of the thermostat card."
   ],
   "max_target": [
    "Maximum target",
    "Highest value of the thermostat card."
   ],
   "min_on_time": [
    "Minimum on time",
    "Always respected (protects the actuator). Not learned."
   ],
   "min_off_time": [
    "Minimum off time",
    "Always respected. Not learned."
   ],
   "heating_type": [
    "Heating type",
    "How the circuit heats. A floor stores heat for hours, radiators react within minutes; the AI judges the learned values with this in mind."
   ],
   "window_delay": [
    "Window delay (start value)",
    "Window open this long pauses heating. The AI may adjust it."
   ],
   "recovery_time": [
    "Recovery time after airing (start value)",
    "After closing, heating waits this long because floor and walls often reheat the room. Learned afterwards."
   ],
   "dead_time": [
    "Dead time until the room warms (start value)",
    "Time from switching on until the room gets warmer; underfloor heating often 30-90 min, radiators 5-20 min. Learned afterwards."
   ],
   "puffer": [
    "Margin above target (start value)",
    "Heating day rule: how far above the target an area must be at the nightly run to manage a day without heating (e.g. 0.7 K). Learned afterwards."
   ],
   "ventilation_rh_threshold": [
    "Humidity threshold",
    "Relative humidity from which ventilating is recommended (e.g. 65 % for bathrooms)."
   ],
   "reference_temperature": [
    "Reference temperature instead of outdoor",
    "Optional, for rooms aired via another room."
   ],
   "reference_humidity": [
    "Reference humidity instead of outdoor",
    "Required together with the reference temperature."
   ],
   "ventilation_block_entity": [
    "Ventilation block entity",
    "Optional. While it blocks, no ventilation is recommended: a cover while closed (e.g. sun protection down), a climate entity or water heater while not off (e.g. air conditioner running), a switch, binary sensor, fan or similar while on."
   ]
  },
  "learned": {
   "window_delay": [
    "Window delay",
    "Window open this long pauses heating. The AI may adjust it."
   ],
   "recovery_time": [
    "Recovery time after airing",
    "Learned wait after the windows are closed."
   ],
   "dead_time": [
    "Dead time until the room warms",
    "Learned time until the room warms up after switching on."
   ],
   "puffer": [
    "Margin above target",
    "Heating day rule: needed margin above the target at the nightly run (learned)."
   ]
  },
  "sections": {
   "sensors": [
    "Sensors",
    ""
   ],
   "heating": [
    "Heating circuit",
    ""
   ],
   "start_values": [
    "Start values (learned later)",
    "Only when the area is created. Afterwards the learned values are edited."
   ],
   "ventilation": [
    "Ventilation",
    ""
   ],
   "learned_values": [
    "Learned values",
    "Values the control currently uses. A change replaces the learned or AI-adjusted value; learning continues from there."
   ]
  },
  "limits": {
   "hysteresis_on": "Switch-on hysteresis",
   "hysteresis_off": "Switch-off hysteresis",
   "overshoot_factor": "Overshoot factor",
   "lead_factor": "Lead time factor",
   "sun_factor": "Sun factor",
   "window_delay_min": "Window delay",
   "recovery_bias_min": "Recovery time correction",
   "puffer": "Margin above target (puffer)",
   "theta": "Heating threshold (theta)"
  },
  "limit_columns": {
   "min": "Minimum",
   "max": "Maximum",
   "step": "Max. change per check"
  },
  "errors": {
   "invalid_day_month": "Please enter a valid date (DD.MM., e.g. 01.10.); a day like 31.02. does not exist.",
   "invalid_auth": "Anthropic rejected the API key. Check it at console.anthropic.com under API keys and paste it without spaces. Without a key the local control keeps running.",
   "cannot_connect": "Anthropic cannot be reached. Check the internet connection, proxy and firewall. The key was not saved.",
   "max_below_base": "The maximum interval must be at least the check interval (e.g. check every 4 h, at most every 48 h).",
   "min_above_max": "For each parameter the minimum must not be above the maximum. Please correct the limits of the parameter concerned.",
   "outdoor_required": "Choose an outdoor temperature sensor or a weather entity."
  },
  "area_errors": {
   "name_required": "Please enter a name.",
   "name_in_use": "Another area already has this name. Please choose a unique name (export and import find areas by name).",
   "switch_in_use": "This switch already controls another heating area. Each circuit can belong to one area only: choose another switch, or remove it from the other area first.",
   "min_above_max": "The smallest target must be below the largest target. Please change one of the two values (both in °C).",
   "target_out_of_range": "The start target must lie between the smallest and the largest target. Please adjust it or the limits.",
   "reference_incomplete": "Reference temperature and reference humidity only work together: choose both sensors or neither."
  },
  "states": {
   "status": {
    "off": "Off",
    "out_of_season": "Outside heating period",
    "no_heating_day": "No heating day",
    "idle": "Ready",
    "heating": "Heating",
    "window_open": "Window open",
    "recovery": "Recovery after airing",
    "frost_protection": "Frost protection",
    "vacation": "Vacation",
    "preheat": "Preheating for return",
    "emergency": "Emergency rule",
    "sensor_error": "Sensor error",
    "actuator_unavailable": "Actuator unavailable",
    "no_circuit": "No heating circuit"
   },
   "ventilation": {
    "unknown": "Unknown",
    "close_window": "Close window",
    "ventilate_now": "Ventilate now",
    "ventilation_useful": "Ventilation useful",
    "do_not_ventilate": "Do not ventilate",
    "blocked": "Ventilation blocked",
    "optimal": "All fine"
   },
   "phase": {
    "ai_leads": "AI leads",
    "shared": "Shared",
    "rule_leads": "Rule leads"
   },
   "override": {
    "auto": "Automatic",
    "heat_today": "Heat today",
    "off_today": "No heating today"
   }
  },
  "effort": {
   "auto": "Auto (model default)",
   "low": "Low",
   "medium": "Medium",
   "high": "High"
  },
  "heating_type": {
   "underfloor": "Underfloor heating",
   "radiator": "Radiators",
   "other": "Other (e.g. wall heating)"
  }
 }
};
