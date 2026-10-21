// AI Heating Assistant sidebar panel: overview and all settings on one page.
// Plain web component without build step; uses only the hass object and the
// WebSocket commands of the integration. Field names, help texts and states
// come from the translation files (labels.js), types and ranges from the
// selectors of the options dialog (sent by the integration).

// labels.js with the version of this file, so a browser never keeps old texts
const { LABELS } = await import(`./labels.js${new URL(import.meta.url).search}`);

const DOMAIN = "ai_heating_assistant";

const UI = {
  de: {
    title: "AI Heating Assistant",
    tabs: {
      overview: "Übersicht",
      areas: "Heizbereiche",
      learned: "Lernwerte",
      general: "Allgemein",
      rules: "Notfall & Lüftung",
      ai: "KI",
      decision: "Heiztag-Entscheidung",
    },
    cards: {
      sensors: ["Sensoren", "Außentemperatur, Wetter und PV für alle Bereiche."],
      season: ["Heizperiode und Frostschutz", "Außerhalb der Heizperiode bleiben alle Kreise aus (nur Frostschutz)."],
      vacation: ["Urlaub", "Urlaubserkennung und Vorheizen zur Rückkehr."],
      emergency: ["Notfallregel", "Komfort-Sicherheitsnetz an Tagen ohne Heizbetrieb."],
      ventilation: ["Lüftung", "Globale Schwellen der Lüftungsempfehlung. Die Feuchte-Schwelle wird je Bereich eingestellt."],
      apikey: ["API-Key", "Ohne API-Key läuft nur die lokale Regelung."],
      model: ["Modell", "Bei einem Modellwechsel werden die Preise auf die Vorschläge des neuen Modells gesetzt, solange sie noch den Vorschlägen des alten Modells entsprechen."],
      schedule: ["Zeiten", "Nachtlauf und periodische Prüfung an Heiztagen."],
      costs: ["Budget und Preise", "Preise je Million Tokens."],
      limits: ["KI-Grenzen", "Minimum, Maximum und größte Änderung je Prüfung für jeden Parameter, den die KI anpassen darf."],
      prompts: ["KI-Anweisungen", "Bausteine der Anweisungen an die KI. Standard-Bausteine lassen sich abschalten oder umformulieren, eigene Bausteine ergänzen sie (in jeder Sprache). Aufgabe und Antwortformat bleiben fest."],
      dayrule: ["Heiztag-Regel", "Gelernte Schwelle theta. Der Startwert wird nur beim Einrichten gesetzt; eine Änderung hier ersetzt den gelernten Wert."],
      evaluation: ["Bewertung", "Wann ein Bereich als zu kalt gilt."],
      learning: ["Lernschritte", "Wie stark theta und puffer nach einem Fehler angepasst werden."],
      phases: ["Phasenwechsel", "Wann die Entscheidung von der KI zur Regel wechselt und zurück."],
      areas: ["Heizbereiche", "Ein Bereich hat einen Heizkreis (oder keinen, nur für die Lüftungsempfehlung)."],
    },
    save: "Speichern",
    saved: "Gespeichert",
    cancel: "Abbrechen",
    delete: "Löschen",
    add: "Hinzufügen",
    addValue: "Hinzufügen …",
    confirmDelete: "Heizbereich wirklich löschen? Die gelernten Werte dieses Bereichs gehen verloren.",
    notFound: "nicht gefunden",
    none: "–",
    newArea: "Neuer Heizbereich",
    on: "an",
    off: "aus",
    heatingDay: "Heute ist Heiztag",
    noHeatingDay: "Heute kein Heiztag",
    unavailable: "Nicht verfügbar",
    phase: "Phase",
    confidence: "Konfidenz",
    outOfSeason: "Außerhalb der Heizperiode",
    vacationActive: "Urlaub",
    override: "Heiztag manuell",
    areasCard: "Bereiche",
    noCircuit: "nur Lüftung",
    ai: "KI",
    aiEnabled: "KI aktiv",
    lastCheck: "Letzte Prüfung",
    nextCheck: "Nächste Prüfung",
    nextNightly: "Nächster Nachtlauf",
    learnedNames: {
      heat_rate: "Aufheizrate",
      cool_rate: "Abkühlrate",
      dead_time: "Totzeit",
      overshoot: "Überschwingen",
      recovery_time: "Erholung nach Lüften",
      outdoor_influence: "Einfluss Außentemp.",
      sun_influence: "Einfluss Sonne",
    },
    learningProgress: "Lernstand",
    aiParams: "Regelparameter (von der KI anpassbar)",
    ventLearned: "Lüftung",
    ventParams: "Lüftungsparameter (von der KI anpassbar)",
    ventNames: {
      typical_humidity: "Übliche Feuchte",
      lowest_humidity_14d: "Tiefste Feuchte (14 Tage)",
      humidity_after_airing: "Erreichbar durch Lüften",
      humidity_threshold: "Feuchte-Schwelle",
    },
    lastVentCheck: "Letzte Lüftungsprüfung",
    nextVentCheck: "Nächste Lüftungsprüfung",
    limitGroups: { heating: "Heizen", ventilation: "Lüften" },
    dayRule: "Heiztag-Regel",
    theta: "Schwelle theta",
    evaluatedDays: "Bewertete Tage",
    noLearning: "Ohne Heizkreis werden keine Heizwerte gelernt:",
    noLearnedAreas: "Noch kein Bereich mit Heizkreis.",
    notRunning: "Die Integration läuft gerade nicht, gelernte Werte sind nicht verfügbar.",
    editLearned: "Gelernte Werte bearbeiten",
    lastDecision: "Letzte Heiztag-Entscheidung",
    sources: {
      ai: "KI",
      rule: "Regel",
      rule_fallback: "Regel (ohne KI)",
      agreement: "Regel und KI einig",
      vacation_rule: "Regel (Urlaub)",
      season: "außerhalb der Heizperiode",
    },
    costMonth: "Kosten im Monat",
    heat: "Wärme",
    heatToday: "Heute",
    heatYesterday: "Gestern",
    heatMonth: "Diesen Monat",
    heatReading: "Letzter Zählerwert",
    noApiKey: "Kein API-Key: nur lokale Regelung",
    budgetReached: "Monatsbudget erreicht, keine KI-Abfragen bis zum Monatswechsel",
    lastError: "Letzter KI-Fehler",
    warnings: "Hinweise",
    noWarnings: "Keine Hinweise",
    missing: "Eingestellte Entitäten fehlen",
    glance: "Auf einen Blick",
    glanceRows: {
      areas: "Heizbereiche",
      outdoor: "Außentemperatur",
      season: "Heizperiode",
      vacation: "Urlaubs-Entitäten",
      emergency: "Notfallregel",
      model: "KI-Modell",
    },
    columns: { name: "Name", circuit: "Heizkreis", temp: "Temperatur", tempShort: "Temp.", status: "Status" },
    noItems: "Noch nichts angelegt.",
    keySet: "API-Key ist gesetzt",
    keyNotSet: "Kein API-Key",
    newKey: "Neuer API-Key",
    newKeyHelp: "Wird vor dem Speichern bei Anthropic geprüft. Der gespeicherte Key wird nie angezeigt.",
    removeKey: "API-Key entfernen",
    checking: "Wird geprüft …",
    errors: {
      required: "Pflichtfeld",
      invalid_value: "Ungültiger Wert",
      unknown_option: "Unbekannte Einstellung",
      api_key_required: "Bitte einen API-Key eingeben.",
      too_many_blocks: "Höchstens 10 eigene Bausteine je Aufruf.",
      text_too_long: "Ein Baustein darf höchstens 2000 Zeichen lang sein.",
    },
    prompts: {
      kinds: { nightly: "Nachtentscheidung (Heiztag ja/nein)", check: "Parameterprüfung", ventilation: "Lüftungsprüfung" },
      blocks: {
        nightly: {
          rules: "Regeln an Heiztagen und Tagen ohne Heizbetrieb",
          types: "Heizungsarten",
          goal: "Ziel und gespeicherte Wärme",
          data: "Erklärung der Daten",
          learn: "Aus Fehlern lernen",
        },
        check: {
          types: "Heizungsarten",
          controller: "Arbeitsweise der Regelung",
          stats: "Erklärung der Statistik",
          comfort: "Komfort vor Einsparung",
          levers: "Stellhebel",
          history: "Verlauf beurteilen",
          changes: "Umfang der Änderungen",
        },
        ventilation: {
          rules: "Arbeitsweise der Empfehlung",
          profile: "Erklärung des Feuchteprofils",
          ranges: "Bereiche je Raum wählen",
          stats: "Erklärung der Statistik",
          goal: "Schimmelschutz vor allem anderen",
          levers: "Stellhebel",
          history: "Verlauf beurteilen",
          changes: "Umfang der Änderungen",
        },
      },
      standard: "Standard-Bausteine",
      custom: "Eigene Bausteine",
      changed: "geändert",
      reset: "Standard wiederherstellen",
      addBlock: "Baustein hinzufügen",
      removeBlock: "Entfernen",
      placeholder: "z. B. Im Wohnbereich ist abends meist ein Kaminofen an.",
      preview: "Vorschau der Anweisung",
      previewNote: "Dazu kommen die Antwortsprache und, bei der Parameterprüfung, die Liste der Parameter.",
    },
    loadError: "Konfiguration konnte nicht geladen werden",
  },
  en: {
    title: "AI Heating Assistant",
    tabs: {
      overview: "Overview",
      areas: "Heating areas",
      learned: "Learned values",
      general: "General",
      rules: "Emergency & ventilation",
      ai: "AI",
      decision: "Heating day decision",
    },
    cards: {
      sensors: ["Sensors", "Outdoor temperature, weather and PV for all areas."],
      season: ["Heating period and frost protection", "Outside the heating period all circuits stay off (frost protection only)."],
      vacation: ["Vacation", "Vacation detection and preheating for the return."],
      emergency: ["Emergency rule", "Comfort safety net on days without heating."],
      ventilation: ["Ventilation", "Global thresholds of the ventilation recommendation. The humidity threshold is set per area."],
      apikey: ["API key", "Without an API key only the local control runs."],
      model: ["Model", "When the model changes, the prices are set to the suggestions of the new model as long as they still match the suggestions of the old model."],
      schedule: ["Times", "Nightly run and periodic check on heating days."],
      costs: ["Budget and prices", "Prices per million tokens."],
      limits: ["AI limits", "Minimum, maximum and largest change per check for every parameter the AI may adjust."],
      prompts: ["AI instructions", "Building blocks of the instructions to the AI. Standard blocks can be switched off or reworded, own blocks add to them (in any language). Task and answer format stay fixed."],
      dayrule: ["Heating day rule", "Learned threshold theta. Its start value is only set during setup; a change here replaces the learned value."],
      evaluation: ["Evaluation", "When an area counts as too cold."],
      learning: ["Learning steps", "How much theta and puffer change after an error."],
      phases: ["Phase changes", "When the decision moves from the AI to the rule and back."],
      areas: ["Heating areas", "An area has a heating circuit (or none, only for the ventilation recommendation)."],
    },
    save: "Save",
    saved: "Saved",
    cancel: "Cancel",
    delete: "Delete",
    add: "Add",
    addValue: "Add …",
    confirmDelete: "Really delete this heating area? Its learned values are lost.",
    notFound: "not found",
    none: "–",
    newArea: "New heating area",
    on: "on",
    off: "off",
    heatingDay: "Today is a heating day",
    noHeatingDay: "No heating day today",
    unavailable: "Unavailable",
    phase: "Phase",
    confidence: "Confidence",
    outOfSeason: "Outside the heating period",
    vacationActive: "Vacation",
    override: "Manual heating day",
    areasCard: "Areas",
    noCircuit: "ventilation only",
    ai: "AI",
    aiEnabled: "AI active",
    lastCheck: "Last check",
    nextCheck: "Next check",
    nextNightly: "Next nightly run",
    learnedNames: {
      heat_rate: "Heat-up rate",
      cool_rate: "Cooling rate",
      dead_time: "Dead time",
      overshoot: "Overshoot",
      recovery_time: "Recovery after airing",
      outdoor_influence: "Outdoor influence",
      sun_influence: "Sun influence",
    },
    learningProgress: "Learning progress",
    aiParams: "Control parameters (adjustable by the AI)",
    ventLearned: "Ventilation",
    ventParams: "Ventilation parameters (adjustable by the AI)",
    ventNames: {
      typical_humidity: "Usual humidity",
      lowest_humidity_14d: "Lowest humidity (14 days)",
      humidity_after_airing: "Reachable by airing",
      humidity_threshold: "Humidity threshold",
    },
    lastVentCheck: "Last ventilation check",
    nextVentCheck: "Next ventilation check",
    limitGroups: { heating: "Heating", ventilation: "Ventilation" },
    dayRule: "Heating day rule",
    theta: "Threshold theta",
    evaluatedDays: "Evaluated days",
    noLearning: "No heating values are learned without a heating circuit:",
    noLearnedAreas: "No area with a heating circuit yet.",
    notRunning: "The integration is not running, learned values are not available.",
    editLearned: "Edit learned values",
    lastDecision: "Last heating day decision",
    sources: {
      ai: "AI",
      rule: "rule",
      rule_fallback: "rule (without AI)",
      agreement: "rule and AI agree",
      vacation_rule: "rule (vacation)",
      season: "outside the heating period",
    },
    costMonth: "Costs this month",
    heat: "Heat",
    heatToday: "Today",
    heatYesterday: "Yesterday",
    heatMonth: "This month",
    heatReading: "Last meter reading",
    noApiKey: "No API key: local control only",
    budgetReached: "Monthly budget reached, no AI requests until the next month",
    lastError: "Last AI error",
    warnings: "Notes",
    noWarnings: "No notes",
    missing: "Configured entities are missing",
    glance: "At a glance",
    glanceRows: {
      areas: "Heating areas",
      outdoor: "Outdoor temperature",
      season: "Heating period",
      vacation: "Vacation entities",
      emergency: "Emergency rule",
      model: "AI model",
    },
    columns: { name: "Name", circuit: "Heating circuit", temp: "Temperature", tempShort: "Temp.", status: "Status" },
    noItems: "Nothing added yet.",
    keySet: "API key is set",
    keyNotSet: "No API key",
    newKey: "New API key",
    newKeyHelp: "Checked with Anthropic before saving. The stored key is never shown.",
    removeKey: "Remove API key",
    checking: "Checking …",
    errors: {
      required: "Required",
      invalid_value: "Invalid value",
      unknown_option: "Unknown setting",
      api_key_required: "Please enter an API key.",
      too_many_blocks: "At most 10 own blocks per call.",
      text_too_long: "A block may have at most 2000 characters.",
    },
    prompts: {
      kinds: { nightly: "Nightly decision (heating day yes/no)", check: "Parameter check", ventilation: "Ventilation check" },
      blocks: {
        nightly: {
          rules: "Rules on heating and no-heating days",
          types: "Heating types",
          goal: "Goal and stored heat",
          data: "Explanation of the data",
          learn: "Learn from errors",
        },
        check: {
          types: "Heating types",
          controller: "How the controller works",
          stats: "Explanation of the statistics",
          comfort: "Comfort before savings",
          levers: "Levers",
          history: "Judging the history",
          changes: "Extent of changes",
        },
        ventilation: {
          rules: "How the recommendation works",
          profile: "Explanation of the humidity profile",
          ranges: "Choosing the range per room",
          stats: "Explanation of the statistics",
          goal: "Mould protection first",
          levers: "Levers",
          history: "Judging the history",
          changes: "Extent of changes",
        },
      },
      standard: "Standard blocks",
      custom: "Own blocks",
      changed: "changed",
      reset: "Restore standard",
      addBlock: "Add block",
      removeBlock: "Remove",
      placeholder: "e.g. A wood stove usually burns in the living area in the evening.",
      preview: "Preview of the instruction",
      previewNote: "The answer language and, for the parameter check, the list of parameters are added.",
    },
    loadError: "Could not load the configuration",
  },
};

