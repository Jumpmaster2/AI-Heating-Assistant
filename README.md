# AI Heating Assistant

[English version](README.en.md)

Custom Integration für Home Assistant, die eine Fußbodenheizung mit einem Schaltaktor je Heizkreis (z. B. ein Relais, das den Stellantrieb schaltet) lokal regelt, das Verhalten jedes Raums lernt und die Parameter regelmäßig von Claude (Anthropic) prüfen lässt. Home Assistant trifft alle Schaltentscheidungen selbst. Die KI schaltet nie, sie passt nur Parameter innerhalb einstellbarer Grenzen an und wird mit wachsender Sicherheit seltener gefragt.

Die Integration ersetzt typischerweise: Thermostat-Helfer (Generic Thermostat), Better Thermostat, Automationen für Sollwert, Wetter, Kälte und Urlaub sowie eine Lüftungsempfehlung auf Basis der Luftfeuchte.

Übersicht, Lernwerte und alle Einstellungen stehen im Dashboard **AI Heating Assistant** in der Seitenleiste (siehe [Dashboard](#dashboard)).

> Status: Version 0.11.10. Bitte die ersten Wochen das Logbuch im Blick behalten.

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
* **Ausfälle:** Liefert der Temperatursensor keinen oder einen unmöglichen Wert (außerhalb −50 bis 80 °C, `nan`), bleibt der Kreis aus (Status *Sensorfehler*), auch der Frostschutz kann dann nicht greifen. Ist der Schalter nicht erreichbar, zeigt der Status *Aktor nicht erreichbar*. Dauert ein solcher Ausfall (oder der des Außentemperatursensors) länger als 15 Minuten, erscheint eine Reparaturmeldung unter Einstellungen > System > Reparaturen; sie verschwindet von selbst, sobald der Wert zurück ist. Eine ignorierte Meldung bleibt auch nach einem Neustart ignoriert, solange der Ausfall andauert. Folgt ein Schalter den Befehlen nicht, wird er nach 1, 2, 4, 8 und dann alle 15 Minuten erneut geschaltet statt jede Minute; nach drei Versuchen erscheint ebenfalls eine Meldung.
* **Heizperiode:** Außerhalb (z. B. 01.04. bis 30.09.) bleiben alle Kreise aus, es gibt keine KI-Abfragen.
* **Urlaub:** Frei wählbare Entitäten zeigen Urlaub an (z. B. `input_boolean.vacation_mode` oder ein Kalender). Dann gilt die Urlaubstemperatur für alle Bereiche. Mit einer optionalen Rückkehr-Entität (z. B. `input_datetime.vacation_end`) wird anhand der gelernten Aufheizrate so rechtzeitig vorgeheizt, dass bei Rückkehr der normale Sollwert erreicht ist. Liegt das Rückkehrdatum in der Vergangenheit (z. B. Urlaub manuell eingeschaltet), wird es ignoriert und die Urlaubstemperatur gilt.

### Heiztag-Entscheidung (Nachtlauf)

Einmal pro Nacht (Uhrzeit einstellbar) wird entschieden, ob heute überhaupt geheizt wird.

1. Eine **lokale Regel** schlägt vor: heizen, wenn die Prognose-Höchsttemperatur unter `theta` liegt oder ein Bereich unter Sollwert plus `puffer` liegt.
2. Die **KI** bekommt Wettervorhersage, Raumwerte, Lernwerte und die bewerteten letzten Tage (mit Heizminuten und Überheizen je Tag) und antwortet strukturiert (JSON mit Schema). Komfort hat Vorrang, unnötige Heiztage soll sie aber vermeiden.
3. Ein **Phasenmodell** entscheidet, wer führt: *KI führt* (Start), *Gemeinsam* (bei Einigkeit diese, sonst die Regel, wenn sie sich sicher ist), *Regel führt* (die KI wird nur gefragt, wenn die Regel unsicher ist, plus einmal pro Woche zur Kontrolle). Ein Wechsel erfolgt nach genügend Tagen mit hoher Übereinstimmung und wenigen Regelfehlern, bei Fehlern geht es eine Phase zurück.
4. Jeder Tag wird nachträglich **bewertet**. Solange nichts geheizt hat, zählt die echte Raumtemperatur (Minuten zu kalt außerhalb von Lüftungsphasen). Sobald ein Kreis lief, hat die Entscheidung den Raum selbst warm gehalten; dann zählt ein virtueller Raum, der mit der gelernten Abkühlrate ohne Heizung weiterläuft. Fehler A (nicht geheizt, obwohl nötig) und Fehler B (geheizt ohne Bedarf) passen `theta` und `puffer` an. Tage mit manuellem Override werden nicht gelernt.

Bei "kein Heiztag" bleiben alle Kreise aus, außer Frostschutz und der optionalen **Notfallregel** (Raum unter dem Sollwert und Temperatur voraussichtlich nach der Vorlaufzeit lange und deutlich darunter, ohne dass gelüftet wurde). Über die Auswahl "Heiztag manuell" lässt sich der Tag übersteuern, das gilt bis zur nächsten Entscheidung. "Heute heizen" wirkt auch außerhalb der Heizperiode (etwa an einem kalten Frühlingstag); die KI bleibt dort aus.

### Lernen je Bereich

* **Thermisches Modell** (rekursive kleinste Quadrate): `dT/dt = a · Ventil − k · (T_innen − T_außen) + s · PV`. Daraus folgen Aufheizrate, Abkühlrate, Einfluss der Außentemperatur (`k`) und Einfluss der Sonne (`s`, PV-Leistung als Sonnenindikator).
* **Ereignisse:** Totzeit nach dem Einschalten, Überschwingen nach dem Abschalten, Erholungszeit nach dem Lüften. Die Totzeit zählt erst, wenn der Anstieg bestätigt ist (ein zweiter Sensorschritt oder ein Schritt, der fünf Minuten anhält), damit ein einzelnes Zittern des Sensors sie nicht verfälscht. Die Erholungszeit wird auch gelernt, wenn die Heizung die Wartezeit abbricht, sofern der Raum am Ende der Wartezeit gerade von selbst wärmer wurde; das thermische Modell vergisst langsam (etwa drei Wochen).
* Alle Werte werden dauerhaft gespeichert, als Sensoren angezeigt und lassen sich exportieren, importieren und zurücksetzen. Export und Import finden Bereiche über den Namen, deshalb muss jeder Bereich anders heißen. Werden die KI-Grenzen enger gestellt, werden Werte außerhalb beim nächsten Laden auf die Grenze gesetzt (mit Logbuch-Eintrag).

### KI-Prüfung (Claude)

* Nur an Heiztagen und in der Heizperiode. Sie erhält eine kompakte Zusammenfassung je Bereich (Ist, Soll, Lernwerte, Kennzahlen seit der letzten Prüfung) und liefert Parameteranpassungen als JSON. Begründungen schreibt sie in der Sprache von Home Assistant (auch regionale Varianten wie de-CH).
* **Ziel:** so wenig Wärme wie möglich, ohne dass ein Raum unter den Sollwert fällt. Komfort ist eine feste Grenze, kein Tauschobjekt. Dafür bekommt die KI neben den Minuten zu kalt auch:
  * **Überheizen** (`over_kh`): Kelvinstunden mehr als 0,2 K über dem Sollwert, während der Kreis läuft und bis 4 Stunden nach dem Abschalten (also Wärme, die die Heizung zu viel geliefert hat). Wärme nur von der Sonne an einem Tag ohne Heizen zählt nicht. Der Anteil bei Sonne (`sun_over_kh`, PV ab 0,3 kW) zeigt, ob der Sonnenfaktor zu niedrig ist.
  * **Heizaufwand je Bedarf** (`on_per_kh`): Heizminuten je Kelvinstunde Unterschied zwischen Sollwert und Außentemperatur. So sind Prüfungen bei unterschiedlichem Wetter vergleichbar.
  * **Mittlere Laufzeit** je Einschalten.
  * **Verlauf der letzten 6 Prüfungen** mit ihren Kennzahlen und den dabei gemachten Änderungen. Die KI kann damit beurteilen, ob eine Änderung etwas gebracht hat, und sie sonst zurücknehmen. Wird ein Bereich zurückgesetzt oder ein gelernter Wert von Hand geändert, wird sein Verlauf gelöscht.
* Anpassbare Parameter: Einschalt- und Ausschalthysterese, Faktor Überschwingen, Faktor Vorlauf, Sonnenfaktor, Fensterverzögerung, Korrektur der Erholungszeit, `puffer` und `theta`. Jeder Wert wird auf Minimum, Maximum und eine maximale Änderung je Prüfung begrenzt (alles einstellbar).
* **Seltener fragen:** Das Prüfintervall verdoppelt sich nach jeder Prüfung ohne relevante Änderung und ohne Komfortfehler (bis zum Maximalintervall). Es fällt auf das Grundintervall zurück, wenn es zu kalt war, ein Bereich deutlich überheizt wurde (mehr als 0,5 Kelvinstunden je Tag, anteilig), die KI deutlich geändert hat oder du Einstellungen bzw. einen Sollwert um mindestens 0,5 K änderst (kleinere Schritte, etwa aus Automationen, setzen das Intervall nicht zurück). Eine bereits geplante Prüfung bleibt über den Nachtlauf hinweg bestehen; nach einem Nicht-Heiztag folgt die nächste Prüfung nach dem Grundintervall, und war ein Raum seit der letzten Prüfung zu kalt, wird die nächste Prüfung vorgezogen.
* **Kosten:** aus der Token-Nutzung mal den eingetragenen Preisen (in USD). Antwortet nach einem serverseitigen Fallback ein anderes Modell, gilt dessen Listenpreis. Vor jeder Abfrage wird geschätzt (Ausgabe: doppelter Mittelwert der bisherigen Antworten im Monat, höchstens die maximalen Ausgabe-Tokens, Standard 16000 inklusive Denken); ist das Monatsbudget erreicht, gibt es bis zum Monatswechsel keine Abfragen.
* **Ausfall:** Bei Fehlern, Zeitüberschreitung oder ungültiger Antwort läuft die Regelung mit den zuletzt gelernten Werten weiter. Der API-Key erscheint nie im Log und wird in der Diagnose geschwärzt.
* **Abgelehnter API-Key:** Lehnt Anthropic den Key ab (z. B. widerrufen), fragt Home Assistant unter Einstellungen > Geräte & Dienste nach einem neuen Key (erneute Authentifizierung). Bis dahin läuft die lokale Regelung ohne KI weiter; ein leeres Feld schaltet die KI ab.
* **Wetterdienst antwortet nicht:** Die Wetterprognose wird höchstens 10 Sekunden lang abgewartet; danach entscheidet die Heiztag-Regel ohne Prognose, und die Regelung läuft weiter. Schlägt die Heiztag-Entscheidung fehl, wird sie nach 15 Minuten erneut versucht (Fehler im Log).

### Wärmezähler

Optional. Mit einem Wärmezähler sieht die KI die tatsächlich verbrauchte Wärme statt nur der Laufzeit der Kreise.

* Verbrauch wird immer **zwischen zwei Zählerwerten** gerechnet, nicht zwischen beliebigen Zeitpunkten. Zusammen mit jedem Zählerwert merkt sich die Integration den bis dahin aufgelaufenen Heizbedarf (Kelvinstunden Sollwert minus Außentemperatur, Mittel über die Bereiche). Verbrauch und Bedarf decken so genau denselben Zeitraum ab, auch wenn der Zähler nur alle paar Stunden und in groben Schritten meldet.
* **KI-Prüfung:** `heat` mit kWh, Stunden und `kwh_per_kh` (kWh je Kelvinstunde Bedarf, das beste Maß für die Effizienz) seit der letzten Prüfung; Zeiträume unter einer Stunde werden nicht gemeldet. `kwh_per_kh` steht auch im Prüfverlauf.
* **Nachtlauf:** kWh je vergangenem Heiztag in der Historie.
* **Dashboard:** Karte **Wärme** mit heute, gestern, diesem Monat und dem Zeitpunkt des letzten Zählerwerts. Ein Tag zählt vom letzten Zählerwert vor Mitternacht bis zum letzten vor der nächsten Mitternacht, „gestern“ fehlt nach einem ausgelassenen Tag.
* Sinkt der Zählerstand (Zählertausch) oder wird ein anderer Zähler gewählt, beginnt die Zählung neu.

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

* **Übersicht:** Heiztag mit Phase und Begründung, Heiztag manuell (Automatik, Heute heizen, Heute nicht heizen), alle Bereiche mit Temperatur, Sollwert, Status und Lüftungsempfehlung (anklicken öffnet das Thermostat), Schalter KI aktiv, letzte und nächste KI-Prüfung, nächster Nachtlauf, letzte Heiztag-Entscheidung mit Quelle (KI, Regel, beide einig), KI-Kosten im Monat, Hinweise (fehlende Entitäten, letzter KI-Fehler, Budget erreicht) und eine Zusammenfassung der Einstellungen.
* **Heizbereiche:** alle Bereiche als Tabelle; anklicken zum Bearbeiten, hinzufügen und löschen.
* **Lernwerte:** je Bereich mit Heizkreis eine kompakte Kachel mit Lernstand, Aufheiz- und Abkühlrate, Totzeit, Überschwingen, Erholung nach Lüften, Einfluss Außentemperatur und Sonne; aufklappbar die von der KI anpassbaren Regelparameter. Dazu die Heiztag-Regel (`theta`, bewertete Tage). Der Stift führt zum Bearbeiten der gelernten Werte.
* **Allgemein, Notfall & Lüftung, KI, Heiztag-Entscheidung:** alle Einstellungen nach Themen in Karten, jede Karte wird für sich gespeichert. Unter **KI** auch der API-Key (wird vor dem Speichern geprüft, der gespeicherte Key wird nie angezeigt) und die KI-Grenzen.

Die Einrichtung selbst läuft weiterhin als Dialog.

### Einrichtung (global)

Temperatursensoren dürfen in °C, °F oder K melden; ohne Einheit gilt das Einheitensystem von Home Assistant. Gerechnet wird intern in °C, und alle Temperaturen in den Einstellungen (Sollwerte, Frostschutz, `theta`) werden in °C eingegeben. Die Thermostate zeigen Werte im Einheitensystem von Home Assistant.

| Option | Standard | Bedeutung |
|---|---|---|
| Außentemperatursensor | | z. B. `sensor.outdoor_temperature` |
| Außenfeuchtesensor | | optional, für die Lüftungsempfehlung |
| Wetter-Entität | | optional, Vorhersage für den Nachtlauf und die Sonnenprognose |
| PV-Leistungssensor | | optional, Sonnenindikator (W oder kW; ohne Einheit gilt W, eine andere Einheit wird mit Warnung ignoriert) |
| PV-Prognosesensor | | optional, nur mit PV-Leistungssensor: Energie der nächsten Stunde (Wh oder kWh) oder Leistung in einer Stunde (W oder kW); ohne ihn wird die Wettervorhersage genutzt |
| Wärmezähler | | optional, Zählerstand der hier geregelten Heizkreise (Wh, kWh, MWh, MJ oder GJ); seltene und grobe Werte sind kein Problem, siehe [Wärmezähler](#wärmezähler) |
| Heizperiode | 01.10. bis 31.03. | Format TT.MM. |
| Frostschutz | 7 °C | gilt immer |
| Urlaubs-Entitäten | | "an" = Urlaub |
| Urlaubstemperatur | 18 °C | für alle Bereiche |
| Rückkehr Datum/Uhrzeit | | optional, für das Vorheizen |
| Vorheiz-Reserve | 30 min | |
| Startwert `theta` | 16 °C | Heiztag-Regel; nur bei der Einrichtung, danach wird der gelernte Wert bearbeitet |
| API-Key, Modell | Claude Opus 5.5 | änderbar, eigener Modellname möglich |
| Nachtlauf | 03:00 | |
| Monatsbudget | 5 USD | |

### Einstellungen

* **Allgemein:** Sensoren, Heizperiode und Frostschutz, Urlaub wie oben.
* **Notfallregel:** an, 1 K unter Sollwert (voraussichtlich nach der Vorlaufzeit, mindestens die Einschalthysterese), 45 min, Fenster 30 min unverändert.
* **Lüftung:** Mindestvorteil absolute Feuchte 0,8 g/m³, außen höchstens 4 K wärmer, Mindest-Kühlvorteil 1 K, Kühlen in der Heizperiode erst ab 1 K über Sollwert, optional Kühlen erst ab einer festen Raumtemperatur (z. B. 23,5 °C, ganzjährig, Standard aus), Nacht 20 bis 8 Uhr.
* **KI:** Modell, Effort (Standard niedrig), Nachtlauf, Prüfintervall 4 h, Maximalintervall 48 h, Budget, Preise in USD je Million Tokens (Anthropic rechnet in US-Dollar ab; es wird nicht umgerechnet) (Eingabe, Ausgabe, Cache schreiben, Cache lesen; vorbelegt mit dem Listenpreis des Modells), maximale Ausgabe-Tokens.
* **KI-Grenzen:** Minimum, Maximum, größte Änderung je Prüfung für jeden Parameter.
* **Heiztag-Entscheidung:** gelerntes `theta` (änderbar), Bewertungsschwellen, Lernschritte, Bedingungen der Phasenwechsel.

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
| Startwerte Fensterverzögerung, Erholungszeit, Totzeit, puffer | 5 min, 30 min, 30 min, 0,7 K; nur beim Anlegen |
| Feuchte-Schwelle | 60 % |
| Referenz-Temperatur und -Feuchte | optional, statt außen (Raum ohne eigenes Fenster) |
| Lüftungs-Sperr-Entität | optional |

Startwerte (auch `theta`) werden nur beim Einrichten bzw. Anlegen gesetzt und gelten, bis etwas gelernt wurde. Danach lassen sie sich nicht mehr ändern; stattdessen zeigt der Bereich unter **Gelernte Werte** die Werte, mit denen gerade geregelt wird (Fensterverzögerung, Erholungszeit, Totzeit, puffer), und das gelernte `theta` steht unter **Heiztag-Entscheidung**. Eine Änderung dort ersetzt den gelernten bzw. von der KI angepassten Wert, das Lernen geht von dort aus weiter, und das Logbuch vermerkt es.

## Entitäten

Global (Gerät "AI Heating Assistant"):

* Binärsensor **Heiztag** (mit Quelle, Begründung, Konfidenz, Phase, Zeitpunkt der Entscheidung `decided_at` und nächstem Nachtlauf `next_decision`)
* Sensoren **Entscheidungsphase**, **Letzte KI-Prüfung** (mit Zusammenfassung und letztem Fehler), **Nächste KI-Prüfung**, **KI-Kosten im Monat**
* Sensor **Wärme heute** (nur mit Wärmezähler, kWh; Attribute `yesterday`, `month`, `last_month`, `meter_reading_at`)
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

## Deaktivieren und Deinstallation

Wird die Integration deaktiviert oder entfernt, schaltet sie alle eingeschalteten Heizkreise aus; sonst würde ein gerade laufender Kreis ohne Grenze weiterheizen. Dasselbe gilt für den Schalter eines gelöschten Heizbereichs und für einen Schalter, der in einem Bereich durch einen anderen ersetzt wurde. Ein Neuladen (z. B. nach einer Änderung der Einstellungen) oder ein Neustart von Home Assistant lässt die Kreise unverändert.

Beim Entfernen werden außerdem die gelernten Werte (`.storage/ai_heating_assistant.<entry_id>`) und die Seite in der Seitenleiste gelöscht. Danach den Ordner `custom_components/ai_heating_assistant` entfernen (bzw. in HACS „Entfernen“ wählen) und Home Assistant neu starten.

## Entwicklung

```bash
pip install -r requirements_test.txt
pytest
```

Die Texte des Dashboards (`frontend/labels.js`) werden aus den Übersetzungsdateien erzeugt. Nach einer Änderung an `translations/*.json` einmal `python scripts/build_labels.py` ausführen (ein Test prüft das).

Die Regel- und Lernlogik in `custom_components/ai_heating_assistant/logic/` hat keine Abhängigkeit zu Home Assistant und ist einzeln testbar. Die Tests mit Home Assistant brauchen Linux oder macOS (sie laufen auch in GitHub Actions).

## Lizenz

MIT, siehe [LICENSE](LICENSE).
