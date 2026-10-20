# Audit: AI Heating Assistant (v0.11.0)

Stand: 2026-10-20 · Geprüft: alle Dateien des Repositorys (Commit `f7f302d`). `ruff check`/`ruff format --check` sauber, 141 Logik-Tests grün; die HA-Tests (`tests/ha`) wurden lokal nicht ausgeführt. Die Anthropic-API-Nutzung (Modell-IDs, `output_config`, Fallback-Beta, Preise) wurde gegen die aktuelle API-Referenz geprüft.

## 1. Zusammenfassung und Gesamtbewertung

**Zweck:** Die Integration regelt eine Fußbodenheizung lokal über einen Schaltaktor (`switch`/`input_boolean`) je Heizkreis. Sie lernt je Raum ein thermisches Modell (RLS: Aufheizen, Wärmeverlust, Sonne) sowie Totzeit, Überschwingen und Erholungszeit. Jede Nacht entscheidet sie, ob „Heiztag“ ist (lokale Regel `theta`/`puffer` plus Claude, Phasenmodell). Claude (Anthropic API) prüft periodisch die Regelparameter innerhalb fester Grenzen. Dazu kommen eine Lüftungsempfehlung (absolute Feuchte), Urlaub mit Vorheizen, Wärmezähler-Auswertung, ein Sidebar-Panel, Logbuch und Dienste.

**Architektur:**
- `__init__.py` richtet Dienste und WebSocket ein, außerdem Gerät, Coordinator, Plattformen und Panel.
- `coordinator.py` (DataUpdateCoordinator, Tick 60 s plus Zustandsänderungen) ist die Regelschleife. Er enthält Lernen, Heiztag-Entscheidung, KI-Planung und Speicherung (`Store`).
- `logic/` ist reine Logik ohne HA-Abhängigkeit (controller, learning, heating_day, ai_schema/policy, prompts, sun, energy, ventilation, start_values).
- Plattformen: `climate`, `sensor`, `binary_sensor`, `select`, `switch`.
- Konfiguration: `config_flow.py` (Config-, Options-, Reconfigure- und Subentry-Flow „Heizbereich“).
- `websocket.py` und `frontend/panel.js` bilden ein Admin-Panel mit allen Einstellungen.
- Weitere Module: `services.py`, `diagnostics.py`, `logbook.py`.
- Konfigurationsdaten: Optionen im Config Entry, Bereiche als Subentries, API-Key in `entry.data`.

**Datenfluss:**
1. Die Zustände der gewählten Entitäten (Temperatur, Feuchte, Fenster, PV, Wetter, Wärmezähler) gehen in den Coordinator-Tick.
2. `logic.controller.step` liefert daraus eine Schaltentscheidung.
3. Der Coordinator setzt sie per `switch.turn_on/turn_off` um.
4. Der Learner lernt aus dem Ergebnis.
5. Der Zustand wird in `.storage/ai_heating_assistant.<entry_id>` gespeichert.

**Externe Schnittstellen:** Anthropic Messages API (SDK `anthropic`, über HAs geteilten httpx-Client), `weather.get_forecasts`, der HA-Eventbus (Logbuch) und WebSocket (Panel). Es gibt keine lokalen Geräte-APIs, IPs oder Ports.

**Gesamtbewertung: gut (≈ 3,5 / 5).**

Stärken:
- Saubere Trennung von reiner Logik und HA, mit vielen gut lesbaren Unit-Tests (141 grün, inkl. Closed-Loop-Simulation).
- Die KI ist strikt begrenzt: Sie schaltet nie. Ihre Antworten werden per JSON-Schema validiert und auf Grenzen und Schrittweite geklemmt.
- Der API-Key wird nie geloggt, im Panel nicht ausgeliefert und in den Diagnosedaten geschwärzt.
- WebSocket und Panel sind nur für Admins.
- `async` wird korrekt genutzt, blockierende Initialisierung läuft im Executor.
- Coordinator, Subentries, `has_entity_name`, eindeutige `unique_id`s und Device-Registry werden genutzt.
- Übersetzungen de/en sind vollständig deckungsgleich (per Skript geprüft).
- `ruff` ist sauber.

Hauptschwächen:
1. Stille Annahme von **°C**: Mit dem US-Einheitensystem fällt die Regelung komplett aus, Frostschutz inklusive.
2. **Fail-safe-Verhalten** fehlt:
   - Kreise bleiben beim Entfernen oder Deaktivieren im letzten Zustand.
   - Ein Aktor- oder Sensorausfall erzeugt keine Warnung.
3. Kein **Reauth-Flow** und keine **Repairs**.
4. Systemspezifische Annahmen: Fußbodenheizung in den Prompts, € statt USD, Heizperiode der Nordhalbkugel, absolute PV-Schwellen.
5. UI: Entity-Selektoren ohne Gerätetyp-Filter, Fachbegriffe („theta“, „puffer“) ohne Erklärung, Freitext für Datumsangaben.
6. README veraltet und ohne Fehlerbehebung, Debug-Logging, Datenschutz und manuelle Installation.

**Quality Scale (Einschätzung):** Bronze erfüllt. Silber fehlt im Wesentlichen `reauthentication-flow` (Testabdeckung ist hier nicht messbar). Gold fehlen `repair-issues`, `entity-disabled-by-default`, `docs-troubleshooting` und `docs-known-limitations`. Platin fehlt `strict-typing`.

## 2. Alle Funde

Schweregrad: **Kritisch / Hoch / Mittel / Niedrig**. „zu prüfen“ heißt: Der Fund ist plausibel, aber nicht vollständig verifiziert.

