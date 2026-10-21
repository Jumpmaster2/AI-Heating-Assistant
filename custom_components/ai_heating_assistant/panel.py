"""Sidebar panel: an overview and all settings on one page."""

from __future__ import annotations

from pathlib import Path

from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER, NAME

PANEL_URL_PATH = "ai-heating-assistant"
PANEL_COMPONENT = "ai-heating-assistant-panel"
STATIC_URL = "/ai_heating_assistant_static"
PANEL_STATIC_URL = "/ai_heating_assistant_panel"
FRONTEND_DIR = Path(__file__).parent / "frontend"
DATA_STATIC = f"{DOMAIN}_static_registered"
DATA_CARD = f"{DOMAIN}_card_url"
CARD_PATH = f"{STATIC_URL}/thermostat-card.js"


async def async_register_panel(hass: HomeAssistant, entry_id: str) -> None:
    """Register the panel (only when the frontend runs, not in tests)."""
    if "frontend" not in hass.config.components or hass.http is None:
        return
    from homeassistant.components import frontend, panel_custom
    from homeassistant.components.http import StaticPathConfig

    # The panel is served below a path with the version, so its imports (labels.js) are
    # new after an update as well; the card keeps its fixed path (dashboard resource).
    # A path can only be registered once per run: keep the version.
    version = hass.data.get(DATA_STATIC)
    if version is None:
        version = await hass.async_add_executor_job(_version)
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=False),
                StaticPathConfig(
                    f"{PANEL_STATIC_URL}/{version}", str(FRONTEND_DIR), cache_headers=False
                ),
            ]
        )
        hass.data[DATA_STATIC] = version
    if not hass.data.get(DATA_CARD):
        # Thermostat card for every dashboard (custom:ai-heating-thermostat-card).
        hass.data[DATA_CARD] = f"{CARD_PATH}?v={version}"
        frontend.add_extra_js_url(hass, hass.data[DATA_CARD])
        await async_set_card_resource(hass, hass.data[DATA_CARD])
    if frontend.async_panel_exists(hass, PANEL_URL_PATH):
        return
    # config_panel_domain: "Configure" on the integration page opens this panel.
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_COMPONENT,
        module_url=f"{PANEL_STATIC_URL}/{version}/panel.js",
        sidebar_title=NAME,
        sidebar_icon="mdi:home-thermometer-outline",
        require_admin=True,
        config={"entry_id": entry_id, "version": version},
        config_panel_domain=DOMAIN,
    )


def async_unregister_panel(hass: HomeAssistant) -> None:
    if "frontend" not in hass.config.components:
        return
    from homeassistant.components import frontend

    if url := hass.data.pop(DATA_CARD, None):
        frontend.remove_extra_js_url(hass, url)
    if frontend.async_panel_exists(hass, PANEL_URL_PATH):
        frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)


def _version() -> str:
    try:
        stamp = max(int(p.stat().st_mtime) for p in FRONTEND_DIR.iterdir())
    except (OSError, ValueError):
        LOGGER.debug("Frontend files not found")
        stamp = 0
    return str(stamp)


async def async_set_card_resource(hass: HomeAssistant, url: str | None) -> None:
    """Keep the card as a dashboard resource (None removes it). The companion app does
    not always load the extra modules of the start page, its resources it loads with
    every dashboard. Only for resources managed in the UI (storage mode)."""
    try:
        from homeassistant.components.lovelace.const import LOVELACE_DATA
    except ImportError:
        return
    data = hass.data.get(LOVELACE_DATA)
    if data is None or getattr(data, "resource_mode", None) != "storage":
        return
    resources = data.resources
    try:
        if not resources.loaded:
            await resources.async_load()
            resources.loaded = True
        ours = [i for i in resources.async_items() if i.get("url", "").split("?")[0] == CARD_PATH]
        for item in ours[1:] if url else ours:
            await resources.async_delete_item(item["id"])
        if not url:
            return
        if not ours:
            await resources.async_create_item({"res_type": "module", "url": url})
        elif ours[0].get("url") != url:
            await resources.async_update_item(ours[0]["id"], {"res_type": "module", "url": url})
    except Exception:  # the card is optional, the control must not fail
        LOGGER.warning("Could not register the thermostat card as a dashboard resource")
