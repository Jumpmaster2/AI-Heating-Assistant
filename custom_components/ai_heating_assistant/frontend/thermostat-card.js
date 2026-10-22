// AI Heating Assistant cards, plain web components without build step, loaded on
// every dashboard by the integration:
// custom:ai-heating-thermostat-card: the dial of the Home Assistant thermostat card,
//   with the room humidity next to the second temperature (same size).
// custom:ai-heating-climate-tile-card: a tile with the name and temperature and
//   humidity side by side.
// custom:ai-heating-thermostat-compact-card: the thermostat without the dial, half as
//   high; a colour bar shows the state, a tap opens the thermostat.

const DOMAIN = "ai_heating_assistant";
const CARD = "ai-heating-thermostat-card";
const TILE = "ai-heating-climate-tile-card";
const COMPACT = "ai-heating-thermostat-compact-card";

const UI = {
  de: {
    name: "AI Heating Assistant Thermostat",
    description: "Thermostat mit Luftfeuchte eines Heizbereichs.",
    entity: "Thermostat",
    title: "Name",
    primary: "Ist-Temperatur groß anzeigen",
    humidity: "Luftfeuchte anzeigen",
    notFound: "Entität nicht gefunden",
    unavailable: "Nicht verfügbar",
    target: "Solltemperatur",
    tileName: "AI Heating Assistant Raumklima",
    tileDescription: "Name mit Temperatur und Luftfeuchte nebeneinander.",
    temperatureEntity: "Temperatursensor (statt Thermostat)",
    humidityEntity: "Feuchtesensor (statt Thermostat)",
    compactName: "AI Heating Assistant Thermostat kompakt",
    compactDescription: "Thermostat ohne Bogen: Temperatur, Luftfeuchte, Sollwert und Status.",
  },
  en: {
    name: "AI Heating Assistant thermostat",
    description: "Thermostat of a heating area with its humidity.",
    entity: "Thermostat",
    title: "Name",
    primary: "Show the current temperature large",
    humidity: "Show the humidity",
    notFound: "Entity not found",
    unavailable: "Unavailable",
    target: "Target temperature",
    tileName: "AI Heating Assistant room climate",
    tileDescription: "Name with temperature and humidity side by side.",
    temperatureEntity: "Temperature sensor (instead of the thermostat)",
    humidityEntity: "Humidity sensor (instead of the thermostat)",
    compactName: "AI Heating Assistant thermostat compact",
    compactDescription: "Thermostat without the dial: temperature, humidity, target and state.",
  },
};

const ui = (lang) => UI[(lang || "en").split("-")[0]] || UI.en;
const docLang = () => document.documentElement.lang || navigator.language;

// Dial geometry (viewBox -160 -160 320 320): 270° from bottom left to bottom right.
const R = 145;
const START = 135;
const SWEEP = 270;

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const point = (deg) => {
  const rad = (deg * Math.PI) / 180;
  return [R * Math.cos(rad), R * Math.sin(rad)];
};

const arc = (from, to) => {
  const [x1, y1] = point(from);
  const [x2, y2] = point(to);
  const large = to - from > 180 ? 1 : 0;
  return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${R} ${R} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
};

class AiHeatingThermostatCard extends HTMLElement {
  static getStubConfig(hass) {
    const entity = Object.values(hass?.entities || {}).find(
      (e) => e.platform === DOMAIN && e.entity_id.startsWith("climate.")
    );
    return { entity: entity?.entity_id || "" };
  }

  static getConfigForm() {
    const t = ui(docLang());
    return {
      schema: [
        { name: "entity", required: true, selector: { entity: { filter: { domain: "climate", integration: DOMAIN } } } },
        { name: "name", selector: { text: {} } },
        { name: "show_current_as_primary", selector: { boolean: {} } },
        { name: "show_humidity", default: true, selector: { boolean: {} } },
      ],
      computeLabel: (s) =>
        ({ entity: t.entity, name: t.title, show_current_as_primary: t.primary, show_humidity: t.humidity })[s.name],
    };
  }