| ID | Kategorie | Schweregrad | Datei:Zeile | Problem | Auswirkung | Lösungsvorschlag |
|---|---|---|---|---|---|---|
| F-01 | Logik / Allgemeingültigkeit | **Kritisch** (für °F-Nutzer) | `coordinator.py:608-615`, `climate.py:53,64`, `const.py:126-183`, `coordinator.py:1968-1983` | Alle Temperaturen (Raum, Außen, Referenz, Wetterprognose) werden ungeprüft als °C gelesen. `unit_of_measurement` und `hass.config.units` werden ignoriert. Auch die Defaults (21 °C, Frost 7 °C, theta 16 °C) sind °C. | Bei °F-Sensoren gilt z. B. 68 > 21, also wird nie geheizt. Frostschutz greift erst bei 7 °F (−14 °C). Die Heiztag-Regel ist ebenfalls falsch. Das Totalversagen geschieht still. | Beim Einlesen mit `TemperatureConverter` anhand der Sensoreinheit nach °C umrechnen und intern in °C rechnen. Die Wetterprognose von `hass.config.units.temperature_unit` umrechnen. Climate bleibt native °C, HA rechnet die Anzeige um. Bei fehlender oder unbekannter Einheit warnen. Tests mit `US_CUSTOMARY_SYSTEM`. |
| F-02 | Sicherheit (Aktor) / Lebenszyklus | **Hoch** | `__init__.py:66-77` | Beim Deaktivieren oder Entfernen der Integration bleibt jeder Heizkreis im letzten Zustand. | Ein laufender Kreis heizt unbegrenzt weiter. Das kostet Energie, überhitzt den Raum und bleibt oft unbemerkt. | In `async_remove_entry` und beim Unload mit gesetztem `entry.disabled_by` alle eigenen Kreise ausschalten, aber nicht bei einem Reload. Optional als Option „Kreise beim Deaktivieren ausschalten“ (Standard an). Test. |
| F-03 | Fehlerbehandlung / Ausfallsicherheit | **Hoch** | `coordinator.py:908-917,980-981`, `logic/controller.py:349-350` | Fehlt der Raumtemperatursensor, wird der Kreis abgeschaltet und auch der Frostschutz ist inaktiv. Ist der Schaltaktor `unavailable`, werden Befehle still ausgelassen, der Status zeigt aber weiter „Heizt“/„Bereit“. Es gibt keine Warnung und kein Repair. | Im Winter kann die Heizung stundenlang ausfallen, ohne dass es jemand merkt. | Neuen Status `actuator_unavailable` einführen. Nach N Minuten Ausfall ein Repair-Issue anlegen (`issue_registry`) für Temperatursensor, Aktor und Außentemperatur. Logbuch-Eintrag und README-Abschnitt. Fallback-Verhalten bei Sensorausfall dokumentieren; **zu prüfen** ist ein optionaler Notbetrieb. |
| F-04 | Fehlerbehandlung / Konformität | Mittel | `ai_client.py:110-111`, `coordinator.py:1555-1560`, `config_flow.py` (kein `async_step_reauth`) | Ein abgelehnter API-Key (401) landet nur im Logbuch und im Attribut `last_error`. Es gibt keinen Reauth-Flow und keine Benachrichtigung. | Die KI bleibt still aus, die Nutzer merken es nicht. Die Quality-Scale-Regel „reauthentication-flow“ ist verletzt. | Bei `AiAuthError` `entry.async_start_reauth(hass)` aufrufen. Kein `ConfigEntryAuthFailed` im Coordinator, damit die Regelung weiterläuft. `async_step_reauth`/`reauth_confirm` implementieren, mit Übersetzungen und Tests. |
| F-05 | Logik / Kosten | Mittel | `const.py:114-120`, `config_flow.py:221,238-241`, `sensor.py:259-260` | Die Preisvorschläge sind Anthropic-USD-Listenpreise (z. B. Opus 5.5: $4/$20 je MTok, Cache-Read $0,20 – verifiziert), werden aber als „€/MTok“ beschriftet. Kostensensor und Budget sind fest in „EUR“. | Kosten und Budget sind in der falschen Währung beschriftet. Die Werte stimmen für keinen Nutzer exakt. | Preise als USD kennzeichnen oder eine Währungsoption anbieten (Standard `hass.config.currency`) samt Umrechnungsfaktor. Die Einheit des Kostensensors aus der Option nehmen. |
| F-06 | Bug | Mittel | `coordinator.py:184,621-624,1136`, `strings.json:416` | „Lüftungs-Sperr-Entität“: Jeder Zustand außer off/idle/unknown/unavailable gilt als aktiv. Eine Beschattung (`cover`) im Zustand `open` blockiert also ebenfalls. | Gerade der dokumentierte Anwendungsfall („Beschattung geschlossen“) sperrt die Lüftungsempfehlung dauerhaft. | Domänenspezifisch auswerten: `cover` sperrt bei closed/closing, `climate` bei hvac_mode ≠ off, sonst bei `on`. Alternativ Sperrzustände einstellbar machen. Selector auf passende Domänen begrenzen. Test. |
| F-07 | Validierung / Logik | Mittel | `config_flow.py:705-716`, `websocket.py:233-256`, `coordinator.py:534-542` | Es wird nicht geprüft, ob ein Heizkreis-Schalter schon einem anderen Bereich zugeordnet ist. | Zwei Bereiche steuern denselben Kreis gegeneinander. `_switch_map` kennt nur den letzten Bereich, deshalb werden externe Schaltungen und Lernereignisse falsch zugeordnet. | Validierung im Subentry-Flow und im WS (`switch_in_use`) mit Übersetzung und Test. |
| F-08 | Ressourcenleck | **widerlegt** (war: Mittel, zu prüfen) | `coordinator.py:417-459`, `__init__.py:47-53` | Listener, Nachtlauf-Timer und KI-Timer werden in `_async_setup` registriert, bevor der erste Refresh erfolgreich war. Schlägt `_async_update_data` beim ersten Lauf fehl (`ConfigEntryNotReady`), bleiben sie am verworfenen Coordinator hängen – es sei denn, HA ruft dessen `async_shutdown` selbst über `async_on_unload` auf (je nach HA-Version zu prüfen). | Beim Setup-Retry entstehen doppelte Regelschleifen, Nachtläufe und KI-Abfragen. | `entry.async_on_unload(coordinator.async_shutdown)` sofort nach dem Erzeugen registrieren, Shutdown idempotent machen. Alternativ Listener erst nach dem erfolgreichen ersten Refresh registrieren. Test für den Setup-Retry. **Nachprüfung:** HA 2026.10.2 registriert `async_shutdown` des Coordinators selbst per `async_on_unload` (`helpers/update_coordinator.py` L155-156) und arbeitet die Unload-Callbacks auch bei `ConfigEntryNotReady` ab (`config_entries.py` L1004-1005). Es gibt also kein Leck; ein Regressionstest (`test_failed_first_refresh_leaves_no_listeners`) sichert das ab. |
| F-09 | Allgemeingültigkeit | Mittel | `logic/prompts.py:12-31,33-58` | Die KI-Prompts setzen eine Fußbodenheizung voraus („Floors store a lot of heat“). | Bei Heizkörpern oder Konvektoren sind die Annahmen zu Trägheit und Überschwingen falsch, die Ratschläge der KI ebenso. | Option „Heizungsart“ (Fußboden/Heizkörper/Sonstige) je Bereich anbieten und im Prompt, ggf. auch in den Lerngrenzen, nutzen. |
| F-10 | Performance | Mittel | `climate.py:96-107`, `sensor.py:58-75,127-130`, `binary_sensor.py:40-56`, `sensor.py:219-226` | `predicted_temperature`, `expected_peak`, `expected_pv_kw`, `heat_rate` und `cool_rate` ändern sich fast jede Minute. Große Attribute (`last_days`, `rule`, `parameters`) werden mit aufgezeichnet. | Viele Recorder-Zeilen je Bereich und Minute, eine wachsende Datenbank und mehr Last auf schwacher Hardware. | `_unrecorded_attributes` für schnelle und große Attribute setzen und gröber runden. Diagnose-Sensoren standardmäßig deaktivieren (siehe UI-12). |
| F-11 | Abhängigkeit / Ressourcen | Mittel | `manifest.json:11`, `ai_client.py:61-73` | `anthropic>=0.125.0` hat keine Obergrenze. SDK 1.x (httpx2) lehnt HAs httpx-Client mit `TypeError` ab (verifiziert). Der Fallback erzeugt dann pro Reload einen eigenen Client, der nie geschlossen wird. Ein Konflikt mit der Pin-Version der Core-Integration `anthropic` ist **zu prüfen**. | Verbindungs-Pools lecken bei jedem Reload, die geteilte Session geht verloren, Installationskonflikte sind möglich. | Version pinnen (`anthropic==x.y.z`). Den eigenen Client in `async_shutdown` schließen. Bei 1.x bewusst `DefaultAsyncHttpxClient` nutzen. |
| F-12 | Robustheit | Mittel | `coordinator.py:717,824-827,1226-1244,1299-1300,1614` | `weather.get_forecasts` wird mit `blocking=True` und ohne Timeout im Regel-Tick aufgerufen. | Hängt die Wetterintegration, verzögert sich die Regelung **aller** Bereiche. | Den Aufruf in `asyncio.timeout(10)` kapseln. Die Prognose im Hintergrund aktualisieren und den Tick nicht darauf warten lassen. |
| F-13 | Doku | Mittel | `README.md:11`, `README.en.md:11` | Versionsangabe veraltet (0.10.2 statt 0.11.0). Es fehlen: manuelle Installation, Debug-Logging, Fehlerbehebung, Datenschutz (Bereichsnamen, Temperaturen und Prognose gehen an Anthropic), bekannte Einschränkungen und Deinstallation. | Die Einrichtung ohne Vorwissen ist erschwert, es fehlt Transparenz über Datenabfluss. | Siehe Abschnitt 5. |
| F-14 | UX / Validierung | Mittel | `config_flow.py:157-170,619-626,633,650` | Die Entity-Selektoren filtern nicht nach `device_class`, z. B. zeigt „Außentemperatur“ alle Sensoren. Ob ein Sensor numerisch ist und eine Temperatur-Einheit hat, wird nicht geprüft. | Falsche Auswahl ist leicht und fällt erst später auf. | Siehe UI-1. Bei der Einrichtung zusätzlich numerischen Zustand und Einheit prüfen (`sensor_not_numeric`, `unit_unsupported`). |
| F-15 | Quality Scale (stale entities) | Niedrig | `sensor.py:169-170`, `climate.py:33-37`, `sensor.py:171-179` | Entitäten, die nach einer Änderung nicht mehr erzeugt werden (Wärmezähler entfernt, Heizkreis aus einem Bereich entfernt), bleiben als „nicht verfügbar“ in der Registry. | Verwaiste Entitäten verwirren und landen in Dashboards. | Beim Setup verwaiste `unique_id`s der Integration aus der Entity-Registry entfernen. |
| F-16 | Bug | Niedrig | `logic/prompts.py:61-62` (vgl. `messages.py:86`, `panel.js:402-405`) | Die Prompt-Sprache passt nur bei exakt „de“ oder „en“. Bei „de-CH“ antwortet die KI englisch, das Logbuch ist aber deutsch. | Gemischtsprachige Begründungen. | Sprachpräfix normalisieren oder die HA-Sprache generell an Claude weitergeben. |
| F-17 | Bug | Niedrig | `logic/ai_schema.py:248-250` | Die Schrittbegrenzung wird **nach** der Grenzklemmung angewandt. Wurden die Grenzen verengt, kann der neue Wert außerhalb [min, max] liegen. Bestehende Werte außerhalb der Grenzen bleiben ohnehin unverändert. | Parameter verletzen die eingestellten KI-Grenzen. | Abschließend erneut auf [min, max] klemmen. Beim Speichern der Grenzen die aktuellen Parameter klemmen. Test. |
| F-18 | Robustheit | Niedrig | `coordinator.py:608-615` | `_float` akzeptiert `nan`/`inf` und unplausible Werte. | Ein defekter Sensor verfälscht Regelung und RLS-Modell, das dann auf die Obergrenze geklemmt wird. | `math.isfinite` plus Plausibilitätsbereich (Temperatur −50…+80 °C, Feuchte 0…100 %). |
| F-19 | Logik | Niedrig | `coordinator.py:626-640,775-778` | Ein PV-Sensor ohne oder mit unbekannter Einheit wird als W gedeutet. Ein Wärmezähler mit unbekannter Einheit wird still ignoriert. | Falsche Sonnenwerte, „Wärme“ fehlt ohne Hinweis. | Einmal warnen bzw. Repair anlegen. Selector-`device_class` power/energy (siehe UI-1). |
| F-20 | Codequalität / Logik | Niedrig | `sensor.py:266-270`, `logic/ai_policy.py:69-73` | `AiCostSensor.native_value` ändert das Budget (`roll`) im State-Property. `budget_reached` bleibt nach einer Budgeterhöhung bis zur nächsten KI-Abfrage gesetzt. | Nebeneffekt beim Lesen, irreführende Anzeige. | `roll` im Tick ausführen, `blocked` aus spent/limit ableiten. |
| F-21 | Sicherheit (Dienste) | Niedrig | `services.py:80-124` | `import_parameters`, `reset_learned` und das kostenpflichtige `run_ai_check` kann jeder Benutzer aufrufen. Panel und WS sind dagegen nur für Admins. | Nicht-Admins können Lernwerte überschreiben und Kosten verursachen. | Admin-Prüfung über `call.context.user_id` (`hass.auth.async_get_user` → `is_admin`) für ändernde und kostenpflichtige Dienste. |
| F-22 | Fehlerbehandlung | Niedrig | `services.py:88-97` | `except Exception` macht aus jedem Programmfehler „Import fehlgeschlagen“. | Bugs werden verdeckt. | Gezielt `HomeAssistantError`, `TypeError`, `ValueError` fangen. |
| F-23 | Fehlerbehandlung | Niedrig, **zu prüfen** | `coordinator.py:736-739,1246-1256` | Wirft `_decide` eine unerwartete Ausnahme, bleibt die Entscheidung abgelaufen und wird bei jedem Tick (minütlich) neu versucht, ggf. mit KI-Abfrage. | Log-Flut, mögliche Kosten. | Backoff: nach einem Fehlschlag frühestens nach 15 min erneut versuchen, Fehler einmal loggen. |
| F-24 | Kosten / KI | Niedrig, **zu prüfen** | `const.py:154`, `ai_client.py:87-133` | Bei Opus 5.5 ist Thinking immer an (Standard-Effort medium). `max_output_tokens` = 4000 enthält auch die Denk-Tokens. | Bei Effort medium oder high droht „answer truncated“: Die Antwort ist bezahlt, wird aber verworfen. | Standard auf 8000–16000 erhöhen. Die Kostenschätzung auf gemessene Mittelwerte stützen statt auf das Maximum. Hinweistext. |
| F-25 | Kosten | Niedrig | `coordinator.py:1563`, `ai_client.py:96-98` | Springt der Server-Fallback auf ein anderes Modell, wird trotzdem mit den Preisen des gewählten Modells gerechnet. | Kosten leicht falsch. | `message.model` bzw. `usage.iterations` auswerten. |
| F-26 | Kosten | Niedrig, **zu prüfen** | `coordinator.py:1154-1159,1192-1201` | Jede Sollwertänderung, auch durch Automationen, setzt das adaptive KI-Intervall zurück. | Bei automatisierten Sollwerten wächst das Intervall nie, also mehr KI-Kosten. | Nur bei einer Änderung ab 0,5 K zurücksetzen oder per Option. |
| F-27 | Lebenszyklus | Niedrig | `__init__.py:66-71`, `websocket.py:97-102` | Das Panel bleibt nach dem Deaktivieren in der Seitenleiste. Der WS arbeitet dann mit einem nicht geladenen Eintrag. | Verwirrende Bedienung. | Panel beim Unload entfernen oder „nicht geladen“ klar anzeigen. |
| F-28 | Lebenszyklus | Niedrig, **zu prüfen** | `__init__.py:66-71` | `async_shutdown` läuft ggf. doppelt: explizit und automatisch durch den Coordinator. | Es wird doppelt gespeichert (harmlos). | Nur einmal aufrufen (zusammen mit F-08). |
| F-29 | Robustheit | Niedrig | `coordinator.py:980-981,1035-1047` | Reagiert ein Aktor nicht, wird jede Minute erneut geschaltet. | Last auf dem Funkbus, keine Rückmeldung an die Nutzer. | Wiederholung mit Backoff, nach N Versuchen Warnung/Repair (mit F-03). |
| F-30 | Konformität | Niedrig | `coordinator.py:554,591` | `hass.async_create_task` statt `config_entry.async_create_task`. | Die Tasks sind nicht an den Lebenszyklus des Eintrags gebunden. | Auf `config_entry.async_create_task` umstellen. |
| F-31 | Übersetzung | **widerlegt** (war: Niedrig) | `strings.json` (`config.abort`, `config_subentries.heating_area.abort` fehlen) | `single_instance_allowed` und `reconfigure_successful` haben keine Texte. | Die UI zeigt Rohschlüssel. | `abort`-Abschnitte in strings/de/en ergänzen. |
| F-32 | UI | Niedrig | `messages.py:8-21`, `coordinator.py:1351-1357,1443-1450,1705-1713` | Das Logbuch zeigt interne Schlüssel: `rule_fallback`, `ai_leads`, `unclear`, Fehler „A/B“, `hysteresis_on`. | Für Laien unverständlich. | Übersetzte Bezeichnungen verwenden (siehe UI-10). |
| F-33 | Konformität | Niedrig | `manifest.json` | `loggers: ["anthropic"]` fehlt. `iot_class: calculated` trotz Cloud-API ist **zu prüfen**. | Debug-Logging des SDK lässt sich nicht über die UI aktivieren. | `loggers` ergänzen und die iot_class bewerten. |
| F-34 | CI / Lieferkette | Niedrig | `.github/workflows/validate.yml:16,21`, `tests.yml:23-26` | Die Actions stehen auf `@master`/`@main` statt fester Versionen. CI prüft weder `ruff format --check` noch mypy. | Ungeprüfte Fremdänderungen in der CI. | Versionen oder SHAs pinnen und die fehlenden Checks ergänzen. |
| F-35 | Codequalität | Niedrig | `websocket.py:18-33`, `climate.py:43`, `coordinator.py:323-328`, `config_flow.py:279-293` | `websocket.py` importiert private `_`-Funktionen aus `config_flow`. Die Übersetzung `entity.climate.area.name` wird wegen `_attr_name = None` nie genutzt. Die Property `opts` baut bei jedem `opt()` ein neues Dict (Hunderte Aufrufe je Tick). Der Options-Schritt `advanced` heißt „Heiztag-Entscheidung“. Einige Typen sind nur `Any`/`dict`. | Wartbarkeit und etwas Performance. | Öffentliche Schema-Helfer verwenden, Optionen einmal je Tick cachen, Typen schärfen, mypy einführen. |
| F-36 | Validierung | Niedrig | `config_flow.py:705-716`, `coordinator.py:1791,1812` | Bei mehreren Fehlern wird nur der letzte `base`-Fehler gezeigt. Doppelte Bereichsnamen sind erlaubt, Export und Import schlüsseln aber nach Namen. | Unklare Fehlermeldungen, Import trifft den falschen Bereich. | Fehler feldbezogen melden (`min_target`/`max_target`) und eindeutige Namen erzwingen. |
| F-37 | Logik | Niedrig, **zu prüfen** | `coordinator.py:376-387`, `logic/controller.py:364-365` | „Heute heizen“ außerhalb der Heizperiode setzt den Heiztag auf „an“, heizt aber nicht (Status `out_of_season`). | Widersprüchliche Anzeige. | Das Verhalten festlegen: Override wirkt auch außerhalb der Saison, oder die Auswahl wird dort gesperrt bzw. erklärt. |
| F-38 | Performance (Panel) | Niedrig | `frontend/panel.js:369-384,517-538` | Bei jedem hass-Update werden alle Registry-Entitäten gezählt. Die Datalists enthalten **alle** Entitäten des Systems. | Großes Datenvolumen und spürbar träge bei großen Installationen. | Zählung nur bei Registry-Events, gefilterte und lazy erzeugte Listen bzw. `ha-selector` (UI-11). |
| F-39 | Allgemeingültigkeit | Niedrig | `coordinator.py:176,182`, `logic/sun.py:22` | `SUN_OVERHEAT_KW = 0.3` und `PV_NEGLIGIBLE_KW = 0.05` sind absolut, also von der Größe der PV-Anlage abhängig. | Bei kleinen oder großen Anlagen wird „Sonne“ falsch bewertet. | Relativ zur gelernten Klarhimmel-Skala rechnen (z. B. 10 %), siehe Abschnitt 3. |