const TABS = [
  ["overview", "mdi:view-dashboard-outline"],
  ["areas", "mdi:home-thermometer-outline"],
  ["learned", "mdi:school-outline"],
  ["general", "mdi:cog-outline"],
  ["rules", "mdi:weather-windy"],
  ["ai", "mdi:robot-outline"],
  ["decision", "mdi:calendar-check-outline"],
];

// Settings cards per tab (types and ranges come from the option specs)
const SETTINGS = {
  general: [
    { id: "sensors", icon: "mdi:thermometer", fields: ["outdoor_temperature", "outdoor_humidity", "weather", "pv_power", "pv_forecast", "forecast_trust", "heat_meter"] },
    { id: "season", icon: "mdi:calendar-range", fields: ["season_start", "season_end", "frost_temperature"] },
    { id: "vacation", icon: "mdi:bag-suitcase-outline", fields: ["vacation_entities", "vacation_temperature", "return_entity", "preheat_reserve"] },
  ],
  rules: [
    { id: "emergency", icon: "mdi:alert-outline", fields: ["emergency_enabled", "emergency_delta", "emergency_duration", "emergency_window_quiet", "force_on_below"] },
    {
      id: "ventilation",
      icon: "mdi:weather-windy",
      fields: [
        "ventilation_min_ah_advantage",
        "ventilation_max_reference_excess",
        "ventilation_energy_rh_per_k",
        "ventilation_mould_rh",
        "ventilation_airing_target_below",
        "ventilation_airing_time_factor",
        "ventilation_airing_min_minutes",
        "ventilation_airing_max_minutes",
        "ventilation_airing_pause",
        "ventilation_min_cooling_advantage",
        "ventilation_cooling_margin",
        "ventilation_cooling_min_temp",
        "night_start_hour",
        "night_end_hour",
        "ventilation_ai_enabled",
        "ventilation_check_interval",
        "ventilation_check_max_interval",
      ],
    },
  ],
  ai: [
    { id: "apikey", icon: "mdi:key-outline", special: "apikey" },
    { id: "model", icon: "mdi:robot-outline", fields: ["model", "effort", "max_output_tokens"] },
    { id: "schedule", icon: "mdi:clock-outline", fields: ["nightly_time", "check_interval", "check_max_interval"] },
    { id: "costs", icon: "mdi:currency-usd", fields: ["monthly_budget", "price_input", "price_output", "price_cache_write", "price_cache_read"] },
    { id: "limits", icon: "mdi:arrow-expand-horizontal", special: "limits" },
    { id: "prompts", icon: "mdi:text-box-edit-outline", special: "prompts" },
  ],
  decision: [
    { id: "dayrule", icon: "mdi:thermometer-lines", special: "theta" },
    { id: "evaluation", icon: "mdi:thermometer-check", fields: ["too_cold_margin", "too_cold_minutes"] },
    { id: "learning", icon: "mdi:school-outline", fields: ["theta_step_up", "theta_step_down", "puffer_step_up", "puffer_step_down"] },
    {
      id: "phases",
      icon: "mdi:swap-horizontal",
      fields: [
        "phase_shared_min_days",
        "phase_shared_min_agreement",
        "phase_rule_min_days",
        "phase_rule_min_agreement",
        "phase_max_rule_errors",
        "phase_fallback_errors_7d",
        "phase_ai_check_every_days",
      ],
    },
  ],
};

// Groups of the heating area editor as in the dialog: [section, fields, collapsed].
// The start values only when an area is created; an existing one shows its learned values.
const AREA_GROUPS = [
  ["sensors", ["temperature_sensor", "humidity_sensor", "window_sensors_small", "window_sensors", "window_sensors_large", "door_sensors"], false],
  ["heating", ["heater_switch", "default_target", "min_target", "max_target", "min_on_time", "min_off_time", "heating_type"], false],
  ["start_values", ["window_delay", "recovery_time", "dead_time", "puffer"], true],
  ["learned_values", ["window_delay", "recovery_time", "dead_time", "puffer"], false],
  ["ventilation", ["ventilation_rh_threshold", "reference_temperature", "reference_humidity", "ventilation_block_entity"], true],
  ["draft", ["draft_group_1", "draft_group_2", "draft_group_3", "draft_group_4"], true],
];

// Learned values per area: [entity key, icon, digits if the frontend cannot format]
const LEARNED = [
  ["heat_rate", "mdi:thermometer-chevron-up", 2],
  ["cool_rate", "mdi:thermometer-chevron-down", 3],
  ["dead_time", "mdi:timer-sand", 0],
  ["overshoot", "mdi:chart-bell-curve", 2],
  ["recovery_time", "mdi:timer-refresh-outline", 0],
  ["outdoor_influence", "mdi:home-thermometer-outline", 4],
  ["sun_influence", "mdi:white-balance-sunny", 3],
];

const STATUS_PILL = {
  heating: "warn",
  preheat: "warn",
  emergency: "warn",
  window_open: "muted",
  recovery: "muted",
  sensor_error: "bad",
  actuator_unavailable: "bad",
  idle: "ok",
};
const VENT_PILL = { ventilate_now: "warn", close_window: "warn", ventilation_useful: "ok" };

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const clone = (value) => JSON.parse(JSON.stringify(value ?? null));
const domainsOf = (spec) => {
  const d = spec?.domain;
  return !d ? [] : Array.isArray(d) ? d : [d];
};

