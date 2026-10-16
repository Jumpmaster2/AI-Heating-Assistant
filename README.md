# AI Heating Assistant

[English version](README.en.md)

Custom Integration für Home Assistant, die eine Fußbodenheizung mit einem Schaltaktor je Heizkreis (z. B. ein Relais, das den Stellantrieb schaltet) lokal regelt, das Verhalten jedes Raums lernt und die Parameter regelmäßig von Claude (Anthropic) prüfen lässt. Home Assistant trifft alle Schaltentscheidungen selbst. Die KI schaltet nie, sie passt nur Parameter innerhalb einstellbarer Grenzen an und wird mit wachsender Sicherheit seltener gefragt.

Die Integration ersetzt typischerweise: Thermostat-Helfer (Generic Thermostat), Better Thermostat, Automationen für Sollwert, Wetter, Kälte und Urlaub sowie eine Lüftungsempfehlung auf Basis der Luftfeuchte.

> Status: Version 0.6.0. Bitte die ersten Wochen das Logbuch im Blick behalten.

## Funktionsweise

### Lokale Regelung je Heizbereich

* **Sollwert** über die normale Thermostatkarte. Er bleibt dauerhaft gespeichert, bis du ihn änderst. Keine Zeitpläne, keine Nachtabsenkung (bei Fußbodenheizung meist kontraproduktiv).
* **Vorausschauend einschalten:** Der Kreis geht an, wenn die Temperatur nach der gelernten Totzeit (unter Berücksichtigung von Abkühlrate, Außentemperatur und Sonne) unter Sollwert minus Einschalthysterese fallen würde.
* **Sonne vorausschauend:** Für die Abkühlung über die Vorlaufzeit zählt nicht nur die aktuelle PV-Leistung, sondern die in dieser Zeit erwartete. Ist absehbar, dass die Sonne den Raum ohnehin aufheizt, schaltet der Kreis morgens nicht erst ein; abends rechnet die Regelung nicht mehr mit Sonne, die gleich verschwindet. Quelle ist ein optionaler PV-Prognosesensor (z. B. Forecast.Solar) oder, ohne ihn, die stündliche Wettervorhersage (Bewölkung) zusammen mit dem Sonnenstand. Dafür lernt die Integration an fast wolkenlosen Tagen, wie viel PV-Leistung bei klarem Himmel zu erwarten ist. Die Prognose fließt nur zu 70 % ein, und 1 K unter Sollwert wird unabhängig von jeder Vorhersage geheizt. Ohne PV-Leistungssensor bleibt alles wie bisher. Liefert der Sensor tagsüber keinen Wert, gilt die PV-Leistung als unbekannt: Es wird dann nichts kalibriert und nichts ins Modell übernommen, gerechnet wird mit der erwarteten Leistung (PV-Prognosesensor oder Sonnenstand und Bewölkung, sobald die Skala gelernt ist, sonst 0); bei tief stehender Sonne oder wenn ohnehin kaum Leistung zu erwarten ist, gilt 0. Fehlt der Wert länger als eine Stunde bei Tag, steht eine Warnung im Protokoll.
* **Vorausschauend abschalten:** Der Kreis geht aus, wenn die aktuelle Temperatur plus das erwartete Überschwingen den Sollwert plus Ausschalthysterese erreicht. Das Überschwingen der trägen Fußbodenheizung wird gelernt (abhängig von der Laufzeit). Nach dem Abschalten wird die noch im Boden steckende Wärme beim Wiedereinschalten berücksichtigt, bis die Temperatur wieder fällt; sonst liefe der Kreis nach der Mindestpause sofort wieder an.
* **Fenster:** Ist ein Fenster länger als die Fensterverzögerung offen, pausiert die Heizanforderung. Nach dem Schließen wird die gelernte Erholungszeit abgewartet, weil Estrich und Wände den Raum oft selbst wieder aufheizen. Ist die Temperatur vor dem Lüften wieder erreicht, endet die Erholung sofort.
* **Kurzlüften:** Solange ein Fenster offen ist, schaltet ein ausgeschalteter Kreis nicht ein, auch vor Ablauf der Fensterverzögerung. Ein laufender Kreis wird dabei nicht unterbrochen. War das Fenster mindestens 2 Minuten, aber kürzer als die Fensterverzögerung offen, folgt eine verkürzte Erholung: der Anteil der Fensterverzögerung, den das Fenster offen war, von der gelernten Erholungszeit (3 von 5 Minuten ergibt 60 %). Auch sie endet sofort, wenn die Temperatur vor dem Lüften wieder erreicht ist.
* **Mindest-Ein- und -Ausschaltzeit** werden immer eingehalten.
* **Frostschutz** gilt immer, auch außerhalb der Heizperiode und bei ausgeschaltetem Thermostat.
* **Heizperiode:** Außerhalb (z. B. 01.04. bis 30.09.) bleiben alle Kreise aus, es gibt keine KI-Abfragen.
* **Urlaub:** Frei wählbare Entitäten zeigen Urlaub an (z. B. `input_boolean.vacation_mode` oder ein Kalender). Dann gilt die Urlaubstemperatur für alle Bereiche. Mit einer optionalen Rückkehr-Entität (z. B. `input_datetime.vacation_end`) wird anhand der gelernten Aufheizrate so rechtzeitig vorgeheizt, dass bei Rückkehr der normale Sollwert erreicht ist. Liegt das Rückkehrdatum in der Vergangenheit (z. B. Urlaub manuell eingeschaltet), wird es ignoriert und die Urlaubstemperatur gilt.