**Geprüft und unauffällig:**
- Keine hartcodierten Secrets, IPs, Hostnamen oder Benutzernamen (Grep).
- Keine deaktivierte SSL-Prüfung.
- Der API-Key steht nur in `entry.data` und ist in den Diagnosedaten geschwärzt.
- Prompt-Injection über Bereichsnamen ist unkritisch, weil Antworten schema-validiert und geklemmt werden und die KI nicht schaltet.
- Die Panel-Ausgabe wird durchgehend escaped (`esc`).
- Keine blockierenden Aufrufe im Event Loop.
- Listener und Timer werden beim Unload aufgeräumt (Ausnahme F-08).
- Die Übersetzungen de/en sind vollständig deckungsgleich.

## 3. Systemspezifische Werte → vorgeschlagene Einstellungen

| Wert (heute) | Ort | Vorschlag | Flow | Standard | Validierung / Erklärung |
|---|---|---|---|---|---|
| Temperatureinheit °C (fest) | überall (F-01) | keine Option: automatisch aus der Sensoreinheit bzw. `hass.config.units` umrechnen | – | Einheit des Sensors | Unbekannte Einheit → Fehler `unit_unsupported` |
| Währung € bei USD-Preisen | `const.py:114-120`, `sensor.py:260` | „Währung“ und „Umrechnungsfaktor USD → Währung“ | Options › KI | `hass.config.currency`, Faktor 1,0 | Faktor > 0. Erklärung: „Anthropic rechnet in USD ab.“ |
| Heizperiode 01.10.–31.03. | `const.py:127-128` | Standard abhängig von der Hemisphäre (`hass.config.latitude < 0` → 01.05.–30.09.). Eingabe per Tag/Monat-Auswahl statt Freitext | Config + Options › Allgemein | je nach Breitengrad | gültiges Datum, Jahreswechsel erlaubt |
| Heizungsart Fußboden (fest im Prompt) | `logic/prompts.py` | „Heizungsart“: Fußboden / Heizkörper / Sonstige | Subentry (je Bereich) | Fußboden | Select. Beeinflusst Prompt und Lerngrenzen |
| Aktor nur `switch`/`input_boolean` | `config_flow.py:633` | zusätzlich `valve` (öffnen/schließen); `climate` **zu prüfen** | Subentry | – | Domäne prüfen |
| Außentemperatur Pflicht | `config_flow.py:160` | optional mit Fallback auf das `temperature`-Attribut der Wetter-Entität | Config + Options › Allgemein | erste Wetter-Entität | Mindestens eines von beiden ist Pflicht |
| „Immer heizen unter Sollwert − 1 K“ | `logic/controller.py:11` | „Zwangsheizen unter Sollwert minus“ | Options › Notfallregel | 1,0 K | 0,3–3 K |
| Prognosevertrauen 70 % | `logic/sun.py:22` | „Vertrauen in PV-/Wetterprognose“ | Options › Allgemein (erweitert) | 70 % | 0–100 % |
| PV-Schwellen 0,3 kW / 0,05 kW | `coordinator.py:176,182` | relativ zur gelernten Klarhimmel-Leistung | intern (keine Option) | 10 % / 2 % | – |
| Kurzlüften < 120 s ignorieren | `logic/controller.py:12` | „Kurzes Öffnen ignorieren unter“ | Subentry › Startwerte bzw. Options | 2 min | 0–10 min |
| Sicherheitsmargen der Regel 2 K / 0,5 K | `logic/heating_day.py:45-50` | „Regel sicher ab Abstand“ (Tmax, Bereich) | Options › Heiztag-Entscheidung (Experten) | 2,0 K / 0,5 K | 0–10 K / 0–3 K |
| Kälte- und Überheiz-Schwellen der KI-Prüfung 0,3 K / 0,2 K / 4 h | `coordinator.py:173-175` | mit `too_cold_margin` vereinheitlichen bzw. Expertenoption | Options › Heiztag-Entscheidung (Experten) | wie heute | 0–2 K / 0–12 h |
| Nachtfenster 20–8 Uhr (Stundenzahl) | `const.py:142-143` | Zeitauswahl statt Zahl | Options › Lüftung | 20:00 / 08:00 | – |
| Totzeit-/Erholungsgrenzen 5 min–4 h | `logic/learning.py:33-34` | an die Heizungsart koppeln (Heizkörper z. B. 1–60 min) | – (abgeleitet) | – | – |
| Gerätenamen und Sidebar-Titel englisch | `entity.py:16-19,50-51`, `panel.py:39` | Geräte-`translation_key`, Sidebar-Titel aus der HA-Sprache | – | – | – |
| Gerät ohne HA-Bereich | `entity.py:47-52` | `suggested_area` aus dem Bereich des Temperatursensors | – | automatisch | – |

