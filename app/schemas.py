"""Pydantic models (schemas) for the appointment booking API."""

from __future__ import annotations

import time
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AppointmentCreate(BaseModel):
    """Payload used to create an appointment."""

    patient_name: str = Field(
        ..., min_length=1, max_length=100, json_schema_extra={"example": "Jane Doe"}
    )
    physician: str = Field(
        ..., min_length=1, max_length=100, json_schema_extra={"example": "Dr. Smith"}
    )
    appointment_date: str = Field(
        ..., pattern=r"^\d{4}-\d{2}-\d{2}$", json_schema_extra={"example": "2026-09-15"}
    )
    time_slot: str = Field(..., min_length=1, max_length=20, json_schema_extra={"example": "09:30"})
    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        json_schema_extra={"example": "Annual physical"},
    )


class AppointmentUpdate(BaseModel):
    """Payload used to partially update an appointment."""

    patient_name: str | None = None
    physician: str | None = None
    appointment_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    time_slot: str | None = None
    status: str | None = Field(
        default=None,
        pattern=r"^(scheduled|completed|cancelled)$",
        json_schema_extra={"example": "scheduled"},
    )


class Appointment(AppointmentCreate):
    """Full appointment representation returned by the API."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "scheduled"
    created_at: float = Field(default_factory=time.time)

    model_config = ConfigDict(
        json_encoders={uuid.UUID: str},
        validate_assignment=True,
    )
