# AI Heating Assistant

[English version](README.en.md)

Custom Integration für Home Assistant, die eine Fußbodenheizung mit einem Schaltaktor je Heizkreis (z. B. ein Relais, das den Stellantrieb schaltet) lokal regelt, das Verhalten jedes Raums lernt und die Parameter regelmäßig von Claude (Anthropic) prüfen lässt. Home Assistant trifft alle Schaltentscheidungen selbst. Die KI schaltet nie, sie passt nur Parameter innerhalb einstellbarer Grenzen an und wird mit wachsender Sicherheit seltener gefragt.

Die Integration ersetzt typischerweise: Thermostat-Helfer (Generic Thermostat), Better Thermostat, Automationen für Sollwert, Wetter, Kälte und Urlaub sowie eine Lüftungsempfehlung auf Basis der Luftfeuchte.

> Status: Version 0.1.0, erste veröffentlichte Version. Bitte die ersten Wochen das Logbuch im Blick behalten.

## Funktionsweise

### Lokale Regelung je Heizbereich

* **Sollwert** über die normale Thermostatkarte. Er bleibt dauerhaft gespeichert, bis du ihn änderst. Keine Zeitpläne, keine Nachtabsenkung (bei Fußbodenheizung meist kontraproduktiv).
* **Vorausschauend einschalten:** Der Kreis geht an, wenn die Temperatur nach der gelernten Totzeit (unter Berücksichtigung von Abkühlrate, Außentemperatur und Sonne) unter Sollwert minus Einschalthysterese fallen würde.
* **Vorausschauend abschalten:** Der Kreis geht aus, wenn die aktuelle Temperatur plus das erwartete Überschwingen den Sollwert plus Ausschalthysterese erreicht. Das Überschwingen der trägen Fußbodenheizung wird gelernt (abhängig von der Laufzeit).
* **Fenster:** Ist ein Fenster länger als die Fensterverzögerung offen, pausiert die Heizanforderung. Nach dem Schließen wird die gelernte Erholungszeit abgewartet, weil Estrich und Wände den Raum oft selbst wieder aufheizen. Ist die Temperatur vor dem Lüften wieder erreicht, endet die Erholung sofort.
* **Mindest-Ein- und -Ausschaltzeit** werden immer eingehalten.
* **Frostschutz** gilt immer, auch außerhalb der Heizperiode und bei ausgeschaltetem Thermostat.
* **Heizperiode:** Außerhalb (z. B. 01.04. bis 30.09.) bleiben alle Kreise aus, es gibt keine KI-Abfragen.
* **Urlaub:** Frei wählbare Entitäten zeigen Urlaub an (z. B. `input_boolean.vacation_mode` oder ein Kalender). Dann gilt die Urlaubstemperatur für alle Bereiche. Mit einer optionalen Rückkehr-Entität (z. B. `input_datetime.vacation_end`) wird anhand der gelernten Aufheizrate so rechtzeitig vorgeheizt, dass bei Rückkehr der normale Sollwert erreicht ist.

### Heiztag-Entscheidung (Nachtlauf)

Einmal pro Nacht (Uhrzeit einstellbar) wird entschieden, ob heute überhaupt geheizt wird.

1. Eine **lokale Regel** schlägt vor: heizen, wenn die Prognose-Höchsttemperatur unter `theta` liegt oder ein Bereich unter Sollwert plus `puffer` liegt.
2. Die **KI** bekommt Wettervorhersage, Raumwerte, Lernwerte und die bewerteten letzten Tage und antwortet strukturiert (JSON mit Schema).
3. Ein **Phasenmodell** entscheidet, wer führt: *KI führt* (Start), *Gemeinsam* (bei Einigkeit diese, sonst die Regel, wenn sie sich sicher ist), *Regel führt* (die KI wird nur gefragt, wenn die Regel unsicher ist, plus einmal pro Woche zur Kontrolle). Ein Wechsel erfolgt nach genügend Tagen mit hoher Übereinstimmung und wenigen Regelfehlern, bei Fehlern geht es eine Phase zurück.
4. Jeder Tag wird nachträglich **bewertet** (Minuten zu kalt außerhalb von Lüftungsphasen, Heizminuten). Fehler A (nicht geheizt, obwohl nötig) und Fehler B (geheizt ohne Bedarf) passen `theta` und `puffer` an.