**Einrichtung ohne Vorwissen / Discovery:** Eine Geräte-Discovery ist nicht anwendbar, weil keine Hardware angebunden wird. Vorgeschlagen werden Vorbelegungen:
- die erste `weather.*`-Entität;
- eine Außentemperatur per `device_class: temperature` plus Name/Bereich „außen/outdoor“, sonst das Wetter-Attribut;
- im Bereichs-Flow optional ein erster Schritt „HA-Bereich wählen“, der Temperatur-, Feuchte- und Fenstersensoren dieses Bereichs vorschlägt.

Die Startwerte haben sinnvolle Defaults. Die Einrichtung ist mit den Vorbelegungen in zwei Minuten möglich.

## 4. UI-Verbesserungen (Vorher → Nachher)

1. **Entity-Selektoren gefiltert** (F-14). Vorher: „Außentemperatursensor“ listet alle `sensor.*`. Nachher: `EntitySelectorConfig(domain="sensor", device_class="temperature")`. Ebenso:
   - Feuchte → `humidity`
   - PV → `power`
   - PV-Prognose → `energy`/`power`
   - Wärmezähler → `energy`
   - Raum- und Referenzsensoren entsprechend
   - Fenster → `filter=[{domain: binary_sensor, device_class: [window, door, opening]}, {domain: input_boolean}]`
   - Sperr-Entität → begrenzte Domänen