class AiHeatingAssistantPanel extends HTMLElement {
  constructor() {
    super();
    this._tab = "overview";
    this._drafts = {};
    this._edit = null;
    this._cfg = null;
    this._error = null;
    this._sig = "";
    this._count = null;
    this.attachShadow({ mode: "open" });
    this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
    this.shadowRoot.addEventListener("input", (ev) => this._onInput(ev));
    this.shadowRoot.addEventListener("change", (ev) => this._onInput(ev, true));
    this.shadowRoot.addEventListener("keydown", (ev) => this._onKey(ev));
    this.shadowRoot.addEventListener("value-changed", (ev) => this._onSelector(ev));
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._entitiesRef = hass.entities;
      this._count = this._entityCount();
      this._load();
      return;
    }
    // new or removed entities (e.g. after adding an area): load the entity ids again.
    // The registry object only changes with the registry, so most updates skip the count.
    if (hass.entities !== this._entitiesRef) {
      this._entitiesRef = hass.entities;
      const count = this._entityCount();
      if (count !== this._count) {
        this._count = count;
        if (this._cfg) this._load(true);
      }
    }
    for (const el of this.shadowRoot.querySelectorAll("ha-selector[data-k]")) el.hass = hass;
    this._live();
  }

  get hass() {
    return this._hass;
  }

  set narrow(value) {
    this._narrow = value;
    const btn = this.shadowRoot.querySelector(".menu");
    if (btn) btn.style.display = value ? "" : "none";
  }

  set panel(value) {
    this._panel = value;
  }

  // ------------------------------------------------------------------ texts

  get lang() {
    const language = this._hass?.locale?.language || this._hass?.language || "en";
    return language.startsWith("de") ? "de" : "en";
  }

  get ui() {
    return UI[this.lang];
  }

  get labels() {
    return LABELS[this.lang] || LABELS.en;
  }

  label(key) {
    return this.labels.fields[key] || [key, ""];
  }

  _stateLabel(kind, value) {
    return this.labels.states[kind]?.[value] || value;
  }

  _errorText(message, area = false) {
    const [code, field] = String(message || "").split(":");
    const texts = { ...this.labels.errors, ...(area ? this.labels.area_errors : {}), ...this.ui.errors };
    const text = texts[code] || message;
    if (!field) return text;
    const name = this.labels.limits[field] || this.ui.cards[field]?.[0] || this.label(field)[0];
    return `${name}: ${text}`;
  }

  // ------------------------------------------------------------------ data

  async _load(quiet = false) {
    try {
      this._cfg = await this._hass.callWS({ type: `${DOMAIN}/config` });
      this._statsAt = 0; // configuration changed: learned values again
      this._error = null;
    } catch (err) {
      this._error = err.message || String(err);
    }
    // keep the editor and its inputs while the entity ids are refreshed
    if (quiet && this._edit) return;
    if (quiet && this.shadowRoot.querySelector(".content")) {
      this._rerenderContent();
      this._sig = this._signature();
      return;
    }
    this._render();
  }

  _entityCount() {
    return Object.values(this._hass?.entities || {}).filter((e) => e.platform === DOMAIN).length;
  }

  _ws(msg) {
    return this._hass.callWS(msg);
  }

  _state(entityId) {
    return entityId ? this._hass.states[entityId] : undefined;
  }

  _name(entityId) {
    const st = this._state(entityId);
    return st?.attributes?.friendly_name || entityId;
  }

  _ok(st) {
    return st && !["unavailable", "unknown"].includes(st.state);
  }

  _time(value) {
    const date = value ? new Date(value) : null;
    if (!date || Number.isNaN(date.getTime())) return this.ui.none;
    return date.toLocaleString(this._hass.locale?.language || this._hass.language, { dateStyle: "short", timeStyle: "short" });
  }

  _num(value, digits = 1) {
    const n = Number(value);
    if (value === null || value === undefined || value === "" || Number.isNaN(n)) return this.ui.none;
    return n.toLocaleString(this._hass.locale?.language || this._hass.language, { maximumFractionDigits: digits });
  }

  // ------------------------------------------------------------------ rendering

  _render() {
    const ui = this.ui;
    const root = this.shadowRoot;
    root.innerHTML = `
      <style>${STYLE}</style>
      <div class="toolbar">
        <button class="menu icon-btn" data-action="menu" style="${this._narrow ? "" : "display:none"}"><ha-icon icon="mdi:menu"></ha-icon></button>
        <div class="title"><ha-icon icon="mdi:home-thermometer-outline"></ha-icon>${esc(ui.title)}</div>
      </div>
      <div class="tabs">
        ${TABS.map(
          ([id, icon]) =>
            `<button class="tab ${this._tab === id ? "active" : ""}" data-tab="${id}"><ha-icon icon="${icon}"></ha-icon><span>${esc(ui.tabs[id])}</span></button>`,
        ).join("")}
      </div>
      <div class="content">${this._content()}</div>
      <div class="datalists">${this._datalists()}</div>
      <div class="toast" hidden></div>`;
    this._upgradeSelectors();
    this._sig = this._signature();
  }

  _content() {
    if (this._error) return `<div class="card error">${esc(this.ui.loadError)}: ${esc(this._error)}</div>`;
    if (!this._cfg) return `<div class="card">…</div>`;
    if (this._edit) return this._editor();
    if (this._tab === "overview") return this._overview();
    if (this._tab === "areas") return this._areasTab();
    if (this._tab === "learned") return this._learnedTab();
    return (SETTINGS[this._tab] || []).map((card) => this._settingsCard(card)).join("");
  }

  _datalists() {
    if (!this._hass) return "";
    let html = "";
    // entity suggestions only for the plain text fields; ha-selector brings its own picker
    if (!customElements.get("ha-selector")) {
      const option = (id) => `<option value="${esc(id)}">${esc(this._name(id))}</option>`;
      const all = Object.keys(this._hass.states).sort();
      html += `<datalist id="dl-all">${all.map(option).join("")}</datalist>`;
      const sets = new Set();
      for (const spec of [...Object.values(this._cfg?.option_specs || {}), ...Object.values(this._cfg?.area_specs || {})]) {
        const domains = domainsOf(spec);
        if (spec.selector === "entity" && domains.length) sets.add(domains.join(","));
      }
      for (const set of sets) {
        const domains = set.split(",");
        const ids = all.filter((id) => domains.includes(id.split(".")[0]));
        html += `<datalist id="dl-${esc(set.replace(/,/g, "-"))}">${ids.map(option).join("")}</datalist>`;
      }
    }
    // choices of free text selects (e.g. the AI model) are always needed
    for (const [key, spec] of Object.entries(this._cfg?.option_specs || {})) {
      if (spec.selector === "select" && spec.custom_value) {
        html += `<datalist id="dl-opt-${esc(key)}">${(spec.options || []).map((o) => `<option value="${esc(typeof o === "object" ? o.value : o)}"></option>`).join("")}</datalist>`;
      }
    }
    return html;
  }

  _listId(spec) {
    const domains = domainsOf(spec);
    return domains.length ? `dl-${domains.join("-")}` : "dl-all";
  }

  // ------------------------------------------------------------------ live updates

  _signature() {
    if (!this._hass || !this._cfg) return "";
    const ids = [
      ...Object.values(this._cfg.entities || {}),
      ...this._cfg.areas.flatMap((a) => [...Object.values(a.entities || {}), a.data.temperature_sensor]),
      this._cfg.options.outdoor_temperature || this._cfg.options.weather,
    ];
    return ids
      .map((id) => {
        const st = this._state(id);
        if (!st) return `${id}=-`;
        const a = st.attributes;
        return `${id}=${st.state}|${a.current_temperature ?? ""}|${a.temperature ?? ""}|${a.hvac_action ?? ""}|${a.reason ?? ""}|${a.decided_at ?? ""}|${a.next_decision ?? ""}|${a.last_error ?? ""}|${a.summary ?? ""}`;
      })
      .join(";");
  }

  _live() {
    const sig = this._signature();
    if (sig === this._sig) return;
    this._sig = sig;
    if (this._edit) return;
    if (["overview", "areas", "learned"].includes(this._tab)) this._rerenderContent();
  }

  // ------------------------------------------------------------------ overview

  _areaTemps(area) {
    const climate = this._state(area.entities.climate);
    const sensor = this._state(area.data.temperature_sensor);
    const current = climate ? climate.attributes.current_temperature : this._ok(sensor) ? sensor.state : null;
    const target = climate ? climate.attributes.temperature : null;
    // the thermostat shows the unit system of HA, a plain sensor its own unit
    const unit = climate
      ? this._hass.config?.unit_system?.temperature || "°C"
      : sensor?.attributes?.unit_of_measurement || this._hass.config?.unit_system?.temperature || "°C";
    return [current, target, climate, unit];
  }

  _tempHtml(current, target, unit) {
    // each value stays on one line; a narrow column breaks before the arrow
    const now = `<span class="temp">${esc(`${this._num(current)} ${unit}`)}</span>`;
    if (target === null || target === undefined) return now;
    return `${now} <span class="temp">${esc(`→ ${this._num(target)} ${unit}`)}</span>`;
  }

  _areaStatus(area) {
    const st = this._state(area.entities.status);
    if (!this._ok(st)) return ["", ""];
    return [this._stateLabel("status", st.state), STATUS_PILL[st.state] || "muted"];
  }

  _areaVent(area) {
    const st = this._state(area.entities.ventilation);
    if (!this._ok(st) || ["optimal", "unknown"].includes(st.state)) return null;
    return [this._stateLabel("ventilation", st.state), VENT_PILL[st.state] || "muted"];
  }

  _overview() {
    const ui = this.ui;
    const ent = this._cfg.entities || {};
    const o = this._cfg.options;

    // heating day
    const day = this._state(ent.heating_day);
    const attrs = day?.attributes || {};
    const available = this._ok(day);
    const heat = day?.state === "on";
    const icon = !available ? "mdi:radiator-disabled" : heat ? "mdi:radiator" : "mdi:radiator-off";
    const color = !available ? "var(--disabled-text-color)" : heat ? "var(--warning-color, #ffa600)" : "var(--secondary-text-color)";
    const phase = this._state(ent.decision_phase);
    const lines = [];
    if (this._ok(phase)) lines.push(`${ui.phase}: ${this._stateLabel("phase", phase.state)}`);
    if (attrs.confidence !== null && attrs.confidence !== undefined) lines.push(`${ui.confidence}: ${attrs.confidence} %`);
    const hints = [];
    if (attrs.season_active === false) hints.push(ui.outOfSeason);
    if (attrs.vacation) hints.push(ui.vacationActive);
    const override = this._state(ent.heating_day_override);
    const overrideOptions = override?.attributes?.options || ["auto", "heat_today", "off_today"];
    const status = `
      <div class="card status">
        <div class="status-main">
          <ha-icon icon="${icon}" style="color:${color}"></ha-icon>
          <div>
            <div class="status-text">${esc(!available ? ui.unavailable : heat ? ui.heatingDay : ui.noHeatingDay)}</div>
            ${lines.length ? `<div class="muted">${esc(lines.join(" · "))}</div>` : ""}
            ${attrs.reason ? `<div class="muted small">${esc(attrs.reason)}</div>` : ""}
            ${hints.map((h) => `<span class="badge">${esc(h)}</span>`).join("")}
          </div>
        </div>
        ${ent.heating_day_override
          ? `<div><div class="lbl small">${esc(ui.override)}</div><div class="segments">
            ${overrideOptions
              .map((opt) => `<button class="segment ${override?.state === opt ? "on" : ""}" data-action="override" data-option="${esc(opt)}" ${this._ok(override) ? "" : "disabled"}>${esc(this._stateLabel("override", opt))}</button>`)
              .join("")}</div></div>`
          : ""}
      </div>`;

    // areas
    const areaRows = this._cfg.areas
      .map((area) => {
        const [current, target, climate, unit] = this._areaTemps(area);
        const heating = climate?.attributes?.hvac_action === "heating";
        const [statusText, statusCls] = this._areaStatus(area);
        const vent = this._areaVent(area);
        const temp = this._tempHtml(current, target, unit);
        const action = area.entities.climate ? `data-action="more-info" data-entity="${esc(area.entities.climate)}"` : `data-edit="${esc(area.id)}"`;
        return `<button class="row link" ${action}>
          <ha-icon icon="${heating ? "mdi:fire" : area.entities.climate ? "mdi:home-thermometer-outline" : "mdi:weather-windy"}" style="${heating ? "color:var(--warning-color, #ffa600)" : ""}"></ha-icon>
          <span class="grow">${esc(area.title)}</span>
          <span class="meta"><span class="muted">${temp}</span>
          ${vent ? `<span class="pill ${vent[1]}">${esc(vent[0])}</span>` : ""}
          ${statusText ? `<span class="pill ${statusCls}">${esc(statusText)}</span>` : ""}</span></button>`;
      })
      .join("");
    const areas = `
      <div class="card">
        <h2><ha-icon icon="mdi:home-thermometer-outline"></ha-icon>${esc(ui.areasCard)}</h2>
        <div class="rows">${areaRows || `<div class="muted">${esc(ui.noItems)}</div>`}</div>
        <div class="actions"><button class="btn" data-tab="areas"><ha-icon icon="mdi:pencil-outline"></ha-icon>${esc(ui.tabs.areas)}</button></div>
      </div>`;

    // AI
    const aiSwitch = this._state(ent.ai_enabled);
    const aiOn = aiSwitch?.state === "on";
    const last = this._state(ent.ai_last_check);
    const next = this._state(ent.ai_next_check);
    const lastVent = this._state(ent.ai_last_vent_check);
    const nextVent = this._state(ent.ai_next_vent_check);
    // shown whenever the ventilation check is on, so a missing value is visible too
    const ventRows = o.ventilation_ai_enabled && this._cfg.has_api_key
      ? `<div class="row"><ha-icon icon="mdi:window-open-variant"></ha-icon><span class="grow">${esc(ui.lastVentCheck)}</span><span class="muted">${esc(this._ok(lastVent) ? this._time(lastVent.state) : ui.none)}</span></div>
          ${lastVent?.attributes?.summary ? `<div class="row"><ha-icon icon="mdi:text-short"></ha-icon><span class="muted small">${esc(lastVent.attributes.summary)}</span></div>` : ""}
          <div class="row"><ha-icon icon="mdi:clock-outline"></ha-icon><span class="grow">${esc(ui.nextVentCheck)}</span><span class="muted">${esc(this._ok(nextVent) ? this._time(nextVent.state) : ui.none)}</span></div>`
      : "";
    const cost = this._state(ent.ai_cost_month);
    const budget = cost?.attributes?.budget ?? o.monthly_budget;
    const source = attrs.source ? ui.sources[attrs.source] || attrs.source : "";
    const decision = attrs.decided_at ? [this._time(attrs.decided_at), source].filter(Boolean).join(" · ") : ui.none;
    const ai = `
      <div class="card">
        <h2><ha-icon icon="mdi:robot-outline"></ha-icon>${esc(ui.ai)}</h2>
        ${this._cfg.has_api_key && ent.ai_enabled
          ? `<div class="tiles"><button class="tile ${aiOn ? "on" : ""}" data-action="toggle" data-entity="${esc(ent.ai_enabled)}" ${this._ok(aiSwitch) ? "" : "disabled"}>
              <ha-icon icon="mdi:robot-outline"></ha-icon><span>${esc(ui.aiEnabled)}</span><span class="switch ${aiOn ? "on" : ""}"></span></button></div>`
          : `<button class="row link" data-tab="ai"><ha-icon icon="mdi:key-outline"></ha-icon><span class="grow">${esc(ui.noApiKey)}</span><ha-icon icon="mdi:chevron-right"></ha-icon></button>`}
        <div class="rows">
          <div class="row"><ha-icon icon="mdi:history"></ha-icon><span class="grow">${esc(ui.lastCheck)}</span><span class="muted">${esc(this._ok(last) ? this._time(last.state) : ui.none)}</span></div>
          ${last?.attributes?.summary ? `<div class="row"><ha-icon icon="mdi:text-short"></ha-icon><span class="muted small">${esc(last.attributes.summary)}</span></div>` : ""}
          <div class="row"><ha-icon icon="mdi:clock-outline"></ha-icon><span class="grow">${esc(ui.nextCheck)}</span><span class="muted">${esc(this._ok(next) ? this._time(next.state) : ui.none)}</span></div>
          ${ventRows}
          <div class="row"><ha-icon icon="mdi:weather-night"></ha-icon><span class="grow">${esc(ui.nextNightly)}</span><span class="muted">${esc(this._time(attrs.next_decision))}</span></div>
          <div class="row"><ha-icon icon="mdi:calendar-check-outline"></ha-icon><span class="grow">${esc(ui.lastDecision)}</span><span class="muted">${esc(decision)}</span></div>
          <div class="row"><ha-icon icon="mdi:currency-usd"></ha-icon><span class="grow">${esc(ui.costMonth)}</span><span class="muted">${esc(`${this._num(this._ok(cost) ? cost.state : 0, 2)} USD / ${this._num(budget, 2)} USD`)}</span></div>
        </div>
      </div>`;

    // heat meter
    const heatState = this._state(ent.heat_today);
    const kwh = (value) => (value === null || value === undefined || value === "" || value === "unknown" || value === "unavailable" ? ui.none : `${this._num(value, 1)} kWh`);
    const ha = heatState?.attributes || {};
    const meterState = this._state(o.heat_meter);
    const meterValue = this._ok(meterState) ? `${this._num(meterState.state, 3)} ${meterState.attributes.unit_of_measurement || ""}`.trim() : ui.none;
    const meterReading = ha.meter_reading_at ? `${meterValue} · ${this._time(ha.meter_reading_at)}` : meterValue;
    const heatCard = ent.heat_today && o.heat_meter
      ? `
      <div class="card">
        <h2><ha-icon icon="mdi:heat-wave"></ha-icon>${esc(ui.heat)}</h2>
        <div class="rows">
          <div class="row"><ha-icon icon="mdi:calendar-today"></ha-icon><span class="grow">${esc(ui.heatToday)}</span><span class="muted">${esc(kwh(heatState?.state))}</span></div>
          <div class="row"><ha-icon icon="mdi:calendar-arrow-left"></ha-icon><span class="grow">${esc(ui.heatYesterday)}</span><span class="muted">${esc(kwh(ha.yesterday))}</span></div>
          <div class="row"><ha-icon icon="mdi:calendar-month-outline"></ha-icon><span class="grow">${esc(ui.heatMonth)}</span><span class="muted">${esc(kwh(ha.month))}</span></div>
          <div class="row"><ha-icon icon="mdi:counter"></ha-icon><span class="grow">${esc(ui.heatReading)}</span><span class="muted">${esc(meterReading)}</span></div>
        </div>
      </div>`
      : "";

    // notes
    const warnings = [];
    if (cost?.attributes?.budget_reached) warnings.push(ui.budgetReached);
    if (last?.attributes?.last_error) warnings.push(`${ui.lastError}: ${last.attributes.last_error}`);
    const missing = this._missingEntities();
    if (missing.length) warnings.push(`${ui.missing}: ${missing.join(", ")}`);
    const info = `
      <div class="card">
        <h2><ha-icon icon="mdi:information-outline"></ha-icon>${esc(ui.warnings)}</h2>
        ${warnings.length
          ? warnings.map((w) => `<div class="row warn-row"><ha-icon icon="mdi:alert-outline"></ha-icon><span>${esc(w)}</span></div>`).join("")
          : `<div class="muted">${esc(ui.noWarnings)}</div>`}
      </div>`;

    // at a glance
    const g = ui.glanceRows;
    // without an outdoor sensor the weather entity provides the outdoor temperature
    const outdoor = this._state(o.outdoor_temperature);
    const weather = o.outdoor_temperature ? null : this._state(o.weather);
    const outdoorText = this._ok(outdoor)
      ? `${this._num(outdoor.state)} ${outdoor.attributes.unit_of_measurement || ""}`
      : weather && typeof weather.attributes.temperature === "number"
        ? `${this._num(weather.attributes.temperature)} ${weather.attributes.temperature_unit || ""} (${this._name(o.weather)})`
        : o.outdoor_temperature || ui.none;
    const effort = this.labels.effort[o.effort] || o.effort;
    const glanceRows = [
      ["areas", "mdi:home-thermometer-outline", g.areas, this._cfg.areas.map((a) => a.title).join(", ") || ui.none],
      ["general", "mdi:thermometer", g.outdoor, outdoorText],
      ["general", "mdi:calendar-range", g.season, `${o.season_start} – ${o.season_end}`],
      ["general", "mdi:bag-suitcase-outline", g.vacation, (o.vacation_entities || []).map((id) => this._name(id)).join(", ") || ui.none],
      ["rules", "mdi:alert-outline", g.emergency, o.emergency_enabled ? ui.on : ui.off],
      ["ai", "mdi:robot-outline", g.model, `${o.model} (${effort})`],
    ];
    const glance = `
      <div class="card">
        <h2><ha-icon icon="mdi:format-list-checks"></ha-icon>${esc(ui.glance)}</h2>
        <div class="rows">
          ${glanceRows
            .map(([tab, ic, label, value]) => `<button class="row link" data-tab="${tab}"><ha-icon icon="${ic}"></ha-icon><span class="grow">${esc(label)}</span><span class="muted">${esc(value)}</span><ha-icon icon="mdi:chevron-right"></ha-icon></button>`)
            .join("")}
        </div>
      </div>`;
    return `<div class="grid">${status}${areas}${ai}${heatCard}${info}${glance}</div>`;
  }

  _missingEntities() {
    const missing = new Set();
    const check = (specs, values) => {
      for (const [key, spec] of Object.entries(specs || {})) {
        if (spec.selector !== "entity") continue;
        const value = values[key];
        for (const id of Array.isArray(value) ? value : value ? [value] : []) {
          if (!this._state(id)) missing.add(id);
        }
      }
    };
    check(this._cfg.option_specs, this._cfg.options);
    for (const area of this._cfg.areas) check(this._cfg.area_specs, area.data);
    return [...missing];
  }

  // ------------------------------------------------------------------ areas

  _areasTab() {
    const ui = this.ui;
    const [title, desc] = ui.cards.areas;
    const rows = this._cfg.areas
      .map((area) => {
        const [current, target, , unit] = this._areaTemps(area);
        const [statusText, statusCls] = this._areaStatus(area);
        const vent = this._areaVent(area);
        const circuit = area.data.heater_switch ? this._name(area.data.heater_switch) : ui.noCircuit;
        const temp = this._tempHtml(current, target, unit);
        return `<tr data-edit="${esc(area.id)}">
          <td class="c-icon"><ha-icon icon="${area.data.heater_switch ? "mdi:home-thermometer-outline" : "mdi:weather-windy"}"></ha-icon></td>
          <td class="c-name"><div>${esc(area.title)}</div><div class="muted small entity-id">${esc(area.data.temperature_sensor)}</div></td>
          <td class="hide-narrow">${esc(circuit)}</td>
          <td class="c-temp">${temp}</td>
          <td class="c-state">${statusText ? `<span class="pill ${statusCls}">${esc(statusText)}</span>` : ""}${vent ? `<span class="pill ${vent[1]}">${esc(vent[0])}</span>` : ""}</td>
          <td class="c-edit hide-narrow"><ha-icon icon="mdi:pencil-outline" class="muted"></ha-icon></td>
        </tr>`;
      })
      .join("");
    return `<div class="card">
      <h2><ha-icon icon="mdi:home-thermometer-outline"></ha-icon>${esc(title)}</h2><p class="desc">${esc(desc)}</p>
      ${this._cfg.areas.length
        ? `<div class="table-wrap"><table><thead><tr><th class="c-icon"></th><th class="c-name">${esc(ui.columns.name)}</th><th class="hide-narrow">${esc(ui.columns.circuit)}</th><th class="c-temp"><span class="hide-narrow">${esc(ui.columns.temp)}</span><span class="show-narrow">${esc(ui.columns.tempShort)}</span></th><th class="c-state">${esc(ui.columns.status)}</th><th class="c-edit hide-narrow"></th></tr></thead><tbody>${rows}</tbody></table></div>`
        : `<div class="muted">${esc(ui.noItems)}</div>`}
      <div class="actions"><button class="btn primary" data-new="area"><ha-icon icon="mdi:plus"></ha-icon>${esc(ui.add)}</button></div>
    </div>`;
  }

  _formatState(entityId, digits) {
    const st = this._state(entityId);
    if (!this._ok(st)) return this.ui.none;
    if (typeof this._hass.formatEntityState === "function") return this._hass.formatEntityState(st);
    const n = Number(st.state);
    if (Number.isNaN(n)) return st.state;
    const lang = this._hass.locale?.language || this._hass.language;
    const text = n.toLocaleString(lang, { minimumFractionDigits: digits, maximumFractionDigits: digits });
    return `${text} ${st.attributes.unit_of_measurement || ""}`.trim();
  }

  // Learned rates come from the integration: their sensors are disabled by default.
  _learnedStats() {
    const now = Date.now();
    if (!this._statsLoading && (!this._statsAt || now - this._statsAt > 60000)) {
      this._statsLoading = true;
      this._ws({ type: `${DOMAIN}/learned` })
        .then((stats) => {
          this._stats = stats;
          this._statsAt = Date.now();
        })
        .catch(() => {
          this._statsAt = Date.now(); // not running: try again later
        })
        .finally(() => {
          this._statsLoading = false;
          if (this._tab === "learned" && this._stats) this._rerenderContent();
        });
    }
    return this._stats || {};
  }

  _learnedText(entityId, stat, digits) {
    if (this._ok(this._state(entityId))) return this._formatState(entityId, digits);
    if (!stat || typeof stat.value !== "number") return this.ui.none;
    return `${this._num(stat.value, digits)} ${stat.unit || ""}`.trim();
  }

  _learnedTab() {
    const ui = this.ui;
    const heating = this._cfg.areas.filter((a) => a.entities.learning_progress);
    const others = this._cfg.areas.filter((a) => !a.entities.learning_progress);
    const phase = this._state(this._cfg.entities.decision_phase);
    const dayRule = this._ok(phase)
      ? `<div class="card learn"><div class="learn-head"><h2><ha-icon icon="mdi:calendar-check-outline"></ha-icon>${esc(ui.dayRule)}</h2>
            <button class="icon-btn muted" data-tab="decision" title="${esc(ui.editLearned)}"><ha-icon icon="mdi:pencil-outline"></ha-icon></button></div>
          <div class="learn-grid">
            <div class="learn-cell"><span class="lbl small">${esc(ui.theta)}</span><span>${esc(`${this._num(phase.attributes.theta)} °C`)}</span></div>
            <div class="learn-cell"><span class="lbl small">${esc(ui.evaluatedDays)}</span><span>${esc(this._num(phase.attributes.evaluated_days, 0))}</span></div>
          </div></div>`
      : "";
    const units = Object.fromEntries((this._cfg.limit_params || []).map((p) => [p.key, p.unit]));
    const cards = heating
      .map((area) => {
        const progress = this._state(area.entities.learning_progress);
        const stats = this._learnedStats()[area.id] || {};
        const cells = LEARNED.filter(([key]) => area.entities[key] || stats[key])
          .map(
            ([key, icon, digits]) => `<div class="learn-cell"><span class="lbl small"><ha-icon icon="${icon}"></ha-icon>${esc(ui.learnedNames[key])}</span>
              <span>${esc(this._learnedText(area.entities[key], stats[key], digits))}</span></div>`,
          )
          .join("");
        const params = Object.entries(progress?.attributes?.parameters || {})
          .map(([key, value]) => {
            const unit = units[key] ? ` ${units[key]}` : "";
            return `<div class="learn-cell"><span class="lbl small">${esc(this.labels.limits[key] || key)}</span><span>${esc(`${this._num(value, 2)}${unit}`)}</span></div>`;
          })
          .join("");
        const open = this._openDetails?.has(`params-${area.id}`);
        return `<div class="card learn">
          <div class="learn-head"><h2>${esc(area.title)}</h2><span class="grow"></span>
            <button class="icon-btn muted" data-edit="${esc(area.id)}" title="${esc(ui.editLearned)}"><ha-icon icon="mdi:pencil-outline"></ha-icon></button>
            <span class="pill ${this._ok(progress) ? "" : "muted"}" title="${esc(ui.learningProgress)}"><ha-icon icon="mdi:school-outline"></ha-icon>${esc(this._formatState(area.entities.learning_progress, 0))}</span></div>
          <div class="learn-grid">${cells}</div>
          ${params ? `<details data-keep="params-${esc(area.id)}" ${open ? "open" : ""}><summary>${esc(ui.aiParams)}</summary><div class="learn-grid">${params}</div></details>` : ""}
        </div>`;
      })
      .join("");
    const ventCards = this._cfg.areas
      .filter((a) => a.entities.ventilation && a.data.humidity_sensor)
      .map((area) => {
        const attrs = this._state(area.entities.ventilation)?.attributes || {};
        const pct = (value) => (value === null || value === undefined ? ui.none : `${this._num(value, 1)} %`);
        const cells = Object.entries(ui.ventNames)
          .map(([key, name]) => `<div class="learn-cell"><span class="lbl small">${esc(name)}</span><span>${esc(pct(attrs[key]))}</span></div>`)
          .join("");
        const params = Object.entries(attrs.parameters || {})
          .map(([key, value]) => {
            const unit = units[key] ? ` ${units[key]}` : "";
            return `<div class="learn-cell"><span class="lbl small">${esc(this.labels.limits[key] || key)}</span><span>${esc(`${this._num(value, 2)}${unit}`)}</span></div>`;
          })
          .join("");
        const open = this._openDetails?.has(`vent-${area.id}`);
        return `<div class="card learn">
          <div class="learn-head"><h2><ha-icon icon="mdi:water-percent"></ha-icon>${esc(`${ui.ventLearned}: ${area.title}`)}</h2></div>
          <div class="learn-grid">${cells}</div>
          ${params ? `<details data-keep="vent-${esc(area.id)}" ${open ? "open" : ""}><summary>${esc(ui.ventParams)}</summary><div class="learn-grid">${params}</div></details>` : ""}
        </div>`;
      })
      .join("");
    const note = others.length ? `<p class="desc">${esc(ui.noLearning)} ${esc(others.map((a) => a.title).join(", "))}</p>` : "";
    const empty = heating.length || ventCards ? "" : `<div class="card"><div class="muted">${esc(ui.noLearnedAreas)}</div></div>`;
    return `<div class="learn-cards">${dayRule}${cards}${ventCards}</div>${empty}${note}`;
  }

  _editor() {
    const ui = this.ui;
    const e = this._edit;
    const specs = this._cfg.area_specs;
    const title = e.id ? e.title || e.originalTitle : ui.newArea;
    const groups = AREA_GROUPS.map(([sec, keys, collapsed]) => {
      const learned = sec === "learned_values";
      if (sec === "start_values" && e.id) return "";
      if (learned && !Object.keys(e.learned).length) return "";
      const [name, desc] = this.labels.sections[sec] || [sec, ""];
      const fields = keys
        .filter((key) => !learned || key in e.learned)
        .map((key) =>
          learned
            ? this._field("learned", key, this._cfg.learned_specs[key], e.learned[key], this.labels.learned[key])
            : this._field("edit", key, specs[key], e.data[key]),
        )
        .join("");
      const body = `${desc ? `<p class="desc">${esc(desc)}</p>` : ""}<div class="fields">${fields}</div>`;
      if (!collapsed) return `<h3>${esc(name)}</h3>${body}`;
      return `<details data-section="${sec}" ${e.open.has(sec) ? "open" : ""}><summary>${esc(name)}</summary>${body}</details>`;
    }).join("");
    const running = !e.id || this._cfg.theta !== null;
    return `<div class="card" data-card="edit">
      <h2><button class="icon-btn" data-action="close-edit"><ha-icon icon="mdi:arrow-left"></ha-icon></button>
        <ha-icon icon="${e.data.heater_switch ? "mdi:home-thermometer-outline" : "mdi:weather-windy"}"></ha-icon>${esc(title)}</h2>
      <div class="fields">${this._field("edit", "name", specs.name, e.title)}</div>
      ${groups}
      ${running ? "" : `<p class="desc">${esc(ui.notRunning)}</p>`}
      <div class="actions"><span class="msg"></span>
        ${e.id ? `<button class="btn danger" data-action="delete-area">${esc(ui.delete)}</button>` : ""}
        <span class="grow"></span>
        <button class="btn" data-action="close-edit">${esc(ui.cancel)}</button>
        <button class="btn primary" data-action="save-area">${esc(ui.save)}</button></div>
    </div>`;
  }

  // ------------------------------------------------------------------ settings cards

  _value(cardId, key) {
    const draft = this._drafts[cardId];
    if (draft && key in draft) return draft[key];
    return this._cfg.options[key];
  }

  _head(card) {
    const [title, desc] = this.ui.cards[card.id] || [card.id, ""];
    return `<h2><ha-icon icon="${card.icon}"></ha-icon>${esc(title)}</h2>${desc ? `<p class="desc">${esc(desc)}</p>` : ""}`;
  }

  _actions(cardId) {
    const dirty = !!this._drafts[cardId];
    return `<div class="actions"><span class="msg"></span>
      ${dirty ? `<button class="btn" data-cancel="${cardId}">${esc(this.ui.cancel)}</button>` : ""}
      <button class="btn primary" data-save="${cardId}" ${dirty ? "" : "disabled"}>${esc(this.ui.save)}</button></div>`;
  }

  _settingsCard(card) {
    if (card.special === "apikey") return this._apiKeyCard(card);
    if (card.special === "limits") return this._limitsCard(card);
    if (card.special === "prompts") return this._promptsCard(card);
    if (card.special === "theta") return this._thetaCard(card);
    const specs = this._cfg.option_specs;
    const fields = card.fields.map((key) => this._field(card.id, key, specs[key], this._value(card.id, key))).join("");
    return `<div class="card" data-card="${card.id}">${this._head(card)}<div class="fields">${fields}</div>${this._actions(card.id)}</div>`;
  }

  _apiKeyCard(card) {
    const ui = this.ui;
    const draft = this._drafts.apikey || {};
    const help = this.label("api_key")[1];
    return `<div class="card" data-card="apikey">${this._head(card)}
      <div class="fields">
        <div class="field"><span class="pill ${this._cfg.has_api_key ? "ok" : "muted"}">${esc(this._cfg.has_api_key ? ui.keySet : ui.keyNotSet)}</span>${help ? `<small>${esc(help)}</small>` : ""}</div>
        <label class="field"><span class="lbl">${esc(ui.newKey)}</span>
          <input type="password" autocomplete="new-password" data-card-id="apikey" data-k="api_key" value="${esc(draft.api_key || "")}">
          <small>${esc(ui.newKeyHelp)}</small></label>
        ${this._cfg.has_api_key ? this._toggle("apikey", "remove", ui.removeKey, "", !!draft.remove) : ""}
      </div>${this._actions("apikey")}</div>`;
  }

  _thetaCard(card) {
    const ui = this.ui;
    if (this._cfg.theta === null) return `<div class="card" data-card="theta">${this._head(card)}<div class="muted">${esc(ui.notRunning)}</div></div>`;
    const draft = this._drafts.theta;
    const value = draft && "theta" in draft ? draft.theta : this._cfg.theta;
    const phase = this._state(this._cfg.entities.decision_phase);
    const days = this._ok(phase) ? phase.attributes.evaluated_days : null;
    return `<div class="card" data-card="theta">${this._head(card)}
      <div class="fields">${this._field("theta", "theta", this._cfg.learned_specs.theta, value)}
        <div class="field"><span class="lbl">${esc(ui.evaluatedDays)}</span><span>${esc(this._num(days, 0))}</span></div></div>
      ${this._actions("theta")}</div>`;
  }

  _limitsCard(card) {
    const cols = this.labels.limit_columns;
    const limits = this._drafts.limits?.limits || this._cfg.options.limits;
    let group = null;
    const rows = this._cfg.limit_params
      .map(({ key, unit, group: g }) => {
        const head = g && g !== group ? `<tr><th class="c-name" colspan="4">${esc(this.ui.limitGroups[g] || g)}</th></tr>` : "";
        group = g;
        const values = limits[key] || {};
        const input = (part) =>
          `<td><input type="number" step="0.01" data-limit="${esc(key)}" data-part="${part}" value="${esc(values[part] ?? "")}"></td>`;
        return `${head}<tr><td class="c-name">${esc(this.labels.limits[key] || key)}${unit ? ` <span class="muted small">(${esc(unit)})</span>` : ""}</td>${input("min")}${input("max")}${input("step")}</tr>`;
      })
      .join("");
    return `<div class="card" data-card="limits">${this._head(card)}
      <div class="table-wrap"><table class="limits"><thead><tr><th class="c-name"></th><th>${esc(cols.min)}</th><th>${esc(cols.max)}</th><th>${esc(cols.step)}</th></tr></thead>
      <tbody>${rows}</tbody></table></div>${this._actions("limits")}</div>`;
  }

  // Prompt configuration of one call from the draft or the saved options.
  _promptConfig(kind) {
    const all = this._drafts.prompts?.prompt_blocks || this._cfg.options.prompt_blocks || {};
    const config = all[kind] || {};
    return { disabled: config.disabled || [], overrides: config.overrides || {}, custom: config.custom || [] };
  }

  _promptDraft(kind) {
    const draft = (this._drafts.prompts = this._drafts.prompts || { prompt_blocks: clone(this._cfg.options.prompt_blocks || {}) });
    const config = (draft.prompt_blocks[kind] = { ...this._promptConfig(kind), ...(draft.prompt_blocks[kind] || {}) });
    const save = this.shadowRoot.querySelector('[data-save="prompts"]');
    if (save) save.disabled = false;
    return config;
  }

  // Same assembly as logic/prompts.py build_system.
  _promptPreview(kind) {
    const spec = this._cfg.prompt_defaults[kind];
    const config = this._promptConfig(kind);
    const parts = [spec.head];
    for (const block of spec.blocks) {
      if (!config.disabled.includes(block.id)) parts.push(String(config.overrides[block.id] || block.text).trim());
    }
    const custom = config.custom.filter((c) => c.enabled !== false).map((c) => String(c.text || "").trim()).filter(Boolean);
    const text = parts.filter(Boolean).join(" ");
    if (custom.length) return [text, spec.custom_head, ...custom.map((c) => `- ${c}`), spec.tail].join("\n");
    return `${text} ${spec.tail}`;
  }

  _promptsCard(card) {
    const ui = this.ui.prompts;
    const kinds = Object.keys(this._cfg.prompt_defaults || {});
    const opened = (key) => (this._openDetails?.has(key) ? "open" : "");
    const switchHtml = (attrs, on) =>
      `<input type="checkbox" class="switch-input" ${attrs} ${on ? "checked" : ""}><span class="switch ${on ? "on" : ""}"></span>`;
    const groups = kinds
      .map((kind) => {
        const spec = this._cfg.prompt_defaults[kind];
        const config = this._promptConfig(kind);
        const standard = spec.blocks
          .map((block) => {
            const on = !config.disabled.includes(block.id);
            const changed = block.id in config.overrides;
            const text = changed ? config.overrides[block.id] : block.text;
            const name = ui.blocks[kind]?.[block.id] || block.id;
            const keep = `prompt-${kind}-${block.id}`;
            return `<div class="prompt-block ${on ? "" : "off"}">
              <label class="field toggle-row"><span><span class="lbl">${esc(name)}${changed ? ` <span class="pill muted">${esc(ui.changed)}</span>` : ""}</span></span>
                ${switchHtml(`data-prompt="toggle" data-kind="${kind}" data-block="${esc(block.id)}"`, on)}</label>
              <details data-keep="${keep}" ${opened(keep)}><summary class="small muted">${esc(text.slice(0, 90))}${text.length > 90 ? " …" : ""}</summary>
                <textarea rows="4" data-prompt="override" data-kind="${kind}" data-block="${esc(block.id)}">${esc(text)}</textarea>
                ${changed ? `<div class="actions"><button class="btn" data-prompt-action="reset" data-kind="${kind}" data-block="${esc(block.id)}">${esc(ui.reset)}</button></div>` : ""}
              </details></div>`;
          })
          .join("");
        const custom = config.custom
          .map((item, i) => {
            const on = item.enabled !== false;
            return `<div class="prompt-block ${on ? "" : "off"}">
              <textarea rows="3" data-prompt="custom" data-kind="${kind}" data-index="${i}" placeholder="${esc(ui.placeholder)}">${esc(item.text || "")}</textarea>
              <div class="actions">
                <label class="toggle-row">${switchHtml(`data-prompt="custom-toggle" data-kind="${kind}" data-index="${i}"`, on)}</label>
                <button class="btn danger" data-prompt-action="remove" data-kind="${kind}" data-index="${i}">${esc(ui.removeBlock)}</button>
              </div></div>`;
          })
          .join("");
        const keep = `prompt-${kind}-preview`;
        return `<h3>${esc(ui.kinds[kind] || kind)}</h3>
          <div class="lbl small muted">${esc(ui.standard)}</div>${standard}
          <div class="lbl small muted">${esc(ui.custom)}</div>${custom}
          <div class="actions"><button class="btn" data-prompt-action="add" data-kind="${kind}" ${config.custom.length >= 10 ? "disabled" : ""}>
            <ha-icon icon="mdi:plus"></ha-icon>${esc(ui.addBlock)}</button></div>
          <details data-keep="${keep}" ${opened(keep)}><summary>${esc(ui.preview)}</summary>
            <pre class="prompt-preview" data-preview="${kind}">${esc(this._promptPreview(kind))}</pre>
            <small class="muted">${esc(ui.previewNote)}</small></details>`;
      })
      .join("");
    return `<div class="card" data-card="prompts">${this._head(card)}${groups}${this._actions("prompts")}</div>`;
  }

  _onPromptInput(el) {
    const { kind, block, index } = el.dataset;
    const config = this._promptDraft(kind);
    switch (el.dataset.prompt) {
      case "toggle":
        config.disabled = el.checked ? config.disabled.filter((id) => id !== block) : [...config.disabled, block];
        el.nextElementSibling?.classList.toggle("on", el.checked);
        el.closest(".prompt-block")?.classList.toggle("off", !el.checked);
        break;
      case "override": {
        const standard = this._cfg.prompt_defaults[kind].blocks.find((b) => b.id === block)?.text;
        const overrides = { ...config.overrides };
        if (el.value.trim() && el.value.trim() !== standard) overrides[block] = el.value;
        else delete overrides[block];
        config.overrides = overrides;
        break;
      }
      case "custom":
        config.custom = config.custom.map((c, i) => (i === Number(index) ? { ...c, text: el.value } : c));
        break;
      case "custom-toggle":
        config.custom = config.custom.map((c, i) => (i === Number(index) ? { ...c, enabled: el.checked } : c));
        el.nextElementSibling?.classList.toggle("on", el.checked);
        el.closest(".prompt-block")?.classList.toggle("off", !el.checked);
        break;
      default:
        break;
    }
    const preview = this.shadowRoot.querySelector(`[data-preview="${kind}"]`);
    if (preview) preview.textContent = this._promptPreview(kind);
  }

  _onPromptAction(el) {
    const { kind, block, index } = el.dataset;
    const config = this._promptDraft(kind);
    if (el.dataset.promptAction === "reset") {
      const overrides = { ...config.overrides };
      delete overrides[block];
      config.overrides = overrides;
    } else if (el.dataset.promptAction === "add") {
      config.custom = [...config.custom, { text: "", enabled: true }];
    } else if (el.dataset.promptAction === "remove") {
      config.custom = config.custom.filter((_, i) => i !== Number(index));
    }
    this._rerenderContent(el.dataset.promptAction === "add" ? `[data-prompt="custom"][data-kind="${kind}"][data-index="${config.custom.length - 1}"]` : undefined);
  }

  _toggle(cardId, key, name, help, on) {
    return `<label class="field toggle-row"><span><span class="lbl">${esc(name)}</span>${help ? `<small>${esc(help)}</small>` : ""}</span>
      <input type="checkbox" class="switch-input" data-card-id="${cardId}" data-k="${key}" data-type="bool" ${on ? "checked" : ""}><span class="switch ${on ? "on" : ""}"></span></label>`;
  }

  _field(cardId, key, spec, value, label = this.label(key)) {
    const ui = this.ui;
    const [name, help] = label;
    const kind = spec?.selector || "text";
    const helpHtml = help ? `<small>${esc(help)}</small>` : "";
    const attrs = (type) => `data-card-id="${cardId}" data-k="${key}" data-type="${type}"`;
    switch (kind) {
      case "boolean":
        return this._toggle(cardId, key, name, help, !!value);
      case "number": {
        const unit = spec.unit_of_measurement;
        return `<label class="field"><span class="lbl">${esc(name)}</span><span class="with-unit">
          <input type="number" ${attrs("number")} value="${esc(value ?? "")}" min="${spec.min ?? ""}" max="${spec.max ?? ""}" step="${spec.step ?? "any"}">
          ${unit ? `<span class="unit">${esc(unit)}</span>` : ""}</span>${helpHtml}</label>`;
      }
      case "time":
        return `<label class="field"><span class="lbl">${esc(name)}</span><input type="time" step="1" ${attrs("time")} value="${esc(value ?? "")}">${helpHtml}</label>`;
      case "select": {
        const options = (spec.options || []).map((o) => (typeof o === "object" ? o.value : o));
        const texts = spec.translation_key ? this.labels[spec.translation_key] || {} : {};
        if (spec.custom_value) {
          return `<label class="field"><span class="lbl">${esc(name)}</span><input type="text" list="dl-opt-${esc(key)}" ${attrs("text")} value="${esc(value ?? "")}" autocomplete="off">${helpHtml}</label>`;
        }
        return `<label class="field"><span class="lbl">${esc(name)}</span><select ${attrs("text")}>
          ${options.map((opt) => `<option value="${esc(opt)}" ${opt === value ? "selected" : ""}>${esc(texts[opt] || opt)}</option>`).join("")}
          </select>${helpHtml}</label>`;
      }
      case "entity": {
        // Home Assistant's own entity picker (names, areas, filters) when available
        if (customElements.get("ha-selector")) {
          this._selectors = this._selectors || new Map();
          this._selectors.set(`${cardId}|${key}`, { spec, value, name });
          return `<div class="field"><ha-selector ${attrs("selector")}></ha-selector>${helpHtml}</div>`;
        }
        if (spec.multiple) {
          const list = Array.isArray(value) ? value : [];
          const chips = list
            .map((item, i) => {
              const st = this._state(item);
              return `<span class="chip ${st ? "" : "bad"}" title="${esc(item)}">${esc(st ? this._name(item) : item)}<button class="chip-btn" data-remove="${i}" ${attrs("entities")}>✕</button></span>`;
            })
            .join("");
          return `<div class="field"><span class="lbl">${esc(name)}</span>
            <div class="chips">${chips}</div>
            <input type="text" list="${this._listId(spec)}" data-add="1" ${attrs("entities")} placeholder="${esc(ui.addValue)}" autocomplete="off">${helpHtml}</div>`;
        }
        const st = value ? this._state(value) : null;
        const hint = value ? (st ? this._name(value) : `⚠ ${ui.notFound}`) : "";
        return `<label class="field"><span class="lbl">${esc(name)}</span>
          <input type="text" list="${this._listId(spec)}" ${attrs("entity")} value="${esc(value ?? "")}" placeholder="${esc(domainsOf(spec)[0] || "entity")}.…" autocomplete="off">
          <span class="entity-hint ${value && !st ? "bad" : ""}">${esc(hint)}</span>${helpHtml}</label>`;
      }
      default:
        return `<label class="field"><span class="lbl">${esc(name)}</span><input type="text" ${attrs("text")} value="${esc(value ?? "")}">${helpHtml}</label>`;
    }
  }

  // ------------------------------------------------------------------ events

  _setValue(cardId, key, value) {
    if (cardId === "edit") {
      if (key === "name") this._edit.title = value;
      else this._edit.data[key] = value;
      return;
    }
    if (cardId === "learned") {
      this._edit.learned[key] = value;
      return;
    }
    this._drafts[cardId] = this._drafts[cardId] || {};
    this._drafts[cardId][key] = value;
    const save = this.shadowRoot.querySelector(`[data-save="${cardId}"]`);
    if (save) save.disabled = false;
  }

  _currentList(cardId, key) {
    const value = cardId === "edit" ? this._edit.data[key] : this._value(cardId, key);
    return Array.isArray(value) ? [...value] : [];
  }

  _onInput(ev, isChange = false) {
    const el = ev.target;
    // typing in the search of a picker is no value; ha-selector reports value-changed
    if (el.localName === "ha-selector") return;
    if (el.dataset.prompt) {
      // text: every keystroke; switches: only once (change), not twice
      if (el.type !== "checkbox" || isChange) this._onPromptInput(el);
      return;
    }
    if (el.dataset.limit) {
      const draft = (this._drafts.limits = this._drafts.limits || { limits: clone(this._cfg.options.limits) });
      draft.limits[el.dataset.limit] = { ...draft.limits[el.dataset.limit], [el.dataset.part]: el.value === "" ? null : Number(el.value) };
      const save = this.shadowRoot.querySelector('[data-save="limits"]');
      if (save) save.disabled = false;
      return;
    }
    if (el.dataset.add) {
      if (isChange) this._addListValue(el);
      return;
    }
    const cardId = el.dataset.cardId;
    const key = el.dataset.k;
    if (!cardId || !key) return;
    const type = el.dataset.type;
    let value;
    if (type === "bool" || el.type === "checkbox") {
      value = el.checked;
      const sw = el.nextElementSibling;
      if (sw?.classList.contains("switch")) sw.classList.toggle("on", value);
    } else if (type === "number") {
      value = el.value === "" ? null : Number(el.value);
    } else {
      value = el.value;
    }
    if (type === "entity") {
      const hint = el.parentElement.querySelector(".entity-hint");
      if (hint) {
        const st = value ? this._state(value) : null;
        hint.textContent = value ? (st ? this._name(value) : `⚠ ${this.ui.notFound}`) : "";
        hint.classList.toggle("bad", !!value && !st);
      }
    }
    this._setValue(cardId, key, value);
  }

  // Configure the ha-selector elements of the rendered content (properties, not attributes).
  _upgradeSelectors() {
    for (const el of this.shadowRoot.querySelectorAll("ha-selector[data-k]")) {
      const { cardId, k: key } = el.dataset;
      const field = this._selectors?.get(`${cardId}|${key}`);
      if (!field) continue;
      const { selector, ...config } = field.spec || {};
      el.hass = this._hass;
      el.selector = { [selector || "entity"]: config };
      el.label = field.name;
      el.value = field.value ?? (config.multiple ? [] : "");
      el.required = false;
    }
  }

  _onSelector(ev) {
    const el = ev.target;
    if (el?.localName !== "ha-selector" || !el.dataset.k) return;
    ev.stopPropagation();
    const value = ev.detail?.value;
    el.value = value;
    const field = this._selectors?.get(`${el.dataset.cardId}|${el.dataset.k}`);
    if (field) field.value = value;
    this._setValue(el.dataset.cardId, el.dataset.k, value === undefined || value === "" ? null : value);
  }

  _onKey(ev) {
    const el = ev.target;
    if (ev.key === "Enter" && el.dataset.add) {
      ev.preventDefault();
      this._addListValue(el);
    }
  }

  _addListValue(el) {
    const value = el.value.trim();
    if (!value) return;
    const { cardId, k: key } = el.dataset;
    const list = this._currentList(cardId, key);
    if (!list.includes(value)) list.push(value);
    this._setValue(cardId, key, list);
    this._rerenderContent(`[data-add][data-k="${key}"]`);
  }

  _rerenderContent(focusSelector) {
    const content = this.shadowRoot.querySelector(".content");
    if (!content) return;
    if (this._edit) {
      for (const details of content.querySelectorAll("details[data-section]")) {
        if (details.open) this._edit.open.add(details.dataset.section);
        else this._edit.open.delete(details.dataset.section);
      }
    }
    this._openDetails = this._openDetails || new Set();
    for (const details of content.querySelectorAll("details[data-keep]")) {
      if (details.open) this._openDetails.add(details.dataset.keep);
      else this._openDetails.delete(details.dataset.keep);
    }
    const scroll = content.scrollTop;
    content.innerHTML = this._content();
    this._upgradeSelectors();
    content.scrollTop = scroll;
    if (focusSelector) content.querySelector(focusSelector)?.focus();
  }

  _openEditor(area) {
    const defaults = clone(this._cfg.area_defaults);
    this._edit = area
      ? { id: area.id, title: area.title, originalTitle: area.title, data: { ...defaults, ...clone(area.data) }, learned: clone(area.learned || {}), open: new Set() }
      : { id: null, title: "", data: defaults, learned: {}, open: new Set() };
    delete this._edit.data.name;
  }

  async _onClick(ev) {
    const el = ev.target.closest("button, [data-edit], [data-tab]");
    if (!el || el.disabled) return;
    const d = el.dataset;
    if (d.tab) {
      this._tab = d.tab;
      this._edit = null;
      this._render();
      return;
    }
    if (d.remove !== undefined) {
      ev.preventDefault();
      const list = this._currentList(d.cardId, d.k);
      list.splice(Number(d.remove), 1);
      this._setValue(d.cardId, d.k, list);
      this._rerenderContent();
      return;
    }
    if (d.promptAction) return this._onPromptAction(el);
    if (d.save) return this._saveCard(d.save, el);
    if (d.cancel) {
      delete this._drafts[d.cancel];
      this._rerenderContent();
      return;
    }
    if (d.new) {
      this._openEditor(null);
      this._rerenderContent();
      return;
    }
    if (d.edit) {
      const area = this._cfg.areas.find((a) => a.id === d.edit);
      if (area) {
        this._openEditor(area);
        this._rerenderContent();
      }
      return;
    }
    switch (d.action) {
      case "menu":
        this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }));
        break;
      case "toggle": {
        const st = this._state(d.entity);
        await this._call("switch", st?.state === "on" ? "turn_off" : "turn_on", { entity_id: d.entity });
        break;
      }
      case "override":
        await this._call("select", "select_option", { entity_id: this._cfg.entities.heating_day_override, option: d.option });
        break;
      case "more-info":
        this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId: d.entity }, bubbles: true, composed: true }));
        break;
      case "close-edit":
        this._edit = null;
        this._rerenderContent();
        break;
      case "save-area":
        await this._saveArea(el);
        break;
      case "delete-area":
        if (confirm(this.ui.confirmDelete)) {
          try {
            this._cfg = await this._ws({ type: `${DOMAIN}/delete_area`, subentry_id: this._edit.id });
            this._statsAt = 0;
            this._edit = null;
            this._render();
            this._toast(this.ui.saved);
          } catch (err) {
            this._cardMessage(el, err.message || String(err), true);
          }
        }
        break;
      default:
        break;
    }
  }

  async _call(domain, service, data) {
    try {
      await this._hass.callService(domain, service, data);
    } catch (err) {
      this._toast(err.message || String(err), true);
    }
  }

  async _saveCard(cardId, button) {
    const draft = this._drafts[cardId];
    if (!draft) return;
    let msg;
    if (cardId === "apikey") {
      msg = draft.remove
        ? { type: `${DOMAIN}/save_api_key`, remove: true }
        : { type: `${DOMAIN}/save_api_key`, api_key: String(draft.api_key || "") };
      if (!draft.remove) this._cardMessage(button, this.ui.checking);
    } else if (cardId === "theta") {
      msg = { type: `${DOMAIN}/save_theta`, theta: draft.theta ?? "" };
    } else {
      msg = { type: `${DOMAIN}/save_options`, options: { ...draft } };
    }
    button.disabled = true;
    try {
      this._cfg = await this._ws(msg);
      this._statsAt = 0;
      delete this._drafts[cardId];
      this._rerenderContent();
      this._toast(this.ui.saved);
    } catch (err) {
      button.disabled = false;
      this._cardMessage(button, this._errorText(err.message || String(err)), true);
    }
  }

  async _saveArea(button) {
    const e = this._edit;
    const msg = { type: `${DOMAIN}/save_area`, title: e.title || "", data: { ...e.data } };
    if (e.id) {
      msg.subentry_id = e.id;
      // only the learned values changed here, the others keep learning undisturbed
      const before = this._cfg.areas.find((a) => a.id === e.id)?.learned || {};
      const changed = Object.entries(e.learned).filter(([key, value]) => value !== before[key]);
      if (changed.length) msg.learned = Object.fromEntries(changed);
    }
    button.disabled = true;
    try {
      const result = await this._ws(msg);
      this._cfg = result.config;
      this._statsAt = 0;
      this._edit = null;
      this._render();
      this._toast(this.ui.saved);
    } catch (err) {
      button.disabled = false;
      this._cardMessage(button, this._errorText(err.message || String(err), true), true);
    }
  }

  _cardMessage(el, text, bad = false) {
    const msg = el.closest(".card")?.querySelector(".msg");
    if (msg) {
      msg.textContent = text;
      msg.classList.toggle("bad", bad);
    }
  }

  _toast(text, bad = false) {
    const toast = this.shadowRoot.querySelector(".toast");
    if (!toast) return;
    toast.textContent = text;
    toast.classList.toggle("bad", bad);
    toast.hidden = false;
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => (toast.hidden = true), 2500);
  }
}

