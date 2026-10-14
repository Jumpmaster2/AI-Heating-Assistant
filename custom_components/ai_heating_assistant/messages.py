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
    "ai_error": {
        "de": "KI-Fehler ({kind}): {error}. Regelung läuft mit den letzten Werten weiter.",
        "en": "AI error ({kind}): {error}. Control continues with the last values.",
    },
    "ai_budget": {
        "de": "KI-Monatsbudget erreicht ({spent} von {budget} €). Keine KI-Abfragen bis Monatsende.",
        "en": "AI monthly budget reached ({spent} of {budget} €). No AI calls until the end of the month.",
    },
    "import": {"de": "Parameter importiert: {areas}.", "en": "Parameters imported: {areas}."},
    "reset": {"de": "Gelernte Werte zurückgesetzt.", "en": "Learned values reset."},
    "start_value": {
        "de": "Startwert {name} aus der Konfiguration übernommen: {old} → {new} {unit}.",
        "en": "Start value {name} applied from the configuration: {old} → {new} {unit}.",
    },
    "dead_time": {"de": "Totzeit", "en": "dead time"},
    "recovery": {"de": "Erholungszeit", "en": "recovery time"},
    "window_delay_min": {"de": "Fensterverzögerung", "en": "window delay"},
    "puffer": {"de": "Puffer", "en": "puffer"},
}


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