2. **Heizperiode:** Vorher Freitext „TT.MM.“ mit Fehler „Bitte im Format TT.MM. angeben“. Nachher je Datum „Tag“ (Zahl 1–31) und „Monat“ (übersetzte Auswahl). Ungültige Kombinationen wie 31.02. werden feldbezogen gemeldet.
3. **Nachtbeginn/-ende:** Vorher Zahl 0–23 „h“, nachher `TimeSelector`.
4. **KI-Schritt bei der Einrichtung:** Vorher Modell, Nachtlauf und Budget auch ohne Key. Nachher zuerst der Key (optional); Modell, Budget und Preise nur mit Key. Preise mit Einheit „USD/MTok“ bzw. der gewählten Währung.
5. **Fachbegriffe erklären bzw. umbenennen:**
   - „theta“ → „Heizgrenze (theta)“ / „Heating threshold (theta)“
   - „puffer“ → „Reserve über Sollwert“ / „Margin above target“ (im Englischen steht heute das deutsche „puffer“)
   - „Totzeit“ → „Totzeit (bis der Raum wärmer wird)“
   - „Hysterese“, „Effort“, „Tokens“, „absolute Feuchte (g/m³)“ jeweils in einem Satz erklären
   - Phasen „KI führt / Gemeinsam / Regel führt“ und Fehler „A/B“ im Text erklären