### Heiztag-Entscheidung (Nachtlauf)

Einmal pro Nacht (Uhrzeit einstellbar) wird entschieden, ob heute überhaupt geheizt wird.

1. Eine **lokale Regel** schlägt vor: heizen, wenn die Prognose-Höchsttemperatur unter `theta` liegt oder ein Bereich unter Sollwert plus `puffer` liegt.
2. Die **KI** bekommt Wettervorhersage, Raumwerte, Lernwerte und die bewerteten letzten Tage und antwortet strukturiert (JSON mit Schema).
3. Ein **Phasenmodell** entscheidet, wer führt: *KI führt* (Start), *Gemeinsam* (bei Einigkeit diese, sonst die Regel, wenn sie sich sicher ist), *Regel führt* (die KI wird nur gefragt, wenn die Regel unsicher ist, plus einmal pro Woche zur Kontrolle). Ein Wechsel erfolgt nach genügend Tagen mit hoher Übereinstimmung und wenigen Regelfehlern, bei Fehlern geht es eine Phase zurück.
4. Jeder Tag wird nachträglich **bewertet**. Solange nichts geheizt hat, zählt die echte Raumtemperatur (Minuten zu kalt außerhalb von Lüftungsphasen). Sobald ein Kreis lief, hat die Entscheidung den Raum selbst warm gehalten; dann zählt ein virtueller Raum, der mit der gelernten Abkühlrate ohne Heizung weiterläuft. Fehler A (nicht geheizt, obwohl nötig) und Fehler B (geheizt ohne Bedarf) passen `theta` und `puffer` an. Tage mit manuellem Override werden nicht gelernt.

Bei "kein Heiztag" bleiben alle Kreise aus, außer Frostschutz und der optionalen **Notfallregel** (Raum unter dem Sollwert und Temperatur voraussichtlich nach der Vorlaufzeit lange und deutlich darunter, ohne dass gelüftet wurde). Über die Auswahl "Heiztag manuell" lässt sich der Tag übersteuern, das gilt bis zur nächsten Entscheidung.

### Lernen je Bereich

