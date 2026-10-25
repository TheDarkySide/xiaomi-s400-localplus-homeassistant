"""Redacted diagnostics for Xiaomi S400 Local."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from . import S400ConfigEntry
from .const import CONF_BINDKEY, CONF_TOKEN, MIBEACON_UUID


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

    bt_info_conn = bluetooth.async_last_service_info(hass, coordinator.address, connectable=True)
    bt_info_nonconn = bluetooth.async_last_service_info(hass, coordinator.address, connectable=False)

    def _fmt_info(info):
        if info is None:
            return None
        raw = info.service_data.get(MIBEACON_UUID)
        return {
            "address": info.address,
            "source": info.source,
            "rssi": info.rssi,
            "time": getattr(info, "time", None),
            "connectable": info.connectable,
            "mibeacon_len": len(raw) if raw else None,
            "mibeacon_hex": raw.hex() if raw else None,
            "all_service_uuids": list(info.service_data.keys()),
        }

    return {
        "config": config,
        "values": {
            key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in coordinator.values.items()
        },
        "last_error": coordinator.last_error,
        "debug_events": list(getattr(coordinator, "debug_events", [])),
        "bt_diagnostics": {
            "scanner_count_conn": bluetooth.async_scanner_count(hass, connectable=True),
            "scanner_count_nonconn": bluetooth.async_scanner_count(hass, connectable=False),
            "last_service_info_conn": _fmt_info(bt_info_conn),
            "last_service_info_nonconn": _fmt_info(bt_info_nonconn),
            "poll_task_status": str(coordinator._poll_task),
            "stopped": coordinator._stopped,
            "last_raw_seen": coordinator._last_raw_seen.hex() if coordinator._last_raw_seen else None,
            "last_time_seen": coordinator._last_time_seen,
        }
    }