6. **Beispiele in jeder `data_description`.** Sie fehlen heute u. a. bei Urlaubstemperatur, Vorheiz-Reserve, Nachtstunden, Prüfintervall, Monatsbudget („5 € ≈ … Abfragen/Monat“), Notfall- und Bewertungsschwellen und Phasenwerten.
7. **Fehlermeldungen mit Was und Wie** (mit `description_placeholders`):
   - `min_above_max`: Vorher „Minimum muss unter dem Maximum liegen.“ Nachher „Der kleinste Sollwert ({min} °C) muss kleiner sein als der größte ({max} °C). Bitte einen der beiden Werte ändern.“ Feldbezogen statt `base`.
   - `invalid_auth`: Nachher „Anthropic hat den API-Key abgelehnt. Prüfe ihn unter console.anthropic.com → API Keys und füge ihn ohne Leerzeichen ein. Ohne Key läuft die lokale Regelung weiter.“
   - `cannot_connect`: Nachher „Anthropic ist nicht erreichbar. Prüfe Internetverbindung, Proxy und Firewall. Der Key wurde nicht gespeichert.“
   - Neu: `switch_in_use`, `sensor_not_numeric`, `unit_unsupported`, `reauth_*`.
8. **Abbruchgründe übersetzen** (F-31): `single_instance_allowed`, `reconfigure_successful`, `reauth_successful`.
9. **Optionsmenü:**
   - Reihenfolge: Allgemein, Urlaub, Notfallregel, Lüftung, KI, Heiztag-Entscheidung (Experten), KI-Grenzen (Experten).
   - Schritt-ID `advanced` → `decision`.
   - Expertenwerte (Lernschritte, Phasen) in einklappbaren Sections.
