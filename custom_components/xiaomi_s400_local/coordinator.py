"""Bluetooth listener and state holder for Xiaomi S400 Local."""

from __future__ import annotations

import asyncio
from collections import deque
import logging
import time
from asyncio import CancelledError, Task
from collections.abc import Callable
from contextlib import suppress
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

from .const import MIBEACON_UUID
from .parser import AdvertisementError, parse_mibeacon

_LOGGER = logging.getLogger(__name__)


class S400Coordinator:
    """Convert advertisements into stable entity values."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        bindkey: bytes,
        token: bytes | None = None,
    ) -> None:
        self.hass = hass
        self.address = address.upper()
        self.bindkey = bindkey
        self.token = token
        self.values: dict[str, Any] = {
            "weight": None,
            "heart_rate": None,
            "impedance_low": None,
            "impedance_high": None,
            "profile_id": None,
            "stabilized": True,
            "measurement_time": None,
            "gatt_connected": False,
            "rssi": None,
            "last_seen": None,
            "product_id": None,
            "mibeacon_version": None,
        }
        self._listeners: set[Callable[[], None]] = set()
        self._cancel_callbacks: list[CALLBACK_TYPE] = []
        self._stopped = False
        self._last_raw_seen: bytes | None = None
        self._last_log_time: float = 0.0
        self.last_error: str | None = None
        self.debug_events: deque[str] = deque(maxlen=120)

    def _log_event(self, msg: str) -> None:
        ts = datetime.now(UTC).strftime("%H:%M:%S.%f")[:-3]
        self.debug_events.append(f"[{ts}] {msg}")
        _LOGGER.warning("[S400 %s] %s", self.address, msg)

    def start(self, entry: Any | None = None) -> None:
        """Register passive Bluetooth listener for every advertisement."""
        self._stopped = False
        self._log_event("Coordinator start (using async_register_advertisement_callback + active matcher)")
        self._cancel_callbacks = []

        # 1. Register for EVERY advertisement packet from this device (no deduplication)
        try:
            cancel_adv = bluetooth.async_register_advertisement_callback(
                self.hass,
                self._advertisement_raw,
                self.address,
            )
            self._cancel_callbacks.append(cancel_adv)
        except Exception as err:
            self._log_event(f"Error registering adv callback: {err}")

        # 2. Also register standard callbacks for both connectable and non-connectable
        for conn in (True, False):
            cancel = bluetooth.async_register_callback(
                self.hass,
                self._advertisement,
                BluetoothCallbackMatcher(
                    address=self.address,
                    connectable=conn,
                ),
                BluetoothScanningMode.ACTIVE,
            )
            self._cancel_callbacks.append(cancel)

    async def stop(self) -> None:
        """Remove the Bluetooth callbacks."""
        self._stopped = True
        if self._cancel_callbacks:
            for cancel in self._cancel_callbacks:
                cancel()
            self._cancel_callbacks.clear()

    @callback
    def add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        self._listeners.add(listener)

        @callback
        def remove() -> None:
            self._listeners.discard(listener)

        return remove

    @callback
    def _advertisement_raw(self, service_info: BluetoothServiceInfoBleak) -> None:
        """Called directly by habluetooth on EVERY advertisement without deduplication."""
        self._advertisement(service_info, BluetoothChange.ADVERTISEMENT)

    @callback
    def _advertisement(
        self, service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        raw = service_info.service_data.get(MIBEACON_UUID)
        if raw is None:
            return
        now = time.monotonic()
        if (
            len(raw) == 11
            and raw == self._last_raw_seen
            and (now - self._last_log_time) < 10.0
        ):
            self.values["rssi"] = service_info.rssi
            self.values["last_seen"] = datetime.now(UTC)
            return

        self._last_raw_seen = raw
        self._last_log_time = now
        self._log_event(
            f"ADV rssi={service_info.rssi} src={service_info.source} conn={service_info.connectable} len={len(raw)} hex={raw.hex()}"
        )
        try:
            update = parse_mibeacon(self.address, raw, self.bindkey)
        except AdvertisementError as err:
            self.last_error = str(err)
            self._log_event(f"FE95 err: {err}")
            return
        self.last_error = None
        parsed = asdict(update)
        if len(raw) > 11 or any(
            parsed.get(k) is not None
            for k in ("weight", "heart_rate", "impedance_low", "impedance_high")
        ):
            self._log_event(f"FE95 decoded: {parsed}")
        if parsed["weight"] is not None and parsed["stabilized"] is False:
            self._start_measurement()
        for key in (
            "weight",
            "heart_rate",
            "impedance_low",
            "impedance_high",
            "profile_id",
            "stabilized",
        ):
            if parsed[key] is not None:
                self.values[key] = parsed[key]
        if (
            update.stabilized
            and update.timestamp is not None
            and update.timestamp >= 1_577_836_800
        ):
            with suppress(OverflowError, OSError, ValueError):
                self.values["measurement_time"] = datetime.fromtimestamp(
                    update.timestamp, UTC
                )
        self.values.update(
            rssi=service_info.rssi,
            last_seen=datetime.now(UTC),
            product_id=f"0x{update.product_id:04X}",
            mibeacon_version=update.frame_version,
        )
        self._notify_listeners()

    @callback
    def _start_measurement(self) -> None:
        """Clear fields from the previous stable reading when weighing restarts."""
        if not self.values["stabilized"]:
            return
        for key in (
            "heart_rate",
            "impedance_low",
            "impedance_high",
            "profile_id",
            "measurement_time",
        ):
            self.values[key] = None
        self.values["stabilized"] = False

    @callback
    def _notify_listeners(self) -> None:
        for listener in tuple(self._listeners):
            listener()
