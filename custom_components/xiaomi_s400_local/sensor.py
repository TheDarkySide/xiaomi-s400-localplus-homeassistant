"""Sensors exposed by Xiaomi S400 Local."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfMass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import S400ConfigEntry
from .coordinator import S400Coordinator
from .entity import S400Entity


@dataclass(frozen=True, kw_only=True)
class S400SensorDescription(SensorEntityDescription):
    """S400 sensor metadata."""


SENSORS = (
    S400SensorDescription(
        key="weight",
        translation_key="weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    S400SensorDescription(
        key="heart_rate",
        translation_key="heart_rate",
        icon="mdi:heart-pulse",
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    S400SensorDescription(
        key="impedance_low",
        translation_key="impedance_low",
        icon="mdi:omega",
        native_unit_of_measurement="Ω",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    S400SensorDescription(
        key="impedance_high",
        translation_key="impedance_high",
        icon="mdi:omega",
        native_unit_of_measurement="Ω",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    S400SensorDescription(
        key="profile_id",
        translation_key="profile_id",
        icon="mdi:account",
    ),
    S400SensorDescription(
        key="measurement_time",
        translation_key="measurement_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    S400SensorDescription(
        key="rssi",
        translation_key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: S400ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        S400Sensor(entry, coordinator, description) for description in SENSORS
    )


class S400Sensor(S400Entity, RestoreSensor):
    """One decoded measurement field."""

    entity_description: S400SensorDescription

    def __init__(
        self,
        entry: S400ConfigEntry,
        coordinator: S400Coordinator,
        description: S400SensorDescription,
    ) -> None:
        super().__init__(entry, coordinator, description.key)
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (restored_data := await self.async_get_last_sensor_data()) is not None:
            if (
                self.coordinator.values[self._key] is None
                and restored_data.native_value is not None
            ):
                self.coordinator.values[self._key] = restored_data.native_value
                if self._key == "weight":
                    self.coordinator.values["stabilized"] = True
        elif (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in ("unknown", "unavailable"):
                try:
                    if (
                        self.entity_description.device_class
                        == SensorDeviceClass.TIMESTAMP
                    ):
                        val = datetime.fromisoformat(last_state.state)
                    elif "." in last_state.state:
                        val = float(last_state.state)
                    else:
                        val = int(last_state.state)
                    if self.coordinator.values[self._key] is None:
                        self.coordinator.values[self._key] = val
                        if self._key == "weight":
                            self.coordinator.values["stabilized"] = True
                except Exception:
                    pass

    @property
    def native_value(self):
        return self.coordinator.values[self._key]