10. **Logbuch** (F-32): Vorher „Heiztag ja (Quelle: rule_fallback, Phase: ai_leads)“. Nachher „Heiztag ja (Quelle: Regel ohne KI, Phase: KI führt). …“ Bedarf „unklar“, Fehler „zu kalt ohne Heizen“ statt „A“, Parameter „Einschalt-Hysterese“ statt `hysteresis_on`.
11. **Panel:** HA-eigene `ha-selector`/`ha-form` verwenden statt Textfeld plus `<datalist>` (Gerätenamen, Bereiche, Filter, mobil bedienbar). HA-Dialog statt `confirm()`. Status „Aktor nicht erreichbar“ anzeigen.
12. **Entitäten:**
   - Diagnose-Sensoren (Aufheiz- und Abkühlrate, Überschwingen, Totzeit, Erholungszeit, Einfluss Außen/Sonne) standardmäßig **deaktiviert**. Voraussetzung: Das Panel liest die Lernwerte per WS statt aus Entitätszuständen, sonst bleibt die Lernwerte-Kachel leer.
   - „Letzte/Nächste KI-Prüfung“, „KI-Kosten“ und „Entscheidungsphase“ als `EntityCategory.DIAGNOSTIC`.
   - Neuer Status `actuator_unavailable`.
   - Icon für „Nächste KI-Prüfung“ neutral (`mdi:robot-outline`/`mdi:clock-outline` statt `robot-confused`).
13. **Repairs** statt nur Logbuch: ungültiger API-Key, Sensor oder Aktor fehlt bzw. nicht erreichbar, unbekannte Einheit.

## 5. Dokumentation und Tests

**README (de/en), was fehlt:**
- Versionsangabe aktualisieren (0.10.2 → aktuell).
- Manuelle Installation (`custom_components/ai_heating_assistant` kopieren, Neustart).
- Debug-Logging per YAML (`logger: logs: custom_components.ai_heating_assistant: debug`, `anthropic: debug`) und über die UI.
- Fehlerbehebung: Status `sensor_error`, Aktor nicht erreichbar, KI-Fehler, Budget erreicht, „keine Heiztage“, Diagnosedaten herunterladen.
- Datenschutz: welche Daten an Anthropic gehen (Bereichsnamen, Temperaturen, Prognose, Lernwerte – kein Standort, kein Key im Log).
- Bekannte Einschränkungen: °C (bis F-01), nur Schaltaktoren, eine Instanz, auf Fußbodenheizung optimiert.
- Deinstallation (was mit den Kreisen passiert, F-02).
- Beispiele: Automation für Urlaub und Override, Dashboard-Karte.
- Jede Option mit Beispiel; eine Tabelle der Entitätsattribute.

**Ungetestete kritische Fälle** (`pytest-homeassistant-custom-component`):
- **Config Flow:**
  - Fehler `cannot_connect`
  - Abbruch `single_instance_allowed`
  - Reconfigure mit ungültigem Key und Entfernen des Keys (leer)
  - Weiterleitung in den Subentry-Flow inklusive Abschluss
- **Subentry-Flow:**
  - Fehler `name_required`, `target_out_of_range`, `reference_incomplete`
  - Reconfigure ohne geladenen Coordinator
  - (nach F-07) `switch_in_use`
- **Options Flow:**
  - Schritte `general` (optionale Entitäten leeren), `vacation` (Rückkehr-Entität leeren), `rules`
  - `advanced` bei nicht geladenem Eintrag
- **Migration** `async_migrate_entry` (Minor 1 → 2) und `async_remove_entry` (Store gelöscht, Panel entfernt).
- **Fehlerfälle:**
  - Temperatursensor `unavailable` → `sensor_error` und Kreis aus
  - Aktor `unavailable`
  - `AiAuthError` zur Laufzeit (nach F-04: Reauth gestartet)
  - Wetterdienst wirft bzw. hängt
  - Setup-Retry ohne Listener-Leck (F-08)
- **Dienste:** `run_ai_check` bei deaktivierter KI (`ai_disabled`), `decide_heating_day` mit `use_ai: false`, `unknown_area`, Import mit ungültigen Daten.
- **Entitäten:** Select-Override (inkl. Rücksetzen am Folgetag), KI-Schalter an/aus.
- **Lüftung:** Sperr-Entität (Cover, Klima), Referenzraum nachts.
- **Prognosen:** `_today_extremes`, `_hourly_compact`, `_return_ts` mit `sensor`/`datetime`/`input_datetime`, PV-Einheiten W/kW/MW.
- **Zeit:** Nachtlauf über eine Zeitumstellung (DST).
- **Einheiten:** Einheitensystem °F (nach F-01).
- **Hinweis:** Die HA-Tests wurden lokal nicht ausgeführt (fehlende Testabhängigkeit). In der CI laufen sie mit Python 3.14.

## 6. Priorisierte Reihenfolge der Behebung

1. **F-01** Temperatureinheiten (°F), mit Tests.
2. **F-03** + **F-29** Aktor- und Sensorausfall: Status, Backoff, Repairs.
3. **F-02** Kreise beim Deaktivieren und Entfernen ausschalten.
4. **F-08** + **F-28** Setup-Retry ohne Listener-Leck, Shutdown idempotent.
5. **F-06** Sperr-Entität und **F-07** doppelter Schalter.
6. **F-04** Reauth-Flow (+ Repair).
7. **F-11** SDK pinnen und Client schließen, **F-12** Prognose-Timeout, **F-23** Backoff des Nachtlaufs.
8. **F-05** Währung, **F-24** / **F-25** / **F-26** Kosten.
9. Kleine Bugs **F-16**, **F-17**, **F-18**, **F-19**, **F-20**, **F-36**, **F-37**.
10. **F-10** / **F-15** Recorder-Last und verwaiste Entitäten.
11. Optionen aus Abschnitt 3: Heizungsart (F-09), Heizperiode nach Hemisphäre, Außentemperatur-Fallback, Prognosevertrauen, Zwangsheizen, relative PV-Schwellen (F-39).
12. UI aus Abschnitt 4: Selektoren, Texte, Fehlermeldungen, Abbruchgründe (F-31), Logbuch (F-32), Entitätskategorien.
13. Dienste **F-21** / **F-22**, Lebenszyklus **F-27** / **F-30**.
14. Rest: **F-33**, **F-34**, **F-35**, **F-38**.
15. README und Tests laufend in jedem Schritt; Abschluss-Review der Doku (F-13).