* **Thermisches Modell** (rekursive kleinste Quadrate): `dT/dt = a · Ventil − k · (T_innen − T_außen) + s · PV`. Daraus folgen Aufheizrate, Abkühlrate, Einfluss der Außentemperatur (`k`) und Einfluss der Sonne (`s`, PV-Leistung als Sonnenindikator).
* **Ereignisse:** Totzeit nach dem Einschalten, Überschwingen nach dem Abschalten, Erholungszeit nach dem Lüften. Die Totzeit zählt erst, wenn der Anstieg bestätigt ist (ein zweiter Sensorschritt oder ein Schritt, der fünf Minuten anhält), damit ein einzelnes Zittern des Sensors sie nicht verfälscht. Die Erholungszeit wird auch gelernt, wenn die Heizung die Wartezeit abbricht, sofern der Raum am Ende der Wartezeit gerade von selbst wärmer wurde; das thermische Modell vergisst langsam (etwa drei Wochen).
* Alle Werte werden dauerhaft gespeichert, als Sensoren angezeigt und lassen sich exportieren, importieren und zurücksetzen.

### KI-Prüfung (Claude)

* Nur an Heiztagen und in der Heizperiode. Sie erhält eine kompakte Zusammenfassung je Bereich (Ist, Soll, Lernwerte, Kennzahlen seit der letzten Prüfung) und liefert Parameteranpassungen als JSON.
* Anpassbare Parameter: Einschalt- und Ausschalthysterese, Faktor Überschwingen, Faktor Vorlauf, Sonnenfaktor, Fensterverzögerung, Korrektur der Erholungszeit, `puffer` und `theta`. Jeder Wert wird auf Minimum, Maximum und eine maximale Änderung je Prüfung begrenzt (alles einstellbar).
* **Seltener fragen:** Das Prüfintervall verdoppelt sich nach jeder Prüfung ohne relevante Änderung und ohne Komfortfehler (bis zum Maximalintervall). Es fällt auf das Grundintervall zurück, wenn es zu kalt war, die KI deutlich geändert hat oder du Sollwert bzw. Einstellungen änderst. Eine bereits geplante Prüfung bleibt über den Nachtlauf hinweg bestehen; nach einem Nicht-Heiztag folgt die nächste Prüfung nach dem Grundintervall, und war ein Raum seit der letzten Prüfung zu kalt, wird die nächste Prüfung vorgezogen.
* **Kosten:** aus der Token-Nutzung mal den eingetragenen Preisen. Vor jeder Abfrage wird geschätzt; ist das Monatsbudget erreicht, gibt es bis zum Monatswechsel keine Abfragen.
* **Ausfall:** Bei Fehlern, Zeitüberschreitung oder ungültiger Antwort läuft die Regelung mit den zuletzt gelernten Werten weiter. Der API-Key erscheint nie im Log und wird in der Diagnose geschwärzt.

### Lüftungsempfehlung

Je Bereich (auch ohne Heizkreis) aus absoluter Feuchte innen und außen (oder eines Referenzraums):
*Jetzt lüften* (Feuchte über Schwelle und Außenluft trockener), *Lüften sinnvoll* (kühlt, wenn nicht geheizt wird; in der Heizperiode nur, wenn der Raum deutlich über dem Sollwert liegt; nie unter der optionalen Mindesttemperatur und nie, wenn die Außenluft die relative Feuchte des Raums über seine Feuchte-Schwelle bringen würde), *Nicht lüften*, *Fenster schließen* (offen, bringt aber nichts), *Lüften blockiert* (Sperr-Entität aktiv, z. B. Klimaanlage) und *Alles optimal*.

## Installation über HACS

1. HACS öffnen, oben rechts im Menü **Benutzerdefinierte Repositories** wählen.
2. Repository `https://github.com/Jumpmaster2/AI-Heating-Assistant`, Typ **Integration**, hinzufügen.
3. **AI Heating Assistant** herunterladen und Home Assistant neu starten.
4. **Einstellungen > Geräte & Dienste > Integration hinzufügen > AI Heating Assistant**.