  setConfig(config) {
    if (!config?.entity) throw new Error("entity required");
    this._config = { show_humidity: true, ...config };
    this._built = false;
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 7;
  }

  getGridOptions() {
    return { columns: 6, rows: "auto", min_columns: 4 };
  }

  connectedCallback() {
    this._observe();
  }

  disconnectedCallback() {
    clearTimeout(this._sendTimer);
    this._resize?.disconnect();
  }

  // A fixed height (grid_options rows as a number): the ring shrinks to fit, as in the
  // thermostat card of Home Assistant. Otherwise the card takes the height of the ring.
  get _fixed() {
    return typeof this._config?.grid_options?.rows === "number";
  }

  _observe() {
    this._resize?.disconnect();
    if (!this._built || !this.isConnected || !this._fixed) return;
    const dial = this.shadowRoot.querySelector(".dial");
    this._resize = new ResizeObserver(() => {
      const size = Math.max(Math.min(dial.clientWidth - 32, dial.clientHeight), 0);
      dial.style.setProperty("--size", `${size}px`);
    });
    this._resize.observe(dial);
  }

  get _t() {
    return ui(this._hass?.locale?.language || this._hass?.language);
  }

  get _state() {
    return this._hass?.states[this._config.entity];
  }

  _build() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; height: 100%; }
        ha-card { height: 100%; display: flex; flex-direction: column; box-sizing: border-box; padding: 0 0 12px; overflow: hidden; }
        .header { position: relative; display: flex; align-items: center; justify-content: center; min-height: 48px; padding: 8px 44px 0; }
        .title { font-size: 1.5em; line-height: 1.3; color: var(--primary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: pointer; }
        .more { position: absolute; top: 6px; right: 4px; width: 40px; height: 40px; border: none; border-radius: 50%; background: none; color: var(--secondary-text-color); cursor: pointer; display: flex; align-items: center; justify-content: center; padding: 0; }
        .more:hover { background: rgba(127, 127, 127, 0.15); }
        .dial { position: relative; width: 100%; max-width: 320px; margin: 0 auto; flex: 1; display: flex; align-items: center; justify-content: center; padding: 0 16px; box-sizing: border-box; }
        .ring { position: relative; width: 100%; aspect-ratio: 1; container-type: inline-size; }
        .fixed .dial { flex: 1 1 0; min-height: 0; max-width: none; }
        .fixed .ring { width: var(--size, 100%); height: var(--size, auto); }
        .fixed .header { min-height: 36px; padding-top: 4px; }
        .fixed .title { font-size: 1.25em; }
        .fixed .more { top: 0; }
        svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
        .knob { fill: transparent; touch-action: none; cursor: grab; }
        .dragging .knob { cursor: grabbing; }
        .track { stroke: var(--primary-text-color); stroke-opacity: 0.1; stroke-width: 24; fill: none; stroke-linecap: round; pointer-events: none; }
        .value { stroke: var(--color); stroke-opacity: 0.5; stroke-width: 24; fill: none; stroke-linecap: round; pointer-events: none; transition: stroke-opacity 0.3s; }
        .heating .value { stroke-opacity: 1; }
        .current { fill: var(--primary-text-color); fill-opacity: 0.5; pointer-events: none; }
        .handle { fill: #fff; stroke: var(--color); stroke-width: 4; outline: none; pointer-events: none; }
        .handle:focus-visible { stroke-width: 7; }
        .off .handle, .off .knob, .off .value, .unavailable .handle, .unavailable .knob, .unavailable .value { display: none; }
        .info { position: absolute; inset: 18% 16%; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; pointer-events: none; color: var(--primary-text-color); }
        .action { font-size: clamp(12px, 5.5cqw, 18px); font-weight: 500; line-height: 1.3; color: var(--primary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
        .big { display: flex; align-items: flex-start; justify-content: center; line-height: 1; margin: 2cqw 0; font-weight: 400; }
        .big .int { font-size: clamp(36px, 22cqw, 64px); letter-spacing: -0.02em; }
        .big .side { display: flex; flex-direction: column; align-items: flex-start; font-size: clamp(14px, 8cqw, 24px); line-height: 1.15; margin-left: 2px; padding-top: 0.15em; }
        .big .side .dec { margin-top: 0.15em; }
        .big.none .int { font-size: clamp(28px, 16cqw, 48px); }
        .secondary { display: flex; align-items: center; justify-content: center; flex-wrap: nowrap; gap: 0 0.6em; font-size: clamp(10px, 6cqw, 16px); font-weight: 500; line-height: 1.4; white-space: nowrap; max-width: 100%; }
        .secondary span { display: inline-flex; align-items: center; gap: 0.2em; }
        .secondary ha-icon { --mdc-icon-size: 1.2em; }
        .warning { padding: 16px; color: var(--error-color); }
      </style>
      <ha-card>
        <div class="header">
          <div class="title" data-more></div>
          <button class="more" data-more><ha-icon icon="mdi:dots-vertical"></ha-icon></button>
        </div>
        <div class="dial">
          <div class="ring">
            <svg viewBox="-160 -160 320 320">
              <path class="track" d="${arc(START, START + SWEEP)}"></path>
              <path class="value"></path>
              <circle class="current" r="4"></circle>
              <circle class="handle" r="11" tabindex="0" role="slider"></circle>
              <circle class="knob" r="40"></circle>
            </svg>
            <div class="info">
              <div class="action"></div>
              <div class="big"></div>
              <div class="secondary"></div>
            </div>
          </div>
        </div>
      </ha-card>`;
    const root = this.shadowRoot;
    this._el = {
      card: root.querySelector("ha-card"),
      title: root.querySelector(".title"),
      svg: root.querySelector("svg"),
      value: root.querySelector(".value"),
      current: root.querySelector(".current"),
      handle: root.querySelector(".handle"),
      knob: root.querySelector(".knob"),
      action: root.querySelector(".action"),
      big: root.querySelector(".big"),
      secondary: root.querySelector(".secondary"),
    };
    root.querySelectorAll("[data-more]").forEach((el) =>
      el.addEventListener("click", () =>
        this.dispatchEvent(
          new CustomEvent("hass-more-info", { detail: { entityId: this._config.entity }, bubbles: true, composed: true })
        )
      )
    );
    // Only the point itself is dragged: a touch elsewhere on the ring scrolls the page.
    // touchstart is cancelled as well, some web views ignore touch-action in SVG.
    this._el.knob.addEventListener("pointerdown", (ev) => this._dragStart(ev));
    this._el.knob.addEventListener("touchstart", (ev) => this._editable() && ev.preventDefault(), {
      passive: false,
    });
    this._el.svg.addEventListener("pointermove", (ev) => this._dragMove(ev));
    this._el.svg.addEventListener("pointerup", (ev) => this._dragEnd(ev));
    this._el.svg.addEventListener("pointercancel", (ev) => this._dragEnd(ev, true));
    this._el.handle.addEventListener("keydown", (ev) => this._key(ev));
    this._built = true;
    this._observe();
  }

  // --- values ---

  _limits(st) {
    const a = st.attributes;
    const step = Number(a.target_temp_step) || 0.5;
    return { min: Number(a.min_temp ?? 7), max: Number(a.max_temp ?? 35), step };
  }

  _round(value, st) {
    const { min, max, step } = this._limits(st);
    const lo = Math.ceil(min / step - 1e-9) * step;
    const hi = Math.floor(max / step + 1e-9) * step;
    const v = Math.round(value / step) * step;
    return Number(Math.min(Math.max(v, lo), hi).toFixed(4));
  }

  _target(st) {
    if (this._pending != null) {
      const reached = Math.abs(Number(st.attributes.temperature) - this._pending) < 1e-6;
      if (!reached && Date.now() - this._pendingAt < 5000) return this._pending;
      this._pending = null;
    }
    const t = st.attributes.temperature;
    return t == null ? null : Number(t);
  }

  _fraction(value, st) {
    const { min, max } = this._limits(st);
    if (value == null || Number.isNaN(value) || max <= min) return null;
    return Math.min(Math.max((value - min) / (max - min), 0), 1);
  }

  _number(value, digits) {
    const lang = this._hass.locale?.language || this._hass.language;
    return Number(value).toLocaleString(lang, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  _digits(st) {
    return this._limits(st).step < 1 ? 1 : 0;
  }

  _unit() {
    return this._hass.config?.unit_system?.temperature || "°C";
  }

  // --- rendering ---

  _render() {
    if (!this._config || !this._hass) return;
    if (!this._built) this._build();
    const st = this._state;
    const el = this._el;
    const t = this._t;
    if (!st) {
      el.card.innerHTML = `<div class="warning">${esc(t.notFound)}: ${esc(this._config.entity)}</div>`;
      this._built = false;
      return;
    }
    const unavailable = st.state === "unavailable" || st.state === "unknown";
    const off = st.state === "off";
    const heating = st.attributes.hvac_action === "heating";
    el.card.className = [this._fixed && "fixed", this._dragging && "dragging", unavailable && "unavailable", off && "off", heating && "heating"].filter(Boolean).join(" ");
    el.card.style.setProperty(
      "--color",
      off || unavailable
        ? "var(--state-climate-off-color, var(--disabled-color, #8a8a8a))"
        : "var(--state-climate-heat-color, #ff8100)"
    );
    el.title.textContent = this._config.name || st.attributes.friendly_name || this._config.entity;

    const target = this._target(st);
    const current = st.attributes.current_temperature;
    const tf = this._fraction(target, st);
    const cf = this._fraction(current == null ? null : Number(current), st);
    if (tf != null && !unavailable) {
      const deg = START + tf * SWEEP;
      el.value.setAttribute("d", tf > 0.002 ? arc(START, deg) : "");
      const [x, y] = point(deg);
      for (const c of [el.handle, el.knob]) {
        c.setAttribute("cx", x.toFixed(2));
        c.setAttribute("cy", y.toFixed(2));
        c.style.display = "";
      }
    } else {
      el.value.setAttribute("d", "");
      el.handle.style.display = "none";
      el.knob.style.display = "none";
    }
    if (cf != null && !unavailable) {
      const [x, y] = point(START + cf * SWEEP);
      el.current.setAttribute("cx", x.toFixed(2));
      el.current.setAttribute("cy", y.toFixed(2));
      el.current.style.display = "";
    } else {
      el.current.style.display = "none";
    }
    el.handle.setAttribute("aria-label", t.target);
    el.handle.setAttribute("aria-valuemin", String(this._limits(st).min));
    el.handle.setAttribute("aria-valuemax", String(this._limits(st).max));
    if (target != null) el.handle.setAttribute("aria-valuenow", String(target));

    // label, big number, secondary line (temperature and humidity side by side)
    el.action.textContent = unavailable ? t.unavailable : this._actionText(st);
    const primaryCurrent = this._config.show_current_as_primary;
    const bigValue = unavailable ? null : primaryCurrent ? current : off ? null : target;
    el.big.className = bigValue == null ? "big none" : "big";
    el.big.innerHTML = bigValue == null ? `<span class="int">–</span>` : this._bigHtml(Number(bigValue), st);

    const parts = [];
    if (!unavailable) {
      const second = primaryCurrent ? (off ? null : target) : current;
      if (second != null) {
        const icon = primaryCurrent ? "mdi:thermostat" : "mdi:thermometer";
        parts.push(`<span><ha-icon icon="${icon}"></ha-icon>${esc(this._number(second, this._digits(st)))} ${esc(this._unit())}</span>`);
      }
      const humidity = st.attributes.current_humidity;
      if (this._config.show_humidity !== false && humidity != null) {
        parts.push(`<span><ha-icon icon="mdi:water-percent"></ha-icon>${esc(this._number(humidity, 0))} %</span>`);
      }
    }
    const html = parts.join("");
    if (el.secondary.dataset.html !== html) {
      el.secondary.innerHTML = html;
      el.secondary.dataset.html = html;
    }
  }

  _actionText(st) {
    const action = st.attributes.hvac_action;
    if (st.state === "off" || action == null) {
      return typeof this._hass.formatEntityState === "function" ? this._hass.formatEntityState(st) : st.state;
    }
    if (typeof this._hass.formatEntityAttributeValue === "function") {
      return this._hass.formatEntityAttributeValue(st, "hvac_action");
    }
    return action;
  }

  _bigHtml(value, st) {
    const digits = this._digits(st);
    const text = this._number(value, digits);
    const sep = this._number(1.5, 1).replace(/\d/g, "");
    const [int, dec] = digits ? [text.slice(0, text.lastIndexOf(sep)), text.slice(text.lastIndexOf(sep))] : [text, ""];
    return `<span class="int">${esc(int)}</span><span class="side"><span>${esc(this._unit())}</span>${
      dec ? `<span class="dec">${esc(dec)}</span>` : ""
    }</span>`;
  }

  // --- interaction ---

  _valueAt(ev) {
    const ctm = this._el.svg.getScreenCTM();
    if (!ctm) return null;
    const p = new DOMPoint(ev.clientX, ev.clientY).matrixTransform(ctm.inverse());
    let a = (((Math.atan2(p.y, p.x) * 180) / Math.PI - START) % 360 + 360) % 360;
    if (a > SWEEP) a = a > SWEEP + (360 - SWEEP) / 2 ? 0 : SWEEP;
    const st = this._state;
    const { min, max } = this._limits(st);
    return this._round(min + (a / SWEEP) * (max - min), st);
  }

  _editable() {
    const st = this._state;
    return st && st.state !== "off" && st.state !== "unavailable" && st.state !== "unknown";
  }

  _dragStart(ev) {
    if (!this._editable() || ev.button > 0) return;
    ev.preventDefault();
    this._dragging = true;
    this._el.svg.setPointerCapture?.(ev.pointerId);
    this._el.handle.focus({ preventScroll: true });
    this._render();
  }

  _dragMove(ev) {
    if (this._dragging) this._preview(this._valueAt(ev));
  }

  // A cancelled gesture (e.g. the page scrolls after all) changes nothing.
  _dragEnd(ev, cancelled = false) {
    if (!this._dragging) return;
    this._dragging = false;
    this._el.svg.releasePointerCapture?.(ev.pointerId);
    if (cancelled) {
      this._pending = null;
      this._render();
    } else {
      this._send(0);
    }
  }

  _key(ev) {
    if (!this._editable()) return;
    const st = this._state;
    const { min, max, step } = this._limits(st);
    const current = this._target(st) ?? min;
    const delta = { ArrowUp: step, ArrowRight: step, ArrowDown: -step, ArrowLeft: -step, PageUp: 1, PageDown: -1 }[ev.key];
    let value = delta != null ? current + delta : ev.key === "Home" ? min : ev.key === "End" ? max : null;
    if (value == null) return;
    ev.preventDefault();
    this._preview(this._round(value, st));
    this._send(1000);
  }

  _preview(value) {
    if (value == null) return;
    this._pending = value;
    this._pendingAt = Date.now();
    this._render();
  }

  _send(delay) {
    clearTimeout(this._sendTimer);
    this._sendTimer = setTimeout(() => {
      const value = this._pending;
      const st = this._state;
      if (value == null || !st) return;
      this._pendingAt = Date.now();
      if (Math.abs(Number(st.attributes.temperature) - value) < 1e-6) return;
      this._hass.callService("climate", "set_temperature", { entity_id: this._config.entity, temperature: value });
    }, delay);
  }
}

// Tile with the name and temperature and humidity side by side. The values come
// from the thermostat (entity) or from sensors (temperature_entity, humidity_entity,
// also for areas without a heating circuit); a sensor wins over the thermostat.
class AiHeatingClimateTileCard extends HTMLElement {
  static getStubConfig(hass) {
    return AiHeatingThermostatCard.getStubConfig(hass);
  }

  static getConfigForm() {
    const t = ui(docLang());
    const sensor = (deviceClass) => ({ entity: { filter: { domain: "sensor", device_class: deviceClass } } });
    return {
      schema: [
        { name: "entity", selector: { entity: { filter: { domain: "climate", integration: DOMAIN } } } },
        { name: "name", selector: { text: {} } },
        { name: "temperature_entity", selector: sensor("temperature") },
        { name: "humidity_entity", selector: sensor("humidity") },
      ],
      computeLabel: (s) =>
        ({
          entity: t.entity,
          name: t.title,
          temperature_entity: t.temperatureEntity,
          humidity_entity: t.humidityEntity,
        })[s.name],
    };
  }

  setConfig(config) {
    if (!config?.entity && !config?.temperature_entity && !config?.humidity_entity) {
      throw new Error("entity, temperature_entity or humidity_entity required");
    }
    this._config = { ...config };
    this._html = null;
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 1;
  }

  getGridOptions() {
    return { columns: 6, rows: 1, min_columns: 3, min_rows: 1 };
  }

  _number(value, digits) {
    const lang = this._hass.locale?.language || this._hass.language;
    return Number(value).toLocaleString(lang, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  // [text, entity for more-info] of a sensor or of a thermostat attribute
  _value(sensorId, attribute, digits, unit) {
    const sensor = sensorId && this._hass.states[sensorId];
    if (sensorId) {
      if (!sensor || sensor.state === "unavailable" || sensor.state === "unknown") return ["–", sensorId];
      const text =
        typeof this._hass.formatEntityState === "function"
          ? this._hass.formatEntityState(sensor)
          : `${sensor.state} ${sensor.attributes.unit_of_measurement || ""}`.trim();
      return [text, sensorId];
    }
    const climate = this._config.entity && this._hass.states[this._config.entity];
    const value = climate?.attributes[attribute];
    if (value == null || Number.isNaN(Number(value))) return [null, this._config.entity];
    return [`${this._number(value, digits)} ${unit}`, this._config.entity];
  }

  _render() {
    if (!this._config || !this._hass) return;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.addEventListener("click", (ev) => {
        const target = ev.composedPath().find((el) => el.dataset?.entity);
        if (!target) return;
        this.dispatchEvent(
          new CustomEvent("hass-more-info", { detail: { entityId: target.dataset.entity }, bubbles: true, composed: true })
        );
      });
    }
    const c = this._config;
    const t = ui(this._hass.locale?.language || this._hass.language);
    const main = c.entity || c.temperature_entity || c.humidity_entity;
    const st = this._hass.states[main];
    const name = c.name || st?.attributes.friendly_name || main;
    const unit = this._hass.config?.unit_system?.temperature || "°C";
    const values = [];
    const temp = this._value(c.temperature_entity, "current_temperature", 1, unit);
    if (temp[0] != null) values.push(["mdi:thermometer", ...temp]);
    const hum = this._value(c.humidity_entity, "current_humidity", 0, "%");
    if (hum[0] != null) values.push(["mdi:water-percent", ...hum]);
    const body = !st
      ? `<div class="values"><span class="warning">${esc(t.notFound)}</span></div>`
      : `<div class="values">${values
          .map(
            ([icon, text, entity]) =>
              `<span class="value" data-entity="${esc(entity)}"><ha-icon icon="${icon}"></ha-icon><span>${esc(text)}</span></span>`
          )
          .join("")}</div>`;
    const html = `<div class="name" data-entity="${esc(main)}">${esc(name)}</div>${body}`;
    if (html === this._html) return;
    this._html = html;
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; height: 100%; }
        ha-card { height: 100%; box-sizing: border-box; padding: 0 12px; display: flex; flex-direction: column; justify-content: center; gap: 2px; overflow: hidden; cursor: pointer; }
        .name { font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500); line-height: 20px; letter-spacing: 0.1px; color: var(--primary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .values { display: flex; align-items: center; gap: 0 16px; min-width: 0; font-size: var(--ha-font-size-s, 12px); line-height: 18px; letter-spacing: 0.4px; color: var(--primary-text-color); white-space: nowrap; overflow: hidden; }
        .value { display: inline-flex; align-items: center; gap: 4px; min-width: 0; }
        .value span { overflow: hidden; text-overflow: ellipsis; }
        ha-icon { --mdc-icon-size: 18px; flex: none; color: var(--tile-color, var(--state-icon-color, #44739e)); }
        .warning { color: var(--error-color); }
      </style>
      <ha-card>${html}</ha-card>`;
  }
}

// Thermostat without the dial (half as high): name, current temperature and humidity
// large, target and state small. A bar on the left shows the state (orange while
// heating). A tap opens the thermostat, the target is not changed on the dashboard.
class AiHeatingThermostatCompactCard extends HTMLElement {
  static getStubConfig(hass) {
    return AiHeatingThermostatCard.getStubConfig(hass);
  }

  static getConfigForm() {
    const t = ui(docLang());
    return {
      schema: [
        { name: "entity", required: true, selector: { entity: { filter: { domain: "climate", integration: DOMAIN } } } },
        { name: "name", selector: { text: {} } },
        { name: "show_humidity", default: true, selector: { boolean: {} } },
      ],
      computeLabel: (s) => ({ entity: t.entity, name: t.title, show_humidity: t.humidity })[s.name],
    };
  }

  setConfig(config) {
    if (!config?.entity) throw new Error("entity required");
    this._config = { show_humidity: true, ...config };
    this._html = null;
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 2;
  }

  getGridOptions() {
    return { columns: 6, rows: 2, min_columns: 4, min_rows: 2 };
  }

  _number(value, digits) {
    const lang = this._hass.locale?.language || this._hass.language;
    return Number(value).toLocaleString(lang, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  _render() {
    if (!this._config || !this._hass) return;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.addEventListener("click", () =>
        this.dispatchEvent(
          new CustomEvent("hass-more-info", { detail: { entityId: this._config.entity }, bubbles: true, composed: true })
        )
      );
    }
    const st = this._hass.states[this._config.entity];
    const t = ui(this._hass.locale?.language || this._hass.language);
    const unit = this._hass.config?.unit_system?.temperature || "°C";
    let html;
    if (!st) {
      html = `<div class="name">${esc(this._config.name || this._config.entity)}</div><div class="line warning">${esc(t.notFound)}</div>`;
    } else {
      const a = st.attributes;
      const unavailable = st.state === "unavailable" || st.state === "unknown";
      const heating = a.hvac_action === "heating";
      const mode = unavailable ? "unavailable" : st.state === "off" ? "off" : heating ? "heating" : "idle";
      const status = unavailable ? t.unavailable : AiHeatingThermostatCard.prototype._actionText.call(this, st);
      const temp = a.current_temperature;
      const hum = this._config.show_humidity !== false ? a.current_humidity : null;
      const target = st.state === "off" || unavailable ? null : a.temperature;
      const vals = [
        `<span class="temp">${temp == null || unavailable ? "–" : `${esc(this._number(temp, 1))}°`}</span>`,
      ];
      if (hum != null && !unavailable) {
        vals.push(
          `<span class="sep"></span><span class="hum"><ha-icon icon="mdi:water-percent"></ha-icon>${esc(this._number(hum, 0))} %</span>`
        );
      }
      const line = [
        target != null ? `<span class="target"><ha-icon icon="mdi:thermostat"></ha-icon>${esc(this._number(target, 1))} ${esc(unit)}</span>` : "",
        `<span class="status">${esc(status)}</span>`,
      ]
        .filter(Boolean)
        .join('<span class="dot">·</span>');
      html = `<ha-card class="${mode}"><div class="name">${esc(this._config.name || a.friendly_name || this._config.entity)}</div>
        <div class="vals">${vals.join("")}</div><div class="line">${line}</div></ha-card>`;
    }
    if (html === this._html) return;
    this._html = html;
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; height: 100%; }
        ha-card { position: relative; height: 100%; min-height: 104px; box-sizing: border-box; padding: 10px 12px 10px 18px; display: flex; flex-direction: column; justify-content: space-between; overflow: hidden; cursor: pointer; container-type: inline-size; --bar: var(--state-climate-off-color, var(--disabled-color, #6f6f6f)); }
        ha-card::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 6px; background: var(--bar); }
        ha-card.heating { --bar: var(--state-climate-heat-color, #ff8100); }
        ha-card.unavailable::before { opacity: 0.4; }
        .name { font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500); line-height: 20px; color: var(--primary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .vals { display: flex; align-items: center; white-space: nowrap; color: var(--primary-text-color); min-width: 0; }
        .temp { font-size: clamp(22px, 14cqw, 32px); line-height: 1.1; font-variant-numeric: tabular-nums; }
        .sep { width: 1px; align-self: stretch; margin: 4px clamp(8px, 5cqw, 12px); background: var(--divider-color, rgba(127, 127, 127, 0.3)); }
        .hum { display: inline-flex; align-items: center; gap: 4px; font-size: clamp(16px, 10cqw, 22px); font-variant-numeric: tabular-nums; }
        .hum ha-icon { --mdc-icon-size: 1em; color: var(--state-icon-color, #44739e); }
        .line { display: flex; align-items: center; gap: 0 4px; font-size: var(--ha-font-size-s, 12px); line-height: 18px; color: var(--secondary-text-color); white-space: nowrap; overflow: hidden; }
        .target { display: inline-flex; align-items: center; gap: 3px; }
        .target ha-icon { --mdc-icon-size: 14px; }
        .heating .status { color: var(--state-climate-heat-color, #ff8100); }
        .status { overflow: hidden; text-overflow: ellipsis; }
        .warning { color: var(--error-color); }
      </style>
      ${st ? html : `<ha-card>${html}</ha-card>`}`;
  }
}

if (!customElements.get(COMPACT)) {
  customElements.define(COMPACT, AiHeatingThermostatCompactCard);
  const t = ui(docLang());
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: COMPACT,
    name: t.compactName,
    description: t.compactDescription,
    preview: true,
    documentationURL: "https://github.com/Jumpmaster2/AI-Heating-Assistant",
  });
}

if (!customElements.get(TILE)) {
  customElements.define(TILE, AiHeatingClimateTileCard);
  const t = ui(docLang());
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: TILE,
    name: t.tileName,
    description: t.tileDescription,
    preview: true,
    documentationURL: "https://github.com/Jumpmaster2/AI-Heating-Assistant",
  });
}

if (!customElements.get(CARD)) {
  customElements.define(CARD, AiHeatingThermostatCard);
  const t = ui(docLang());
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: CARD,
    name: t.name,
    description: t.description,
    preview: true,
    documentationURL: "https://github.com/Jumpmaster2/AI-Heating-Assistant",
  });
}
