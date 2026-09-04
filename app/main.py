"""FastAPI application entrypoint for the appointment booking service.

Serves both the JSON REST API and a minimal HTML frontend used to
perform CRUD operations against physician appointment records.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import database
from app.schemas import Appointment, AppointmentCreate, AppointmentUpdate

APP_VERSION = os.getenv("APP_VERSION", "dev")
SERVICE_NAME = "appointment-service"

tags_metadata = [
    {
        "name": "health",
        "description": "Liveness / readiness probes.",
    },
    {
        "name": "appointments",
        "description": "CRUD operations for physician appointments.",
    },
]

app = FastAPI(
    title="Appointment Booking Service",
    description="Fullstack CRUD application for booking appointments with a physician. "
    "Persistence is provided by a Redis container.",
    version=APP_VERSION,
    openapi_tags=tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"], summary="Liveness probe")
def health() -> dict:
    """Simple liveness endpoint."""
    return {"status": "alive"}


@app.get("/ready", tags=["health"], summary="Readiness probe")
def ready() -> dict:
    """Readiness endpoint that verifies Redis connectivity."""
    return database.healthcheck()


@app.get(
    "/api/appointments",
    response_model=list[Appointment],
    tags=["appointments"],
    summary="List appointments",
)
def list_appointments(limit: int = 100) -> list[dict]:
    """Return the most recently created appointments."""
    return database.list_appointments(limit=limit)


@app.post(
    "/api/appointments",
    response_model=Appointment,
    status_code=status.HTTP_201_CREATED,
    tags=["appointments"],
    summary="Create an appointment",
)
def create_appointment(payload: AppointmentCreate) -> dict:
    """Create a new appointment with a physician."""
    appointment = Appointment(**payload.model_dump())
    return database.create_appointment(appointment.model_dump())


@app.get(
    "/api/appointments/{appointment_id}",
    response_model=Appointment,
    tags=["appointments"],
    summary="Get an appointment",
)
def get_appointment(appointment_id: str) -> dict:
    """Fetch a single appointment by id."""
    appointment = database.get_appointment(appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    return appointment


@app.put(
    "/api/appointments/{appointment_id}",
    response_model=Appointment,
    tags=["appointments"],
    summary="Update an appointment",
)
def update_appointment(appointment_id: str, payload: AppointmentUpdate) -> dict:
    """Partially update fields of an existing appointment."""
    fields = payload.model_dump(exclude_none=True)
    updated = database.update_appointment(appointment_id, fields)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    return updated


@app.delete(
    "/api/appointments/{appointment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["appointments"],
    summary="Delete an appointment",
)
def delete_appointment(appointment_id: str) -> Response:
    """Delete an appointment by id."""
    if not database.delete_appointment(appointment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