Voraussetzung: Home Assistant 2026.10 oder neuer. Für die KI ein API-Key von Anthropic (optional, ohne Key läuft nur die lokale Regelung).

## Konfiguration

### Dashboard

Nach der Einrichtung gibt es in der Seitenleiste die Seite **AI Heating Assistant** (nur für Administratoren). **Konfigurieren** unter Einstellungen > Geräte & Dienste führt direkt dorthin.

* **Übersicht:** Heiztag mit Phase und Begründung, Heiztag manuell (Automatik, Heute heizen, Heute nicht heizen), alle Bereiche mit Temperatur, Sollwert, Status und Lüftungsempfehlung (anklicken öffnet das Thermostat), Schalter KI aktiv, letzte und nächste KI-Prüfung, KI-Kosten im Monat, Hinweise (fehlende Entitäten, letzter KI-Fehler, Budget erreicht) und eine Zusammenfassung der Einstellungen.
* **Heizbereiche:** alle Bereiche als Tabelle; anklicken zum Bearbeiten, hinzufügen und löschen.
* **Allgemein, Notfall & Lüftung, KI, Heiztag-Entscheidung:** alle Einstellungen nach Themen in Karten, jede Karte wird für sich gespeichert. Unter **KI** auch der API-Key (wird vor dem Speichern geprüft, der gespeicherte Key wird nie angezeigt) und die KI-Grenzen.

Die Einrichtung selbst läuft weiterhin als Dialog.

### Einrichtung (global)

| Option | Standard | Bedeutung |
|---|---|---|
| Außentemperatursensor | | z. B. `sensor.outdoor_temperature` |
| Außenfeuchtesensor | | optional, für die Lüftungsempfehlung |
| Wetter-Entität | | optional, Vorhersage für den Nachtlauf und die Sonnenprognose |
| PV-Leistungssensor | | optional, Sonnenindikator (W oder kW) |
| PV-Prognosesensor | | optional, nur mit PV-Leistungssensor: Energie der nächsten Stunde (Wh oder kWh) oder Leistung in einer Stunde (W oder kW); ohne ihn wird die Wettervorhersage genutzt |
| Heizperiode | 01.10. bis 31.03. | Format TT.MM. |
| Frostschutz | 7 °C | gilt immer |
| Urlaubs-Entitäten | | "an" = Urlaub |
| Urlaubstemperatur | 18 °C | für alle Bereiche |
| Rückkehr Datum/Uhrzeit | | optional, für das Vorheizen |
| Vorheiz-Reserve | 30 min | |
| API-Key, Modell | Claude Opus 5.5 | änderbar, eigener Modellname möglich |
| Nachtlauf | 03:00 | |
| Monatsbudget | 5 € | |

### Einstellungen

* **Allgemein:** Sensoren, Heizperiode und Frostschutz, Urlaub wie oben.
* **Notfallregel:** an, 1 K unter Sollwert (voraussichtlich nach der Vorlaufzeit, mindestens die Einschalthysterese), 45 min, Fenster 30 min unverändert.
* **Lüftung:** Mindestvorteil absolute Feuchte 0,8 g/m³, außen höchstens 4 K wärmer, Mindest-Kühlvorteil 1 K, Kühlen in der Heizperiode erst ab 1 K über Sollwert, optional Kühlen erst ab einer festen Raumtemperatur (z. B. 23,5 °C, ganzjährig, Standard aus), Nacht 20 bis 8 Uhr.
* **KI:** Modell, Effort (Standard niedrig), Nachtlauf, Prüfintervall 4 h, Maximalintervall 48 h, Budget, Preise in €/Million Tokens (Eingabe, Ausgabe, Cache schreiben, Cache lesen; vorbelegt mit dem Listenpreis des Modells), maximale Ausgabe-Tokens.
* **KI-Grenzen:** Minimum, Maximum, größte Änderung je Prüfung für jeden Parameter.
* **Heiztag-Entscheidung:** Startwert `theta` (16 °C), Bewertungsschwellen, Lernschritte, Bedingungen der Phasenwechsel.

