"""Redis-backed persistence layer for the appointment booking app.

Redis is used as the primary data store (as requested for simplicity).
Each appointment is stored as a JSON hash under ``appointments:<id>`` and
its id is tracked in a sorted set so we can list appointments ordered by
creation time.
"""

from __future__ import annotations

import json
import os
from typing import Any

import redis
from redis.exceptions import RedisError

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

APPOINTMENT_KEY_PREFIX = "appointments"
APPOINTMENT_INDEX_KEY = "appointments:index"

_redis_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    """Return a lazily-initialised Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD or None,
            decode_responses=True,
            socket_timeout=5,
        )
    return _redis_client


def _key(appointment_id: str) -> str:
    return f"{APPOINTMENT_KEY_PREFIX}:{appointment_id}"


def create_appointment(appointment: dict[str, Any]) -> dict[str, Any]:
    """Persist a new appointment and return it with its generated id."""
    appointment_id = appointment["id"]
    client = get_client()
    client.hset(_key(appointment_id), mapping=_flatten(appointment))
    client.zadd(APPOINTMENT_INDEX_KEY, {appointment_id: float(appointment["created_at"])})
    return get_appointment(appointment_id)


def get_appointment(appointment_id: str) -> dict[str, Any] | None:
    """Fetch a single appointment by id."""
    client = get_client()
    raw = client.hgetall(_key(appointment_id))
    if not raw:
        return None
    return _unflatten(raw)


def list_appointments(limit: int = 100) -> list[dict[str, Any]]:
    """Return appointments ordered by creation time (newest first)."""
    client = get_client()
    ids = client.zrevrange(APPOINTMENT_INDEX_KEY, 0, limit - 1)
    appointments = []
    for appointment_id in ids:
        item = get_appointment(appointment_id)
        if item is not None:
            appointments.append(item)
    return appointments


def update_appointment(appointment_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    """Partially update an appointment and return the updated record."""
    client = get_client()
    key = _key(appointment_id)
    if not client.exists(key):
        return None
    if "patient_name" in fields:
        client.hset(key, "patient_name", json.dumps(fields["patient_name"]))
    if "physician" in fields:
        client.hset(key, "physician", json.dumps(fields["physician"]))
    if "appointment_date" in fields:
        client.hset(key, "appointment_date", json.dumps(fields["appointment_date"]))
    if "time_slot" in fields:
        client.hset(key, "time_slot", json.dumps(fields["time_slot"]))
    if "status" in fields:
        client.hset(key, "status", json.dumps(fields["status"]))
    return get_appointment(appointment_id)


def delete_appointment(appointment_id: str) -> bool:
    """Delete an appointment and remove it from the index."""
    client = get_client()
    key = _key(appointment_id)
    if not client.exists(key):
        return False
    client.delete(key)
    client.zrem(APPOINTMENT_INDEX_KEY, appointment_id)
    return True


def healthcheck() -> dict[str, Any]:
    """Ping Redis and report connectivity status."""
    try:
        get_client().ping()
        return {"status": "ok"}
    except RedisError:
        return {"status": "unavailable"}


def _flatten(appointment: dict[str, Any]) -> dict[str, str]:
    """Encode an appointment dict into hash-compatible strings."""
    return {k: json.dumps(v) for k, v in appointment.items()}


def _unflatten(raw: dict[str, str]) -> dict[str, Any]:
    """Decode a Redis hash back into a plain dict."""
    return {k: json.loads(v) for k, v in raw.items()}
