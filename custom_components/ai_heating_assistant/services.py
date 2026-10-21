"""Service actions."""

from __future__ import annotations

import probatio as vol
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError, Unauthorized
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import HeatingCoordinator

SERVICE_EXPORT = "export_parameters"
SERVICE_IMPORT = "import_parameters"
SERVICE_RESET = "reset_learned"
SERVICE_AI_CHECK = "run_ai_check"
SERVICE_VENT_CHECK = "run_ai_ventilation_check"
SERVICE_DECIDE = "decide_heating_day"

ATTR_DATA = "data"
ATTR_INCLUDE_PARAMETERS = "include_parameters"
ATTR_USE_AI = "use_ai"

EXPORT_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})
IMPORT_SCHEMA = vol.Schema(
    {vol.Required(ATTR_DATA): dict, vol.Optional(ATTR_ENTITY_ID): cv.entity_ids}
)
RESET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_INCLUDE_PARAMETERS, default=False): cv.boolean,
    }
)
AI_CHECK_SCHEMA = vol.Schema({})
DECIDE_SCHEMA = vol.Schema({vol.Optional(ATTR_USE_AI, default=True): cv.boolean})


def _coordinator(hass: HomeAssistant) -> HeatingCoordinator:
    entries = [e for e in hass.config_entries.async_loaded_entries(DOMAIN)]
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_loaded")
    return entries[0].runtime_data


def _area_ids(
    hass: HomeAssistant, coordinator: HeatingCoordinator, entity_ids: list[str] | None
) -> list[str] | None:
    """Map entity ids of this integration to area (subentry) ids."""
    if not entity_ids:
        return None
    registry = er.async_get(hass)
    result = []
    for entity_id in entity_ids:
        entry = registry.async_get(entity_id)
        if (
            entry is None
            or entry.platform != DOMAIN
            or entry.config_subentry_id not in coordinator.areas
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_area",
                translation_placeholders={"entity_id": entity_id},
            )
        result.append(entry.config_subentry_id)
    return result


async def _require_admin(hass: HomeAssistant, call: ServiceCall) -> None:
    """Changing and paid services are for administrators, like the panel. Calls
    without a user (automations, scripts) are allowed."""
    if not (user_id := call.context.user_id):
        return
    user = await hass.auth.async_get_user(user_id)
    if user is None or not user.is_admin:
        raise Unauthorized(context=call.context)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register all services."""

    async def export_parameters(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass)
        return coordinator.export_parameters(
            _area_ids(hass, coordinator, call.data.get(ATTR_ENTITY_ID))
        )

    async def import_parameters(call: ServiceCall) -> ServiceResponse:
        await _require_admin(hass, call)
        coordinator = _coordinator(hass)
        try:
            imported = coordinator.import_parameters(
                call.data[ATTR_DATA], _area_ids(hass, coordinator, call.data.get(ATTR_ENTITY_ID))
            )
        except (HomeAssistantError, TypeError, ValueError, KeyError) as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="import_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await coordinator.async_request_refresh()
        return {"imported": imported}

    async def reset_learned(call: ServiceCall) -> None:
        await _require_admin(hass, call)
        coordinator = _coordinator(hass)
        area_ids = _area_ids(hass, coordinator, call.data[ATTR_ENTITY_ID]) or []
        coordinator.reset_learned(area_ids, call.data[ATTR_INCLUDE_PARAMETERS])
        await coordinator.async_request_refresh()

    async def run_ai_check(call: ServiceCall) -> None:
        await _require_admin(hass, call)  # the check costs money
        coordinator = _coordinator(hass)
        if not coordinator.ai_enabled:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="ai_disabled")
        await coordinator.async_run_ai_check("manual")

    async def run_ai_ventilation_check(call: ServiceCall) -> None:
        await _require_admin(hass, call)  # the check costs money
        coordinator = _coordinator(hass)
        if not coordinator.vent_ai_active:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="ai_disabled")
        await coordinator.async_run_vent_check("manual")

    async def decide_heating_day(call: ServiceCall) -> None:
        await _require_admin(hass, call)  # changes the day and may ask the paid AI
        await _coordinator(hass).async_decide_heating_day("manual", call.data[ATTR_USE_AI])

    hass.services.async_register(
        DOMAIN, SERVICE_EXPORT, export_parameters, EXPORT_SCHEMA, SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, SERVICE_IMPORT, import_parameters, IMPORT_SCHEMA, SupportsResponse.OPTIONAL
    )
    hass.services.async_register(DOMAIN, SERVICE_RESET, reset_learned, RESET_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_AI_CHECK, run_ai_check, AI_CHECK_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_VENT_CHECK, run_ai_ventilation_check, AI_CHECK_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_DECIDE, decide_heating_day, DECIDE_SCHEMA)
