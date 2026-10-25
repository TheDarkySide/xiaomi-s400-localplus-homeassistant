"""Bluetooth listener and state holder for Xiaomi S400 Local."""

from __future__ import annotations

import asyncio
from collections import deque
import logging
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
        self._cancel: CALLBACK_TYPE | None = None
        self._poll_task: Task[None] | None = None
        self._stopped = False
        self._last_raw_seen: bytes | None = None
        self._last_time_seen: float = 0.0
        self.last_error: str | None = None
        self.debug_events: deque[str] = deque(maxlen=120)

    def _log_event(self, msg: str) -> None:
        ts = datetime.now(UTC).strftime("%H:%M:%S.%f")[:-3]
        self.debug_events.append(f"[{ts}] {msg}")
        _LOGGER.warning("[S400 %s] %s", self.address, msg)

    def start(self) -> None:
        """Register passive/active Bluetooth callback without connectable=False filter."""
        self._stopped = False
        self._log_event("Coordinator start (PASSIVE FE95 mode, connectable=Any)")
        self._cancel = bluetooth.async_register_callback(
            self.hass,
            self._advertisement,
            BluetoothCallbackMatcher(
                address=self.address,
                service_data_uuid=MIBEACON_UUID,
            ),
            BluetoothScanningMode.ACTIVE,
        )
        self._poll_task = self.hass.async_create_task(
            self._poll_service_info_loop(), f"S400 adv poll {self.address}"
        )

    async def stop(self) -> None:
        """Remove the Bluetooth callback."""
        self._stopped = True
        if self._cancel:
            self._cancel()
            self._cancel = None
        if self._poll_task:
            self._poll_task.cancel()
            with suppress(CancelledError):
                await self._poll_task
            self._poll_task = None

    async def _poll_service_info_loop(self) -> None:
        """Poll habluetooth service_info every 0.4s so no FE95 frame is missed."""
        while not self._stopped:
            try:
                for conn in (True, False):
                    info = bluetooth.async_last_service_info(
                        self.hass, self.address, connectable=conn
                    )
                    if info is None:
                        continue
                    raw = info.service_data.get(MIBEACON_UUID)
                    if raw is None:
                        continue
                    info_time = getattr(info, "time", 0.0) or 0.0
                    if raw != self._last_raw_seen or (
                        info_time > self._last_time_seen and len(raw) > 11
                    ):
                        self._advertisement(info, BluetoothChange.ADVERTISEMENT)
            except Exception as err:
                self._log_event(f"Poll err: {err}")
            await asyncio.sleep(0.4)

    @callback
    def add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        self._listeners.add(listener)

        @callback
        def remove() -> None:
            self._listeners.discard(listener)

        return remove

    @callback
    def _advertisement(
        self, service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        raw = service_info.service_data.get(MIBEACON_UUID)
        if raw is None:
            return
        info_time = getattr(service_info, "time", 0.0) or 0.0
        if (
            raw == self._last_raw_seen
            and (info_time - self._last_time_seen) < 2.0
            and len(raw) == 11
        ):
            return
        self._last_raw_seen = raw
        self._last_time_seen = info_time
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
