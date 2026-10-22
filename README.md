# AI Heating Assistant

[English version](README.en.md)

Custom Integration für Home Assistant, die eine Fußbodenheizung (oder Heizkörper je Bereich, siehe Heizungsart) mit einem Schaltaktor je Heizkreis (z. B. ein Relais, das den Stellantrieb schaltet) lokal regelt, das Verhalten jedes Raums lernt und die Parameter regelmäßig von Claude (Anthropic) prüfen lässt. Home Assistant trifft alle Schaltentscheidungen selbst. Die KI schaltet nie, sie passt nur Parameter innerhalb einstellbarer Grenzen an und wird mit wachsender Sicherheit seltener gefragt.

Die Integration ersetzt typischerweise: Thermostat-Helfer (Generic Thermostat), Better Thermostat, Automationen für Sollwert, Wetter, Kälte und Urlaub sowie eine Lüftungsempfehlung auf Basis der Luftfeuchte.

Übersicht, Lernwerte und alle Einstellungen stehen im Dashboard **AI Heating Assistant** in der Seitenleiste (siehe [Dashboard](#dashboard)).

> Status: Version 1.6.0. Bitte die ersten Wochen das Logbuch im Blick behalten.

## Funktionsweise

### Lokale Regelung je Heizbereich

* **Sollwert** über die normale Thermostatkarte. Er bleibt dauerhaft gespeichert, bis du ihn änderst. Keine Zeitpläne, keine Nachtabsenkung (bei Fußbodenheizung meist kontraproduktiv).
* **Vorausschauend einschalten:** Der Kreis geht an, wenn die Temperatur nach der gelernten Totzeit (unter Berücksichtigung von Abkühlrate, Außentemperatur und Sonne) unter Sollwert minus Einschalthysterese fallen würde.
* **Sonne vorausschauend:** Für die Abkühlung über die Vorlaufzeit zählt nicht nur die aktuelle PV-Leistung, sondern die in dieser Zeit erwartete. Ist absehbar, dass die Sonne den Raum ohnehin aufheizt, schaltet der Kreis morgens nicht erst ein; abends rechnet die Regelung nicht mehr mit Sonne, die gleich verschwindet. Quelle ist ein optionaler PV-Prognosesensor (z. B. Forecast.Solar) oder, ohne ihn, die stündliche Wettervorhersage (Bewölkung) zusammen mit dem Sonnenstand. Dafür lernt die Integration an fast wolkenlosen Tagen, wie viel PV-Leistung bei klarem Himmel zu erwarten ist. Die Prognose fließt nur zu 70 % ein (Option „Vertrauen in die Sonnenprognose“), und 1 K unter Sollwert wird unabhängig von jeder Vorhersage geheizt (Option „Immer heizen unter Sollwert um“, 0,3 bis 3 K). Ohne PV-Leistungssensor bleibt alles wie bisher. Liefert der Sensor tagsüber keinen Wert, gilt die PV-Leistung als unbekannt: Es wird dann nichts kalibriert und nichts ins Modell übernommen, gerechnet wird mit der erwarteten Leistung (PV-Prognosesensor oder Sonnenstand und Bewölkung, sobald die Skala gelernt ist, sonst 0); bei tief stehender Sonne oder wenn ohnehin kaum Leistung zu erwarten ist, gilt 0. Fehlt der Wert länger als eine Stunde bei Tag, steht eine Warnung im Protokoll.
* **Vorausschauend abschalten:** Der Kreis geht aus, wenn die aktuelle Temperatur plus das erwartete Überschwingen den Sollwert plus Ausschalthysterese erreicht. Das Überschwingen der trägen Fußbodenheizung wird gelernt (abhängig von der Laufzeit). Nach dem Abschalten wird die noch im Boden steckende Wärme beim Wiedereinschalten berücksichtigt, bis die Temperatur wieder fällt; sonst liefe der Kreis nach der Mindestpause sofort wieder an.
* **Fenster:** Ist ein Fenster länger als die Fensterverzögerung offen, pausiert die Heizanforderung. Nach dem Schließen wird die gelernte Erholungszeit abgewartet, weil Estrich und Wände den Raum oft selbst wieder aufheizen. Ist die Temperatur vor dem Lüften wieder erreicht, endet die Erholung sofort.
* **Luftzug aus anderen Räumen:** Werden gegenüberliegende Räume gleichzeitig gelüftet, kühlt der Luftzug oft auch einen dritten Bereich aus. Dafür gibt es je Bereich unter *Luftzug aus anderen Räumen* bis zu vier Kombinationen von Fenstern anderer Räume. Sobald alle Fenster einer Kombination offen sind, verhält sich der Bereich wie bei einem eigenen offenen Fenster: Pause nach der Fensterverzögerung, danach Erholungszeit, kein Lernen und keine Zählung als „zu kalt“. Beispiel Wohnbereich: Kombination 1 = Kinderzimmer + Bad, Kombination 2 = Kinderzimmer + Schlafzimmer. Dann lösen diese beiden Paare aus, Schlafzimmer + Bad aber nicht. Eine Kombination mit nur einem Fenster löst schon allein aus. Die Lüftungsempfehlung des Bereichs richtet sich weiter nur nach seinen eigenen Fenstern. Das Attribut `draft` des Thermostats zeigt, ob gerade Luftzug erkannt wird.
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
  * **Überheizen** (`over_kh`): Kelvinstunden mehr als 0,2 K über dem Sollwert, während der Kreis läuft und bis 4 Stunden nach dem Abschalten (also Wärme, die die Heizung zu viel geliefert hat). Wärme nur von der Sonne an einem Tag ohne Heizen zählt nicht. Der Anteil bei Sonne (`sun_over_kh`, PV ab 0,3 kW bzw. ab 10 % der gelernten Leistung bei klarem Himmel) zeigt, ob der Sonnenfaktor zu niedrig ist.
  * **Heizaufwand je Bedarf** (`on_per_kh`): Heizminuten je Kelvinstunde Unterschied zwischen Sollwert und Außentemperatur. So sind Prüfungen bei unterschiedlichem Wetter vergleichbar.
  * **Mittlere Laufzeit** je Einschalten.
  * **Verlauf der letzten 6 Prüfungen** mit ihren Kennzahlen und den dabei gemachten Änderungen. Die KI kann damit beurteilen, ob eine Änderung etwas gebracht hat, und sie sonst zurücknehmen. Wird ein Bereich zurückgesetzt oder ein gelernter Wert von Hand geändert, wird sein Verlauf gelöscht.
* Anpassbare Parameter: Einschalt- und Ausschalthysterese, Faktor Überschwingen, Faktor Vorlauf, Sonnenfaktor, Fensterverzögerung, Korrektur der Erholungszeit, `puffer` und `theta`. Jeder Wert wird auf Minimum, Maximum und eine maximale Änderung je Prüfung begrenzt (alles einstellbar).
* **KI-Anweisungen anpassen:** Im Panel unter *KI > KI-Anweisungen* sind die Anweisungen an die KI für beide Aufrufe (Nachtentscheidung und Parameterprüfung) in Bausteine zerlegt. Jeder Standard-Baustein lässt sich abschalten oder umformulieren (*Standard wiederherstellen* setzt ihn zurück). Eigene Bausteine (bis zu 10 je Aufruf, je höchstens 2000 Zeichen, in jeder Sprache) ergänzen das Wissen über das Haus, z. B. „Im Wohnbereich brennt abends meist der Kaminofen“. Aufgabe und Antwortformat bleiben fest, damit die Antwort gültig bleibt. Eine Vorschau zeigt die fertige Anweisung. Längere Anweisungen kosten etwas mehr je Abfrage.
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
*Jetzt lüften* (Feuchte über Schwelle, Außenluft trockener und Lüften senkt die Feuchte spürbar), *Lüften sinnvoll* (kühlt, wenn nicht geheizt wird; in der Heizperiode nur, wenn der Raum deutlich über dem Sollwert liegt; nie unter der optionalen Mindesttemperatur und nie, wenn die Außenluft die relative Feuchte des Raums über seine Feuchte-Schwelle bringen würde), *Nicht lüften*, *Fenster schließen* (offen, bringt aber nichts), *Lüften blockiert* (Sperr-Entität aktiv, z. B. Klimaanlage) und *Alles optimal*.

**Gelerntes Feuchteprofil je Raum:** Für jeden Bereich mit Feuchtesensor lernt die Integration, was im Raum üblich ist (Tagesminimum, -mittel, -maximum, tags und nachts, getrennt für Heizperiode und Rest des Jahres), die tiefste Feuchte der letzten 14 Tage, wie schnell die Feuchte bei geschlossenem Fenster steigt und was Lüften wirklich bringt: welcher Teil des Unterschieds zur Außenluft beim Lüften verschwindet und wie viel davon innerhalb von 30 Minuten aus Wänden und Möbeln zurückkommt. Sobald zwei Lüftungsvorgänge ausgewertet sind, rechnet die Empfehlung mit der Feuchte, die Lüften tatsächlich erreicht: Sinkt sie dadurch nicht mindestens um den Mindest-Feuchteabfall, lautet die Empfehlung *Nicht lüften* statt *Jetzt lüften* (manchmal geht es eben nicht tiefer). Eine Hysterese verhindert ein Hin und Her um die Schwelle.

**Energiesparend lüften:** In der Heizperiode kostet Lüften Wärme, umso mehr, je kälter die Außenluft ist. Ein nur leicht zu feuchter Raum wartet deshalb: Die Feuchte muss die Schwelle um den *Energiespar-Zuschlag* je Kelvin Temperaturunterschied übersteigen (Standard 0,25 %/K, bei 21 °C innen und 1 °C außen also 5 % mehr). Der Zuschlag reicht nie über 70 %; ab dort wird gegen Schimmel immer gelüftet. Bis dahin lautet die Empfehlung *Nicht lüften*, ein offenes Fenster ergibt *Fenster schließen*. Hat das Lüften begonnen, läuft es bis zur Hysterese unter der nötigen Feuchte weiter. Der Zuschlag reicht nie über die *Schimmelgrenze* (Standard 70 %, je Raum einstellbar, z. B. niedriger bei kalten Außenwänden). Nach einer Lüftung bekommt der Raum eine *Pause* (Standard 30 Minuten), in der Feuchte aus Wänden zurückkommt, bevor erneut zum Trocknen geraten wird.

**Gelernte Lüftdauer:** Jeder Raum lernt aus seinen Lüftungen, wie schnell seine Fenster die Luft austauschen (umgerechnet auf den Temperaturunterschied, denn kalte Luft zieht schneller). Daraus schlägt das Attribut `airing_minutes` die Minuten vor, die bis zum *Lüftziel* (Standard 5 % unter der Schwelle) nötig sind, mal *Lüftdauer-Faktor*, begrenzt auf *kürzeste* und *längste Lüftdauer* (3 bis 20 Minuten). Bis zwei Lüftungen ausgewertet sind, gilt eine Tabelle nach Außentemperatur (5 Minuten bei Frost, 10 bis 10 °C, 15 bis 15 °C, sonst 20). Die Größe der Fenster zählt mit: Ein kleines Fenster hat die halbe Öffnung eines mittleren, ein großes das 1,6-fache, eine Tür das 2,5-fache. Gelernt wird der Luftaustausch je Öffnungsfläche, deshalb stimmt die Lüftdauer für jedes Fenster des Raums. Vorgeschlagen wird die größte Öffnung (Attribut `airing_window`) mit der Dauer dafür; ist schon ein Fenster offen, gilt die Dauer für die offenen Fenster. Die KI sieht bei jeder Lüftung vorgeschlagene und tatsächliche Dauer, Feuchte vorher, am tiefsten und 30 Minuten danach und passt alle diese Werte je Raum an.

**KI-Lüftungsprüfung:** Ganzjährig prüft die KI die Lüftungsschwellen jedes Bereichs mit Feuchtesensor, aufgebaut wie die Parameterprüfung der Heizkreise: Sie bekommt das Feuchteprofil, die Statistik seit der letzten Prüfung (Minuten feucht, ab 70 %, empfohlen, Fenster offen, unnötig offen, offen beim Heizen, Wechsel der Empfehlung) und den Verlauf früherer Prüfungen und darf je Bereich Feuchte-Schwelle, Hysterese, Mindest-Trocknungsvorteil, Übertemperatur der Referenz, Mindest-Feuchteabfall, Energiespar-Zuschlag, Schimmelgrenze, Lüftziel, Lüftdauer-Faktor, kürzeste und längste Lüftdauer, Pause nach dem Lüften, Mindest-Kühlvorteil, Kühl-Abstand und Kühlen-ab-Temperatur innerhalb der KI-Grenzen anpassen. Die konfigurierten Werte sind Startwerte; ändert man sie, ersetzen sie den Wert der KI. Das Intervall beginnt beim Grundintervall (6 h) und verdoppelt sich mit jeder Prüfung ohne relevante Änderung bis zum Höchstintervall (72 h); bleibt ein Raum lange feucht oder ändert sich etwas, beginnt es von vorn. Die Prüfung nutzt das gemeinsame Monatsbudget; ihre Anweisungen lassen sich unter *KI-Anweisungen* (Lüftungsprüfung) anpassen. Die gelernten Werte zeigt der Reiter **Lernwerte**.

## Installation über HACS

1. HACS öffnen, oben rechts im Menü **Benutzerdefinierte Repositories** wählen.
2. Repository `https://github.com/Jumpmaster2/AI-Heating-Assistant`, Typ **Integration**, hinzufügen.
3. **AI Heating Assistant** herunterladen und Home Assistant neu starten.
4. **Einstellungen > Geräte & Dienste > Integration hinzufügen > AI Heating Assistant**.

Voraussetzung: Home Assistant 2026.10 oder neuer. Für die KI ein API-Key von Anthropic (optional, ohne Key läuft nur die lokale Regelung). Bei der Einrichtung fragt der KI-Schritt nur den Key und die Uhrzeit des Nachtlaufs; Modell und Monatsbudget folgen erst, wenn ein Key eingegeben und angenommen wurde.

### Manuelle Installation

1. Den Ordner `custom_components/ai_heating_assistant` aus diesem Repository nach `config/custom_components/` von Home Assistant kopieren.
2. Home Assistant neu starten und die Integration wie oben unter Schritt 4 hinzufügen.

## Konfiguration

Die Auswahlfelder zeigen nur passende Entitäten (z. B. Temperatursensoren mit Geräteklasse Temperatur oder Einheit °C/°F/K, Feuchtesensoren mit Einheit %). Bereits gewählte Entitäten außerhalb dieser Auswahl bleiben gültig.

### Dashboard

Nach der Einrichtung gibt es in der Seitenleiste die Seite **AI Heating Assistant** (nur für Administratoren). **Konfigurieren** unter Einstellungen > Geräte & Dienste führt direkt dorthin.

* **Übersicht:** Heiztag mit Phase und Begründung, Heiztag manuell (Automatik, Heute heizen, Heute nicht heizen), alle Bereiche mit Temperatur, Sollwert, Status und Lüftungsempfehlung (anklicken öffnet das Thermostat), Schalter KI aktiv, letzte und nächste KI-Prüfung, nächster Nachtlauf, letzte Heiztag-Entscheidung mit Quelle (KI, Regel, beide einig), KI-Kosten im Monat, Hinweise (fehlende Entitäten, letzter KI-Fehler, Budget erreicht) und eine Zusammenfassung der Einstellungen.
* **Heizbereiche:** alle Bereiche als Tabelle; anklicken zum Bearbeiten, hinzufügen und löschen.
* **Lernwerte:** je Bereich mit Heizkreis eine kompakte Kachel mit Lernstand, Aufheiz- und Abkühlrate, Totzeit, Überschwingen, Erholung nach Lüften, Einfluss Außentemperatur und Sonne; aufklappbar die von der KI anpassbaren Regelparameter. Dazu die Heiztag-Regel (`theta`, bewertete Tage). Der Stift führt zum Bearbeiten der gelernten Werte.
* **Allgemein, Notfall & Lüftung, KI, Heiztag-Entscheidung:** alle Einstellungen nach Themen in Karten, jede Karte wird für sich gespeichert. Unter **KI** auch der API-Key (wird vor dem Speichern geprüft, der gespeicherte Key wird nie angezeigt) und die KI-Grenzen.

Die Einrichtung selbst läuft weiterhin als Dialog.

### Thermostat-Karte

Die Integration bringt eine eigene Dashboard-Karte mit, die wie die Thermostat-Karte von Home Assistant aussieht und zusätzlich die **Luftfeuchte** des Bereichs zeigt, in derselben Zeile wie die zweite Temperatur (die Karte wird dadurch nicht größer). Sie wird automatisch geladen (bei im UI verwalteten Ressourcen auch als Dashboard-Ressource eingetragen, damit die Companion-App sie zuverlässig lädt) und steht beim Hinzufügen einer Karte als **AI Heating Assistant Thermostat** zur Auswahl. Den Sollwert stellst du durch Ziehen am Punkt auf dem Ring oder mit den Pfeiltasten ein (eine Berührung woanders auf dem Ring scrollt nur die Seite), die drei Punkte öffnen das Thermostat. Mit fester Höhe (`grid_options` mit `rows` als Zahl) wird der Ring so verkleinert, dass er in die Kachel passt.

```yaml
type: custom:ai-heating-thermostat-card
entity: climate.wohnbereich
show_current_as_primary: true   # Ist-Temperatur groß, Sollwert klein (Standard: false)
show_humidity: true             # Standard: true
name: Wohnbereich               # optional
```

Die Luftfeuchte kommt vom Feuchtesensor des Bereichs (Attribut `current_humidity` des Thermostats); ohne Feuchtesensor bleibt sie weg. Nach einem Update ggf. den Browser-Cache leeren bzw. die App neu laden.

### Thermostat kompakt

Das Thermostat ohne Bogen, halb so hoch (Standard 6 × 2): oben der Name, groß die Ist-Temperatur und die Luftfeuchte, klein der Sollwert und der Status. Die Leiste links ist orange, solange geheizt wird, sonst grau. Ein Tipp öffnet das Thermostat zum Einstellen; auf dem Dashboard selbst wird nichts verstellt. Beim Hinzufügen einer Karte heißt sie **AI Heating Assistant Thermostat kompakt**.

```yaml
type: custom:ai-heating-thermostat-compact-card
entity: climate.wohnbereich
show_humidity: true   # Standard: true
name: Wohnbereich     # optional
```

### Raumklima-Kachel

Eine kompakte Kachel (Standard 6 × 1 wie die Kachel-Karte): oben der Name, darunter Temperatur und Luftfeuchte nebeneinander. Beim Hinzufügen einer Karte heißt sie **AI Heating Assistant Raumklima**. Die Werte kommen vom Thermostat des Bereichs oder von beliebigen Sensoren (auch für Bereiche ohne Heizkreis); ein angegebener Sensor hat Vorrang. Ein Tipp auf einen Wert öffnet die zugehörige Entität.

```yaml
type: custom:ai-heating-climate-tile-card
entity: climate.wohnbereich            # oder/und:
temperature_entity: sensor.temperatur_schlafzimmer
humidity_entity: sensor.luftfeuchtigkeit_schlafzimmer
name: Schlafzimmer                     # optional
```

### Einrichtung (global)

Temperatursensoren dürfen in °C, °F oder K melden; ohne Einheit gilt das Einheitensystem von Home Assistant. Gerechnet wird intern in °C, und alle Temperaturen in den Einstellungen (Sollwerte, Frostschutz, `theta`) werden in °C eingegeben. Die Thermostate zeigen Werte im Einheitensystem von Home Assistant.

| Option | Standard | Bedeutung |
|---|---|---|
| Außentemperatursensor | | z. B. `sensor.outdoor_temperature`; optional, wenn eine Wetter-Entität gewählt ist (dann gilt deren aktuelle Temperatur) |
| Außenfeuchtesensor | | optional, für die Lüftungsempfehlung |
| Wetter-Entität | | optional, Vorhersage für den Nachtlauf und die Sonnenprognose |
| PV-Leistungssensor | | optional, Sonnenindikator (W oder kW; ohne Einheit gilt W, eine andere Einheit wird mit Warnung ignoriert) |
| PV-Prognosesensor | | optional, nur mit PV-Leistungssensor: Energie der nächsten Stunde (Wh oder kWh) oder Leistung in einer Stunde (W oder kW); ohne ihn wird die Wettervorhersage genutzt |
| Wärmezähler | | optional, Zählerstand der hier geregelten Heizkreise (Wh, kWh, MWh, MJ oder GJ); seltene und grobe Werte sind kein Problem, siehe [Wärmezähler](#wärmezähler) |
| Heizperiode | 01.10. bis 31.03. (Südhalbkugel: 01.05. bis 30.09.) | im Dialog als Tag und Monat, im Panel im Format TT.MM.; der Vorschlag richtet sich bei der Einrichtung nach dem Breitengrad von Home Assistant |
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

Reihenfolge im Optionsmenü: Allgemein, Urlaub, Notfallregel, Lüftung, KI, Heiztag-Entscheidung (Experten), KI-Grenzen (Experten). Lernschritte und Entscheidungsphasen liegen in einklappbaren Abschnitten.

* **Allgemein:** Sensoren, Heizperiode und Frostschutz, Urlaub wie oben.
* **Notfallregel:** an, 1 K unter Sollwert (voraussichtlich nach der Vorlaufzeit, mindestens die Einschalthysterese), 45 min, Fenster 30 min unverändert.
* **Lüftung:** Mindestvorteil absolute Feuchte 0,8 g/m³, außen höchstens 4 K wärmer, Mindest-Kühlvorteil 1 K, Kühlen in der Heizperiode erst ab 1 K über Sollwert, optional Kühlen erst ab einer festen Raumtemperatur (z. B. 23,5 °C, ganzjährig, Standard aus), Nacht 20:00 bis 08:00 Uhr (Uhrzeiten, minutengenau). Alle Schwellen sind Startwerte für die KI-Lüftungsprüfung (an, Grundintervall 6 h, Höchstintervall 72 h).
* **KI:** Modell, Effort (Standard niedrig), Nachtlauf, Prüfintervall 4 h, Maximalintervall 48 h, Budget, Preise in USD je Million Tokens (Anthropic rechnet in US-Dollar ab; es wird nicht umgerechnet) (Eingabe, Ausgabe, Cache schreiben, Cache lesen; vorbelegt mit dem Listenpreis des Modells), maximale Ausgabe-Tokens.
* **KI-Grenzen:** Minimum, Maximum, größte Änderung je Prüfung für jeden Parameter.
* **Heiztag-Entscheidung:** gelerntes `theta` (änderbar), Bewertungsschwellen, Lernschritte, Bedingungen der Phasenwechsel.

Den API-Key änderst du im Dashboard unter **KI** oder über **Neu konfigurieren**.

### Heizbereiche

Im Dashboard unter **Heizbereiche** (oder unter der Integration **Heizbereich hinzufügen**). Je Bereich:

| Option | Standard |
|---|---|
| Name | |
| Temperatursensor, Feuchtesensor | z. B. `sensor.living_room_temperature` |
| Kleine, mittlere, große Fenster, Türen | Fensterkontakte nach Größe, z. B. `binary_sensor.living_room_window`; Türen nach draußen wie die Balkontür. Fenster früherer Versionen stehen bei „mittel“ |
| Luftzug aus anderen Räumen | optional: bis zu 4 Kombinationen von Fensterkontakten anderer Räume, die zusammen offen sein müssen |
| Heizkreis-Schalter | z. B. `switch.heating_circuit_1`; leer = nur Lüftungsempfehlung |
| Start-Sollwert, kleinster und größter Sollwert | 21 / 16 / 24 °C |
| Mindest-Ein- und -Ausschaltzeit | 10 / 10 min (fest) |
| Heizungsart | Fußbodenheizung (Standard), Heizkörper oder Andere; die KI beurteilt Trägheit und gelernte Werte danach. Die Regelung selbst lernt das Verhalten jedes Raums ohnehin. |
| Startwerte Fensterverzögerung, Erholungszeit, Totzeit, puffer | 5 min, 30 min, 30 min, 0,7 K; nur beim Anlegen |
| Feuchte-Schwelle | 60 % |
| Referenz-Temperatur und -Feuchte | optional, statt außen (Raum ohne eigenes Fenster) |
| Lüftungs-Sperr-Entität | optional |

Startwerte (auch `theta`) werden nur beim Einrichten bzw. Anlegen gesetzt und gelten, bis etwas gelernt wurde. Danach lassen sie sich nicht mehr ändern; stattdessen zeigt der Bereich unter **Gelernte Werte** die Werte, mit denen gerade geregelt wird (Fensterverzögerung, Erholungszeit, Totzeit, puffer), und das gelernte `theta` steht unter **Heiztag-Entscheidung**. Eine Änderung dort ersetzt den gelernten bzw. von der KI angepassten Wert, das Lernen geht von dort aus weiter, und das Logbuch vermerkt es.

## Entitäten

Entitäten, die nach einer Änderung nicht mehr entstehen (z. B. „Wärme heute“ nach dem Entfernen des Wärmezählers), werden beim nächsten Laden aus der Entitätsregistrierung entfernt. Schnell wechselnde Prognosewerte (`predicted_temperature`, `expected_peak`, `expected_pv_kw`) und große Attribute (Parameterliste, letzte Tage, Regel, KI-Zusammenfassung) zeichnet der Recorder nicht auf; die Werte sind auf die angezeigte Genauigkeit gerundet, damit nicht jede Minute ein neuer Zustand entsteht.

Bei neuen Installationen sind die Diagnose-Sensoren der Lernwerte (Aufheiz- und Abkühlrate, Überschwingen, Totzeit, Erholungszeit, Einfluss Außen und Sonne) zunächst deaktiviert; das Panel zeigt die Werte trotzdem an. Bei Bedarf lassen sie sich unter Einstellungen > Entitäten aktivieren. KI-Zeitstempel, KI-Kosten und Entscheidungsphase sind Diagnose-Entitäten. Ein neues Bereichsgerät kommt in den Home-Assistant-Bereich seines Temperatursensors.

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

`import_parameters`, `reset_learned`, `decide_heating_day`, `run_ai_check` und `run_ai_ventilation_check` (die drei letzten können KI-Kosten verursachen) dürfen nur Administratoren aufrufen; Automationen und Skripte ohne Benutzer dürfen sie weiter nutzen.

| Dienst | Zweck |
|---|---|
| `ai_heating_assistant.export_parameters` | Lernwerte und Parameter als JSON (Antwort des Dienstes) |
| `ai_heating_assistant.import_parameters` | Lernwerte und Parameter aus JSON setzen (z. B. Startwerte) |
| `ai_heating_assistant.reset_learned` | Lernwerte einzelner Bereiche auf die Startwerte zurücksetzen, optional auch die Parameter |
| `ai_heating_assistant.run_ai_check` | KI-Prüfung sofort starten |
| `ai_heating_assistant.run_ai_ventilation_check` | KI-Lüftungsprüfung sofort starten |
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

## Fehlerbehebung

* **Status *Sensorfehler*:** Der Temperatursensor liefert keinen, einen unmöglichen Wert oder eine Einheit, die keine Temperatur ist (Warnung im Protokoll). Der Kreis bleibt aus; nach 15 Minuten erscheint eine Reparaturmeldung.
* **Status *Aktor nicht erreichbar*:** Der Schalter ist `unavailable`. Folgt er Befehlen nicht, wird mit wachsendem Abstand erneut geschaltet; nach drei Versuchen erscheint eine Reparaturmeldung.
* **KI fragt nicht mehr:** Budget erreicht (Hinweis im Dashboard, Sensor *KI-Kosten im Monat* mit `budget_reached`) oder der API-Key wurde abgelehnt (erneute Authentifizierung unter Einstellungen > Geräte & Dienste).
* **Debug-Protokoll:** In der Integration *Debug-Protokollierung aktivieren* wählen, oder in `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.ai_heating_assistant: debug
    anthropic: debug
```

## Datenschutz

Ohne API-Key verlässt nichts das Haus. Mit Key gehen an Anthropic: die Bereichsnamen, Temperaturen, Soll- und Lernwerte, Kennzahlen seit der letzten Prüfung, Außentemperatur, PV-Leistung, eine kompakte Wettervorhersage, Wärmezählerwerte und der Verlauf der Heiztag-Entscheidungen. Entitäts-IDs, Standort und der API-Key selbst sind nicht Teil der Anfragen.

## Bekannte Einschränkungen

* Alle Temperaturen in den Einstellungen werden in °C eingegeben (Sensoren und Thermostate dürfen °F nutzen).
* Nur Schaltaktoren (an/aus) je Heizkreis, keine stetigen Ventile.
* Eine Instanz je Home Assistant.

## Beispiel für eine Automation

An einem Brückentag nicht heizen. Die Auswahl gilt für den Tag, an dem sie gesetzt wird; nach Mitternacht und vor dem Nachtlauf gesetzt, gilt sie für den neuen Tag:

```yaml
automation:
  - alias: "Kein Heizen am Brückentag"
    triggers:
      - trigger: time
        at: "00:30:00"
    conditions:
      - condition: state
        entity_id: calendar.brueckentage
        state: "on"
    actions:
      - action: select.select_option
        target:
          # mit deutscher Systemsprache bei der Einrichtung; die ID steht unter
          # Einstellungen > Entitäten (Englisch: ..._heating_day_override)
          entity_id: select.ai_heating_assistant_heiztag_manuell
        data:
          option: off_today
```

## Deaktivieren und Deinstallation

Wird die Integration deaktiviert oder entfernt, verschwindet ihre Seite aus der Seitenleiste, und sie schaltet alle eingeschalteten Heizkreise aus; sonst würde ein gerade laufender Kreis ohne Grenze weiterheizen. Dasselbe gilt für den Schalter eines gelöschten Heizbereichs und für einen Schalter, der in einem Bereich durch einen anderen ersetzt wurde. Ein Neuladen (z. B. nach einer Änderung der Einstellungen) oder ein Neustart von Home Assistant lässt die Kreise unverändert.

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