Den API-Key änderst du im Dashboard unter **KI** oder über **Neu konfigurieren**.

### Heizbereiche

Im Dashboard unter **Heizbereiche** (oder unter der Integration **Heizbereich hinzufügen**). Je Bereich:

| Option | Standard |
|---|---|
| Name | |
| Temperatursensor, Feuchtesensor, Fenstersensoren | z. B. `sensor.living_room_temperature`, `binary_sensor.living_room_window` |
| Heizkreis-Schalter | z. B. `switch.heating_circuit_1`; leer = nur Lüftungsempfehlung |
| Start-Sollwert, kleinster und größter Sollwert | 21 / 16 / 24 °C |
| Mindest-Ein- und -Ausschaltzeit | 10 / 10 min (fest) |
| Startwerte Fensterverzögerung, Erholungszeit, Totzeit, puffer | 5 min, 30 min, 30 min, 0,7 K; eine Änderung ersetzt den gelernten Wert |
| Feuchte-Schwelle | 60 % |
| Referenz-Temperatur und -Feuchte | optional, statt außen (Raum ohne eigenes Fenster) |
| Lüftungs-Sperr-Entität | optional |

Startwerte gelten, bis etwas gelernt wurde. Änderst du einen Startwert später, ersetzt er den gelernten bzw. von der KI angepassten Wert, das Lernen dieses Werts beginnt neu, und das Logbuch vermerkt es.

## Entitäten

Global (Gerät "AI Heating Assistant"):

* Binärsensor **Heiztag** (mit Quelle, Begründung, Konfidenz, Phase)
* Sensoren **Entscheidungsphase**, **Letzte KI-Prüfung** (mit Zusammenfassung und letztem Fehler), **Nächste KI-Prüfung**, **KI-Kosten im Monat**
* Schalter **KI aktiv**
* Auswahl **Heiztag manuell** (Automatik, Heute heizen, Heute nicht heizen)

Je Heizbereich (eigenes Gerät):

* **Thermostat** (climate), Attribute u. a. `predicted_temperature`, `expected_peak` und `expected_pv_kw` (über die Vorlaufzeit erwartete PV-Leistung)
* Sensoren **Status**, **Aufheizrate**, **Abkühlrate**, **Überschwingen nach Abschalten**, **Totzeit**, **Erholungszeit nach Lüften**, **Einfluss Außentemperatur**, **Einfluss Sonne**, **Lernstand**
* Sensor **Lüftungsempfehlung** und Binärsensor **Lüften empfohlen** (auch für Bereiche ohne Heizkreis)

Alle wichtigen Entscheidungen und jede KI-Anpassung mit Begründung stehen im **Logbuch**. Benachrichtigungen verschickt die Integration nicht.

## Dienste

| Dienst | Zweck |
|---|---|
| `ai_heating_assistant.export_parameters` | Lernwerte und Parameter als JSON (Antwort des Dienstes) |
| `ai_heating_assistant.import_parameters` | Lernwerte und Parameter aus JSON setzen (z. B. Startwerte) |
| `ai_heating_assistant.reset_learned` | Lernwerte einzelner Bereiche auf die Startwerte zurücksetzen, optional auch die Parameter |
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

Die Texte des Dashboards (`frontend/labels.js`) werden aus den Übersetzungsdateien erzeugt. Nach einer Änderung an `translations/*.json` einmal `python scripts/build_labels.py` ausführen (ein Test prüft das).

Die Regel- und Lernlogik in `custom_components/ai_heating_assistant/logic/` hat keine Abhängigkeit zu Home Assistant und ist einzeln testbar. Die Tests mit Home Assistant brauchen Linux oder macOS (sie laufen auch in GitHub Actions).

## Lizenz

MIT, siehe [LICENSE](LICENSE).