Bei "kein Heiztag" bleiben alle Kreise aus, außer Frostschutz und der optionalen **Notfallregel** (Bereich lange und deutlich unter dem Sollwert, ohne dass gelüftet wurde). Über die Auswahl "Heiztag manuell" lässt sich der Tag übersteuern, das gilt bis zur nächsten Entscheidung.

### Lernen je Bereich

* **Thermisches Modell** (rekursive kleinste Quadrate): `dT/dt = a · Ventil − k · (T_innen − T_außen) + s · PV`. Daraus folgen Aufheizrate, Abkühlrate, Einfluss der Außentemperatur (`k`) und Einfluss der Sonne (`s`, PV-Leistung als Sonnenindikator).
* **Ereignisse:** Totzeit nach dem Einschalten, Überschwingen nach dem Abschalten, Erholungszeit nach dem Lüften.
* Alle Werte werden dauerhaft gespeichert, als Sensoren angezeigt und lassen sich exportieren, importieren und zurücksetzen.

### KI-Prüfung (Claude)

* Nur an Heiztagen und in der Heizperiode. Sie erhält eine kompakte Zusammenfassung je Bereich (Ist, Soll, Lernwerte, Kennzahlen seit der letzten Prüfung) und liefert Parameteranpassungen als JSON.
* Anpassbare Parameter: Einschalt- und Ausschalthysterese, Faktor Überschwingen, Faktor Vorlauf, Sonnenfaktor, Fensterverzögerung, Korrektur der Erholungszeit, `puffer` und `theta`. Jeder Wert wird auf Minimum, Maximum und eine maximale Änderung je Prüfung begrenzt (alles einstellbar).
* **Seltener fragen:** Das Prüfintervall verdoppelt sich nach jeder Prüfung ohne relevante Änderung und ohne Komfortfehler (bis zum Maximalintervall). Es fällt auf das Grundintervall zurück, wenn es zu kalt war, die KI deutlich geändert hat oder du Sollwert bzw. Einstellungen änderst.
* **Kosten:** aus der Token-Nutzung mal den eingetragenen Preisen. Vor jeder Abfrage wird geschätzt; ist das Monatsbudget erreicht, gibt es bis zum Monatswechsel keine Abfragen.
* **Ausfall:** Bei Fehlern, Zeitüberschreitung oder ungültiger Antwort läuft die Regelung mit den zuletzt gelernten Werten weiter. Der API-Key erscheint nie im Log und wird in der Diagnose geschwärzt.

### Lüftungsempfehlung

Je Bereich (auch ohne Heizkreis) aus absoluter Feuchte innen und außen (oder eines Referenzraums):
*Jetzt lüften* (Feuchte über Schwelle und Außenluft trockener), *Lüften sinnvoll* (kühlt, wenn nicht geheizt wird), *Nicht lüften*, *Fenster schließen* (offen, bringt aber nichts), *Lüften blockiert* (Sperr-Entität aktiv, z. B. Klimaanlage) und *Alles optimal*.

## Installation über HACS

1. HACS öffnen, oben rechts im Menü **Benutzerdefinierte Repositories** wählen.
2. Repository `https://github.com/Jumpmaster2/AI-Heating-Assistant`, Typ **Integration**, hinzufügen.
3. **AI Heating Assistant** herunterladen und Home Assistant neu starten.
4. **Einstellungen > Geräte & Dienste > Integration hinzufügen > AI Heating Assistant**.

Voraussetzung: Home Assistant 2026.10 oder neuer. Für die KI ein API-Key von Anthropic (optional, ohne Key läuft nur die lokale Regelung).

## Konfiguration

### Einrichtung (global)

| Option | Standard | Bedeutung |
|---|---|---|
| Außentemperatursensor | | z. B. `sensor.outdoor_temperature` |
| Außenfeuchtesensor | | optional, für die Lüftungsempfehlung |
| Wetter-Entität | | optional, Vorhersage für den Nachtlauf |
| PV-Leistungssensor | | optional, Sonnenindikator (W oder kW) |
| Heizperiode | 01.10. bis 31.03. | Format TT.MM. |
| Frostschutz | 7 °C | gilt immer |
| Urlaubs-Entitäten | | "an" = Urlaub |
| Urlaubstemperatur | 18 °C | für alle Bereiche |
| Rückkehr Datum/Uhrzeit | | optional, für das Vorheizen |
| Vorheiz-Reserve | 30 min | |
| API-Key, Modell | Claude Opus 5.5 | änderbar, eigener Modellname möglich |
| Nachtlauf | 03:00 | |
| Monatsbudget | 5 € | |