const STYLE = `
:host { display:block; min-height:100vh; overflow-x:hidden; background:var(--primary-background-color); color:var(--primary-text-color); font-family:var(--paper-font-body1_-_font-family, Roboto, sans-serif); }
* { box-sizing:border-box; }
.toolbar { display:flex; align-items:center; height:56px; padding:0 12px; background:var(--app-header-background-color, var(--primary-color)); color:var(--app-header-text-color, #fff); gap:8px; }
.title { display:flex; align-items:center; gap:10px; font-size:20px; font-weight:400; }
.tabs { display:flex; overflow-x:auto; background:var(--app-header-background-color, var(--primary-color)); padding:0 8px; scrollbar-width:none; }
.tab { display:flex; align-items:center; gap:6px; background:none; border:none; color:var(--app-header-text-color, #fff); opacity:.75; padding:10px 14px; cursor:pointer; border-bottom:2px solid transparent; font-size:14px; white-space:nowrap; }
.tab.active { opacity:1; border-bottom-color:var(--app-header-text-color, #fff); }
.tab ha-icon { --mdc-icon-size:20px; }
.content { padding:16px; max-width:1200px; margin:0 auto; }
.grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(340px, 1fr)); gap:16px; align-items:start; }
.content > .card { margin-bottom:16px; }
.card { min-width:0; overflow-wrap:anywhere; background:var(--ha-card-background, var(--card-background-color, #fff)); border-radius:var(--ha-card-border-radius, 12px); border:1px solid var(--divider-color, #e0e0e0); padding:16px; box-shadow:var(--ha-card-box-shadow, none); }
.card.error { color:var(--error-color); }
h2 { display:flex; align-items:center; gap:10px; margin:0 0 4px; font-size:18px; font-weight:500; }
h2 ha-icon { color:var(--state-icon-color, var(--primary-color)); }
h3 { margin:20px 0 4px; font-size:15px; font-weight:500; }
.desc { margin:0 0 12px; color:var(--secondary-text-color); font-size:14px; }
.fields { display:grid; grid-template-columns:repeat(auto-fill, minmax(260px, 1fr)); gap:12px 20px; margin-top:8px; }
.field { display:flex; flex-direction:column; gap:4px; font-size:14px; }
.lbl { font-weight:500; }
small { color:var(--secondary-text-color); font-size:12px; line-height:1.3; }
input[type=text], input[type=number], input[type=time], input[type=password], select {
  font:inherit; color:var(--primary-text-color); background:var(--input-fill-color, var(--secondary-background-color, #f5f5f5));
  border:1px solid var(--divider-color, #ccc); border-radius:8px; padding:8px 10px; width:100%; }
input:focus, select:focus { outline:2px solid var(--primary-color); outline-offset:-1px; }
.with-unit { display:flex; align-items:center; gap:6px; }
.unit { color:var(--secondary-text-color); min-width:24px; white-space:nowrap; }
.entity-hint { font-size:12px; color:var(--secondary-text-color); min-height:14px; }
.entity-hint.bad, .chip.bad, .msg.bad { color:var(--error-color, #db4437); }
.toggle-row { flex-direction:row; align-items:center; justify-content:space-between; gap:12px; cursor:pointer; }
.toggle-row > span:first-child { display:flex; flex-direction:column; gap:2px; }
.switch-input { display:none; }
.switch { position:relative; flex:none; width:36px; height:20px; border-radius:10px; background:var(--switch-unchecked-track-color, #9e9e9e); transition:background .2s; }
.switch::after { content:""; position:absolute; top:2px; left:2px; width:16px; height:16px; border-radius:50%; background:#fff; transition:left .2s; }
.switch.on { background:var(--switch-checked-track-color, var(--primary-color)); }
.switch.on::after { left:18px; }
.chips { display:flex; flex-wrap:wrap; gap:6px; }
.chip { max-width:100%; overflow-wrap:anywhere; display:inline-flex; align-items:center; gap:4px; background:var(--secondary-background-color, #eee); border-radius:16px; padding:3px 4px 3px 10px; font-size:13px; }
.chip-btn { border:none; background:none; cursor:pointer; color:var(--secondary-text-color); padding:0 4px; font-size:12px; }
.actions { display:flex; align-items:center; justify-content:flex-end; gap:8px; margin-top:16px; flex-wrap:wrap; }
.msg { margin-right:auto; font-size:13px; color:var(--secondary-text-color); }
.grow { flex:1; }
.btn { display:inline-flex; align-items:center; gap:6px; font:inherit; font-weight:500; border-radius:18px; padding:8px 16px; cursor:pointer; border:1px solid var(--divider-color); background:none; color:var(--primary-color); }
.btn ha-icon { --mdc-icon-size:18px; }
.btn.primary { background:var(--primary-color); color:var(--text-primary-color, #fff); border-color:var(--primary-color); }
.btn.danger { color:var(--error-color, #db4437); border-color:var(--error-color, #db4437); }
.btn:disabled { opacity:.45; cursor:default; }
.icon-btn { background:none; border:none; color:inherit; cursor:pointer; padding:4px; display:inline-flex; }
.status { display:flex; flex-direction:column; gap:16px; }
.status-main { display:flex; align-items:center; gap:16px; }
.status-main ha-icon { --mdc-icon-size:56px; flex:none; }
.status-text { font-size:22px; font-weight:500; margin-bottom:2px; }
.segments { display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }
.segment { border:1px solid var(--divider-color); background:none; color:var(--primary-text-color); border-radius:16px; padding:6px 12px; cursor:pointer; font:inherit; font-size:14px; }
.segment.on { background:var(--primary-color); color:var(--text-primary-color, #fff); border-color:var(--primary-color); }
.segment:disabled { opacity:.45; cursor:default; }
.tiles { display:grid; grid-template-columns:repeat(auto-fill, minmax(150px, 1fr)); gap:8px; margin:8px 0; }
.tile { display:flex; align-items:center; gap:8px; padding:10px; border-radius:10px; border:1px solid var(--divider-color); background:none; color:var(--primary-text-color); cursor:pointer; text-align:left; font:inherit; font-size:14px; }
.tile span:nth-child(2) { flex:1; }
.tile.on { border-color:var(--primary-color); }
.tile.on ha-icon { color:var(--primary-color); }
.tile:disabled { opacity:.45; cursor:default; }
.rows { display:flex; flex-direction:column; }
.row { display:flex; align-items:center; gap:10px; padding:8px 4px; border-bottom:1px solid var(--divider-color); font:inherit; font-size:14px; color:var(--primary-text-color); background:none; border-left:none; border-right:none; border-top:none; text-align:left; width:100%; }
.row:last-child { border-bottom:none; }
.row > span { min-width:0; overflow-wrap:anywhere; }
.row > span.grow { flex:1 1 40%; min-width:7em; overflow-wrap:normal; }
.row > span.muted { flex:0 1 auto; text-align:right; }
.row > .meta { flex:0 1 auto; display:flex; flex-wrap:wrap; justify-content:flex-end; align-items:center; gap:4px 6px; }
.temp { white-space:nowrap; }
.row.link { cursor:pointer; }
.row.link:hover, tbody tr:hover { background:var(--secondary-background-color, #f5f5f5); }
.warn-row ha-icon { color:var(--warning-color, #ffa600); flex:none; }
.muted { color:var(--secondary-text-color); }
.small { font-size:12px; }
.show-narrow { display:none; }
.pill { flex:none; display:inline-block; border-radius:12px; padding:2px 10px; margin:1px 0; font-size:12px; background:var(--secondary-background-color, #eee); white-space:nowrap; }
.pill.ok { background:rgba(67,160,71,.15); color:var(--success-color, #2e7d32); }
.pill.warn { background:rgba(255,166,0,.18); color:var(--warning-color, #b26a00); }
.pill.bad { background:rgba(219,68,55,.15); color:var(--error-color, #db4437); }
.pill.muted { color:var(--secondary-text-color); }
.field > .pill { align-self:flex-start; }
.badge { display:inline-block; font-size:11px; border:1px solid var(--divider-color); border-radius:10px; padding:1px 8px; margin:4px 4px 0 0; color:var(--secondary-text-color); }
.table-wrap { width:100%; overflow-x:auto; }
table { width:100%; border-collapse:collapse; font-size:14px; table-layout:fixed; }
th.c-icon { width:40px; } th.c-temp { width:140px; } th.c-state { width:150px; } th.c-edit { width:32px; }
td.c-name div { overflow-wrap:anywhere; }
td.c-name div:first-child { overflow-wrap:break-word; hyphens:auto; }
td.c-state .pill { margin-right:4px; }
th { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; text-align:left; font-weight:500; color:var(--secondary-text-color); padding:6px 8px; border-bottom:1px solid var(--divider-color); }
td { padding:8px; border-bottom:1px solid var(--divider-color); vertical-align:middle; }
tbody tr { cursor:pointer; }
table.limits tbody tr { cursor:default; }
table.limits tbody tr:hover { background:none; }
table.limits th.c-name { width:34%; }
table.limits td { padding:4px; }
.learn-cards { display:grid; grid-template-columns:repeat(auto-fill, minmax(300px, 1fr)); gap:12px; align-items:start; margin-bottom:12px; }
.card.learn { padding:12px 14px; }
.learn-head { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.learn-head h2 { margin:0; font-size:16px; }
.learn-head .pill ha-icon { --mdc-icon-size:14px; margin-right:4px; vertical-align:-2px; }
.learn-grid { display:grid; grid-template-columns:1fr 1fr; gap:6px 12px; margin-top:8px; }
.learn-cell { display:flex; flex-direction:column; min-width:0; font-size:14px; }
.learn-cell .lbl { font-weight:400; color:var(--secondary-text-color); display:flex; align-items:center; gap:4px; }
.learn-cell .lbl ha-icon { --mdc-icon-size:14px; color:var(--state-icon-color, var(--primary-color)); flex:none; }
.card.learn details { margin-top:8px; }
.card.learn summary { font-size:13px; }
details { margin-top:16px; }
.prompt-block { border-top:1px solid var(--divider-color, #e0e0e0); padding:8px 0; }
.prompt-block.off .lbl, .prompt-block.off textarea { opacity:.55; }
.prompt-block details { margin-top:4px; }
.prompt-block .actions { margin-top:6px; }
.card[data-card="prompts"] h3 { margin:20px 0 8px; font-size:15px; }
textarea { width:100%; box-sizing:border-box; font:inherit; font-size:13px; padding:8px; border-radius:6px; border:1px solid var(--divider-color); background:var(--card-background-color, #fff); color:var(--primary-text-color); resize:vertical; }
.prompt-preview { white-space:pre-wrap; overflow-wrap:anywhere; font-size:12px; background:var(--secondary-background-color, #f5f5f5); padding:8px; border-radius:6px; max-height:320px; overflow:auto; }
summary { cursor:pointer; font-weight:500; color:var(--primary-color); }
details .desc { margin-top:8px; }
.toast { position:fixed; bottom:24px; left:50%; transform:translateX(-50%); background:var(--primary-text-color); color:var(--primary-background-color); padding:10px 18px; border-radius:8px; z-index:10; }
.toast.bad { background:var(--error-color, #db4437); color:#fff; }
@media (max-width: 700px) {
  .hide-narrow { display:none; } .show-narrow { display:inline; } .content { padding:8px; } .grid { grid-template-columns:1fr; }
  .tab span { display:none; } .tab.active span { display:inline; } .tab { padding:10px 12px; }
  .fields { grid-template-columns:1fr; }
  th.c-icon { width:32px; } th.c-temp { width:84px; } th.c-state { width:96px; }
  td { padding:8px 4px; } .entity-id { font-size:11px; }
  table.limits th.c-name { width:40%; }
  .card { padding:12px; }
}
`;

if (!customElements.get("ai-heating-assistant-panel")) {
  customElements.define("ai-heating-assistant-panel", AiHeatingAssistantPanel);
}