## 7. Umsetzungsstand (Branch `ccr-739e6cae-60cxas`)

Jeder Schritt hat Tests, ruff (Prüfung und Format) sowie Übersetzungen de/en und eine höhere Version. Nach jedem Schritt lief ein Review mit unabhängiger Gegenprüfung; bestätigte Review-Funde sind in eigenen Commits behoben.

| Fund | Stand | Commit(s) |
|---|---|---|
| F-01 Temperatureinheiten | behoben | `f9227b3`, `cf7cc33` (Thermostat in °F) |
| F-02 Kreise beim Deaktivieren/Entfernen aus | behoben | `efa3744`, `cf7cc33` (Wiederholung beim nächsten Start), Nachprüfung: noch nicht ausgeschaltete freigegebene Kreise auch beim Entfernen und Deaktivieren |
| F-03 Ausfall Sensor/Aktor, Repairs | behoben | `b8a6770`, `cf7cc33` (ignorierte Meldungen bleiben). Ein Notbetrieb bei Sensorausfall ist **nicht** eingebaut (zu prüfen, ob gewünscht). |
| F-04 Reauth | behoben | `9df0cfc` |
| F-05 USD | behoben | `2fd4f72` |
| F-06 Sperr-Entität | behoben | `d3143c4` |
| F-07 doppelter Schalter | behoben | `d3143c4` |
| F-08 Listener-Leck | widerlegt (Beleg in der Tabelle), Regressionstest | `f00e892` |
| F-09 Heizungsart | behoben | `db474b9` |
| F-10 Recorder-Last | behoben | `21c24f9` |
| F-11 SDK-Version, eigener Client | behoben: eigener Client wird geschlossen. Statt Pinnen gilt die Mindestversion `anthropic>=0.125.0`, weil hassfest das Pinnen einer Abhängigkeit von Home Assistant selbst ablehnt; lehnt ein neueres SDK den geteilten Client ab, greift der eigene Client | `74fa3fd`, `dfed005` |
| F-12 Prognose-Timeout | behoben | `74fa3fd`, `2fd4f72` (Test) |
| F-13 Doku | behoben | laufend, Abschluss in Schritt 15 |
| F-14 Selektoren | behoben | `09a81dc`, `b2d928d` |
| F-15 verwaiste Entitäten | behoben | `21c24f9`, `9158fe8` (konfigurationsbasiert) |
| F-16 bis F-20 | behoben | `8f01541`, `0b83c26` |
| F-21 Admin-Dienste | behoben | `2ffc385`, `54bc982` (auch `decide_heating_day`) |
| F-22 Fehlerbehandlung Import | behoben | `2ffc385`, `54bc982` (Daten vorab geprüft) |
| F-23 Backoff Heiztag | behoben | `74fa3fd` |
| F-24 bis F-26 Kosten | behoben | `2fd4f72`, `8f01541` (Timeout, Rundung) |
| F-27 Panel beim Deaktivieren | behoben | `2ffc385` |
| F-28 doppelter Shutdown | behoben | `f00e892` |
| F-29 Backoff Aktor | behoben | `b8a6770` |
| F-30 Tasks am Eintrag | behoben | `2ffc385` |
| F-31 Abbruchgründe | widerlegt: HA übersetzt `single_instance_allowed`, `reconfigure_successful` und `reauth_successful` selbst | – |
| F-32 Logbuch | behoben | `c5102f5` |
| F-33 loggers, iot_class | behoben; `iot_class` bleibt `calculated`, weil die Regelung lokal arbeitet und die KI optional ist | `54bc982` |
| F-34 CI | teilweise: Format- und Label-Prüfung ergänzt. Pinnen der Actions per Commit-SHA **offen** (die SHAs ließen sich aus dieser Sitzung nicht verifizieren) | `54bc982` |
| F-35 Codequalität | behoben (öffentliche Schema-Helfer, Optionen einmal je Lauf, Typen, ungenutzte Übersetzung); mypy nicht eingeführt | `54bc982` |
| F-36 eindeutige Namen | behoben | `8f01541` |
| F-37 Heute heizen außerhalb der Saison | behoben | `8f01541`, `0b83c26` |
| F-38 Panel-Last | behoben | `54bc982` |
| F-39 relative PV-Schwellen | behoben | `c60ee33` |
| F-40 (neu) `probatio` statt `voluptuous`-Alias | behoben | `54bc982` |
| Neue Optionen aus Abschnitt 3 | umgesetzt: Heizungsart, Hemisphäre, Außentemperatur aus Wetter, Prognosevertrauen, Zwangsheizen | `db474b9`, `74ac782`, `6fb1bed`, `a99e1a8`, `281ed43`, `f4a336d` |
| UI-1 bis UI-7, UI-9, UI-10, UI-12 | umgesetzt | `09a81dc`, `e21b84d`, `5a792a6`, `d6e31c0`, `73b8b2b`, `12e5bec`, `c5102f5`, `d7db976` |
| UI-8 | entfällt (F-31 widerlegt) | – |
| UI-11 Panel | `ha-selector` für Entitätsfelder umgesetzt (im Browser mit nachgebildetem Element geprüft, **in einem laufenden HA-Frontend noch zu prüfen**). HA-Dialog statt `confirm()` **offen**. | `694b204`, `54bc982` |
| UI-13 Repairs | für Sensor, Aktor, Außentemperatur und abgelehnten API-Key (Reauth) umgesetzt; eine unbekannte Einheit erzeugt nur eine Warnung im Protokoll, kein Repair (**offen**) | `b8a6770`, `9df0cfc` |

