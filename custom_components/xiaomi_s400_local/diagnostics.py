"""Redacted diagnostics for Xiaomi S400 Local."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from . import S400ConfigEntry
from .const import CONF_BINDKEY, CONF_TOKEN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: S400ConfigEntry
) -> dict:
    """Return state while replacing long-lived secrets."""
    coordinator = entry.runtime_data
    config = dict(entry.data)
    if config.get(CONF_BINDKEY):
        config[CONF_BINDKEY] = "**REDACTED**"
    if config.get(CONF_TOKEN):
        config[CONF_TOKEN] = "**REDACTED**"
    return {
        "config": config,
        "values": {
            key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in coordinator.values.items()
        },
        "last_error": coordinator.last_error,
        "debug_events": list(getattr(coordinator, "debug_events", [])),
    }