### Optionen (Menü)

* **Allgemein, Urlaub:** wie oben.
* **Notfallregel:** an, 1 K unter Sollwert, 45 min, Fenster 30 min unverändert.
* **Lüftung:** Mindestvorteil absolute Feuchte 0,8 g/m³, außen höchstens 4 K wärmer, Mindest-Kühlvorteil 1 K, Nacht 20 bis 8 Uhr.
* **KI:** Modell, Effort (Standard niedrig), Nachtlauf, Prüfintervall 4 h, Maximalintervall 48 h, Budget, Preise in €/Million Tokens (Eingabe, Ausgabe, Cache schreiben, Cache lesen; vorbelegt mit dem Listenpreis des Modells), maximale Ausgabe-Tokens.
* **KI-Grenzen:** Minimum, Maximum, größte Änderung je Prüfung für jeden Parameter.
* **Heiztag-Entscheidung:** Startwert `theta` (16 °C), Bewertungsschwellen, Lernschritte, Bedingungen der Phasenwechsel.

Den API-Key änderst du über **Neu konfigurieren**.

### Heizbereiche

Unter der Integration **Heizbereich hinzufügen**. Je Bereich:

| Option | Standard |
|---|---|
| Name | |
| Temperatursensor, Feuchtesensor, Fenstersensoren | z. B. `sensor.living_room_temperature`, `binary_sensor.living_room_window` |
| Heizkreis-Schalter | z. B. `switch.heating_circuit_1`; leer = nur Lüftungsempfehlung |
| Start-Sollwert, kleinster und größter Sollwert | 21 / 16 / 24 °C |
| Mindest-Ein- und -Ausschaltzeit | 10 / 10 min (fest) |
| Startwerte Fensterverzögerung, Erholungszeit, Totzeit, puffer | 5 min, 30 min, 30 min, 0,7 K |
| Feuchte-Schwelle | 60 % |
| Referenz-Temperatur und -Feuchte | optional, statt außen (Raum ohne eigenes Fenster) |
| Lüftungs-Sperr-Entität | optional |

## Entitäten

Global (Gerät "AI Heating Assistant"):

* Binärsensor **Heiztag** (mit Quelle, Begründung, Konfidenz, Phase)
* Sensoren **Entscheidungsphase**, **Letzte KI-Prüfung** (mit Zusammenfassung und letztem Fehler), **Nächste KI-Prüfung**, **KI-Kosten im Monat**
* Schalter **KI aktiv**
* Auswahl **Heiztag manuell** (Automatik, Heute heizen, Heute nicht heizen)

Je Heizbereich (eigenes Gerät):

* **Thermostat** (climate)
* Sensoren **Status**, **Aufheizrate**, **Abkühlrate**, **Überschwingen nach Abschalten**, **Totzeit**, **Erholungszeit nach Lüften**, **Einfluss Außentemperatur**, **Einfluss Sonne**, **Lernstand**
* Sensor **Lüftungsempfehlung** und Binärsensor **Lüften empfohlen** (auch für Bereiche ohne Heizkreis)

Alle wichtigen Entscheidungen und jede KI-Anpassung mit Begründung stehen im **Logbuch**. Benachrichtigungen verschickt die Integration nicht.

## Dienste

| Dienst | Zweck |
|---|---|
| `ai_heating_assistant.export_parameters` | Lernwerte und Parameter als JSON (Antwort des Dienstes) |
| `ai_heating_assistant.import_parameters` | Lernwerte und Parameter aus JSON setzen (z. B. Startwerte) |
| `ai_heating_assistant.reset_learned` | Lernwerte einzelner Bereiche zurücksetzen, optional auch die Parameter |
| `ai_heating_assistant.run_ai_check` | KI-Prüfung sofort starten |
| `ai_heating_assistant.decide_heating_day` | Heiztag-Entscheidung sofort ausführen, optional ohne KI |

Beispiel Import:

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

## Entwicklung

```bash
pip install -r requirements_test.txt
pytest
```

Die Regel- und Lernlogik in `custom_components/ai_heating_assistant/logic/` hat keine Abhängigkeit zu Home Assistant und ist einzeln testbar. Die Tests mit Home Assistant brauchen Linux oder macOS (sie laufen auch in GitHub Actions).

## Lizenz

MIT, siehe [LICENSE](LICENSE).
