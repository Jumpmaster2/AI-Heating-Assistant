"""Localised texts for logbook entries (German and English)."""

from __future__ import annotations

from typing import Any

_TEXTS: dict[str, dict[str, str]] = {
    "heating_day": {
        "de": "Heiztag {decision} (Quelle: {source}, Phase: {phase}). {reason}",
        "en": "Heating day {decision} (source: {source}, phase: {phase}). {reason}",
    },
    "yes": {"de": "ja", "en": "yes"},
    "no": {"de": "nein", "en": "no"},
    "evaluation": {
        "de": "Bewertung {date}: Bedarf {need}, Fehler Entscheidung {err_final}, Regel {err_rule}, KI {err_ai}.",
        "en": "Evaluation {date}: need {need}, error decision {err_final}, rule {err_rule}, AI {err_ai}.",
    },
    "rule_learned": {
        "de": "Heiztag-Regel gelernt: theta {theta} °C, puffer {puffer}.",
        "en": "Heating day rule learned: theta {theta} °C, puffer {puffer}.",
    },
    "phase_change": {
        "de": "Entscheidungsphase gewechselt: {old} -> {new}.",
        "en": "Decision phase changed: {old} -> {new}.",
    },
    "window_pause": {
        "de": "Fenster offen: Heizanforderung pausiert.",
        "en": "Window open: heating demand paused.",
    },
    "recovery_start": {
        "de": "Fenster geschlossen: Erholungszeit bis {until}.",
        "en": "Window closed: recovery until {until}.",
    },
    "recovery_end": {"de": "Erholung beendet.", "en": "Recovery finished."},
    "emergency": {
        "de": "Notfallregel: {temp} °C, voraussichtlich {predicted} °C nach der Vorlaufzeit (Grenze {limit} °C), seit langem darunter; heizt trotz Nicht-Heiztag.",
        "en": "Emergency rule: {temp} °C, expected {predicted} °C after the lead time (limit {limit} °C), long below it; heating despite no heating day.",
    },
    "frost_start": {
        "de": "Frostschutz aktiv ({temp} °C).",
        "en": "Frost protection active ({temp} °C).",
    },
    "frost_end": {"de": "Frostschutz beendet.", "en": "Frost protection ended."},
    "external_switch": {
        "de": "Heizkreis wurde von außen {state} geschaltet.",
        "en": "Heating circuit was switched {state} externally.",
    },
    "on": {"de": "ein", "en": "on"},
    "off": {"de": "aus", "en": "off"},
    "ai_adjust": {
        "de": "KI-Anpassung {parameter}: {old} -> {new}{clamped}. {reason}",
        "en": "AI adjustment {parameter}: {old} -> {new}{clamped}. {reason}",
    },
    "clamped": {"de": " (begrenzt)", "en": " (limited)"},
    "ai_check": {
        "de": "KI-Prüfung: {count} Anpassung(en), Konfidenz {confidence}. {summary} Nächste Prüfung in {hours} h.",
        "en": "AI check: {count} adjustment(s), confidence {confidence}. {summary} Next check in {hours} h.",
    },
    "ai_vent_check": {
        "de": "KI-Lüftungsprüfung: {count} Anpassung(en), Konfidenz {confidence}. {summary} Nächste Prüfung in {hours} h.",
        "en": "AI ventilation check: {count} adjustment(s), confidence {confidence}. {summary} Next check in {hours} h.",
    },
    "ai_error": {
        "de": "KI-Fehler ({kind}): {error}. Regelung läuft mit den letzten Werten weiter.",
        "en": "AI error ({kind}): {error}. Control continues with the last values.",
    },
    "ai_budget": {
        "de": "KI-Monatsbudget erreicht ({spent} von {budget} USD). Keine KI-Abfragen bis Monatsende.",
        "en": "AI monthly budget reached ({spent} of {budget} USD). No AI calls until the end of the month.",
    },
    "import": {"de": "Parameter importiert: {areas}.", "en": "Parameters imported: {areas}."},
    "reset": {"de": "Gelernte Werte zurückgesetzt.", "en": "Learned values reset."},
    "start_value": {
        "de": "Startwert {name} aus der Konfiguration übernommen: {old} → {new} {unit}.",
        "en": "Start value {name} applied from the configuration: {old} → {new} {unit}.",
    },
    "learned_edit": {
        "de": "Gelernter Wert {name} von Hand geändert: {old} → {new} {unit}.",
        "en": "Learned value {name} changed by hand: {old} → {new} {unit}.",
    },
    "sensor_unavailable": {
        "de": "Temperatursensor {entity_id} liefert seit 15 Minuten keinen Wert; der Heizkreis bleibt aus, auch der Frostschutz greift nicht.",
        "en": "Temperature sensor {entity_id} has had no value for 15 minutes; the heating circuit stays off and frost protection cannot work either.",
    },
    "actuator_unavailable": {
        "de": "Schalter {entity_id} ist seit 15 Minuten nicht erreichbar; der Heizkreis kann nicht geschaltet werden.",
        "en": "Switch {entity_id} has been unavailable for 15 minutes; the heating circuit cannot be switched.",
    },
    "actuator_not_responding": {
        "de": "Schalter {entity_id} folgt den Schaltbefehlen nicht; neue Versuche mit wachsendem Abstand (bis 15 Minuten).",
        "en": "Switch {entity_id} does not follow the switching commands; it is asked again with growing pauses (up to 15 minutes).",
    },
    "outdoor_unavailable": {
        "de": "Außentemperatursensor {entity_id} liefert seit 15 Minuten keinen Wert; Vorhersage und Lernen sind eingeschränkt.",
        "en": "Outdoor temperature sensor {entity_id} has had no value for 15 minutes; prediction and learning are limited.",
    },
    "limit_clamp": {
        "de": "{parameter}: {old} -> {new}, weil die KI-Grenzen geändert wurden.",
        "en": "{parameter}: {old} -> {new} because the AI limits were changed.",
    },
    "circuit_released": {
        "de": "Schalter {entity_id} gehört zu keinem Heizbereich mehr und wurde ausgeschaltet.",
        "en": "Switch {entity_id} no longer belongs to a heating area and was switched off.",
    },
    "dead_time": {"de": "Totzeit", "en": "dead time"},
    "recovery": {"de": "Erholungszeit", "en": "recovery time"},
    "window_delay_min": {"de": "Fensterverzögerung", "en": "window delay"},
    "puffer": {"de": "Puffer", "en": "puffer"},
}


# Values shown in logbook texts instead of internal keys.
_VALUES: dict[str, dict[str, dict[str, str]]] = {
    "source": {
        "ai": {"de": "KI", "en": "AI"},
        "rule": {"de": "Regel", "en": "rule"},
        "rule_fallback": {"de": "Regel ohne KI", "en": "rule without AI"},
        "agreement": {"de": "Regel und KI einig", "en": "rule and AI agree"},
        "vacation_rule": {"de": "Regel im Urlaub", "en": "rule on vacation"},
        "season": {"de": "außerhalb der Heizperiode", "en": "outside the heating period"},
        "override": {"de": "von Hand", "en": "set by hand"},
    },
    "phase": {
        "ai_leads": {"de": "KI führt", "en": "AI leads"},
        "shared": {"de": "gemeinsam", "en": "shared"},
        "rule_leads": {"de": "Regel führt", "en": "rule leads"},
    },
    "need": {
        "yes": {"de": "ja", "en": "yes"},
        "no": {"de": "nein", "en": "no"},
        "unclear": {"de": "unklar", "en": "unclear"},
    },
    "error": {
        "A": {"de": "zu kalt ohne Heizen", "en": "too cold without heating"},
        "B": {"de": "unnötig geheizt", "en": "heated without need"},
        "": {"de": "keiner", "en": "none"},
    },
    "parameter": {
        "hysteresis_on": {"de": "Einschalt-Hysterese", "en": "switch-on hysteresis"},
        "hysteresis_off": {"de": "Ausschalt-Hysterese", "en": "switch-off hysteresis"},
        "overshoot_factor": {"de": "Überschwing-Faktor", "en": "overshoot factor"},
        "lead_factor": {"de": "Vorlauf-Faktor", "en": "lead factor"},
        "sun_factor": {"de": "Sonnenfaktor", "en": "sun factor"},
        "window_delay_min": {"de": "Fensterverzögerung", "en": "window delay"},
        "recovery_bias_min": {"de": "Erholungszeit-Zuschlag", "en": "recovery time offset"},
        "puffer": {"de": "Reserve über Sollwert", "en": "margin above target"},
        "theta": {"de": "Heizgrenze", "en": "heating threshold"},
        "rh_threshold": {"de": "Feuchte-Schwelle", "en": "humidity threshold"},
        "rh_hysteresis": {"de": "Feuchte-Hysterese", "en": "humidity hysteresis"},
        "min_ah_advantage": {"de": "Mindest-Feuchtevorteil", "en": "minimum humidity advantage"},
        "max_reference_excess": {
            "de": "max. Übertemperatur der Referenz",
            "en": "max. reference excess",
        },
        "min_rh_drop": {"de": "Mindest-Feuchteabfall", "en": "minimum humidity drop"},
        "min_cooling_advantage": {"de": "Mindest-Kühlvorteil", "en": "minimum cooling advantage"},
        "cooling_margin": {"de": "Kühl-Abstand zum Sollwert", "en": "cooling margin"},
        "cooling_min_temp": {
            "de": "Kühlen ab Raumtemperatur",
            "en": "cooling from room temperature",
        },
    },
}


def label_of(language: str, group: str, key: Any) -> str:
    """Readable name of an internal value (source, phase, need, error, parameter)."""
    lang = "de" if language.lower().startswith("de") else "en"
    entry = _VALUES.get(group, {}).get(str(key or ""))
    return entry[lang] if entry else str(key)


def text(language: str, key: str, **kwargs: Any) -> str:
    """Return the localised text."""
    lang = "de" if language.lower().startswith("de") else "en"
    entry = _TEXTS.get(key)
    if entry is None:
        return key
    try:
        return entry[lang].format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return entry[lang]
