"""API integration tests using FastAPI's TestClient.

These tests run against the real application but swap the Redis client
for a fake in-memory implementation so they pass without a Redis server.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app


class FakeRedis:
    """Minimal in-memory stand-in for the redis client."""

    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, str]] = {}
        self._zset: dict[str, dict[str, float]] = {}

    def hset(self, key: str, *args, **kwargs) -> None:
        if "mapping" in kwargs:
            mapping = kwargs["mapping"]
        elif len(args) == 2 and isinstance(args[1], dict):
            mapping = args[1]
        elif len(args) == 2:
            mapping = {args[0]: args[1]}
        else:
            mapping = {}
        self._hashes.setdefault(key, {}).update(mapping)

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self._hashes.get(key, {}))

    def exists(self, key: str) -> int:
        return 1 if key in self._hashes else 0

    def delete(self, key: str) -> int:
        return 1 if self._hashes.pop(key, None) is not None else 0

    def zadd(self, key: str, mapping: dict[str, float]) -> None:
        self._zset.setdefault(key, {}).update(mapping)

    def zrevrange(self, key: str, start: int, end: int) -> list[str]:
        items = sorted(self._zset.get(key, {}).items(), key=lambda kv: kv[1], reverse=True)
        return [item[0] for item in items[start : end + 1]]

    def zrem(self, key: str, member: str) -> int:
        return 1 if self._zset.get(key, {}).pop(member, None) is not None else 0

    def ping(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def fake_redis() -> FakeRedis:
    """Replace the real Redis client with an in-memory fake."""
    fake = FakeRedis()
    with patch.object(database, "_redis_client", fake):
        yield fake


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def sample_payload() -> dict:
    return {
        "patient_name": "Jane Doe",
        "physician": "Dr. Smith",
        "appointment_date": "2026-09-15",
        "time_slot": "09:30",
        "reason": "Annual physical",
    }


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_ready_endpoint(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_appointment(client: TestClient) -> None:
    response = client.post("/api/appointments", json=sample_payload())
    assert response.status_code == 201
    data = response.json()
    assert data["patient_name"] == "Jane Doe"
    assert data["physician"] == "Dr. Smith"
    assert data["status"] == "scheduled"
    assert data["id"]


def test_get_appointment(client: TestClient) -> None:
    created = client.post("/api/appointments", json=sample_payload()).json()
    response = client.get(f"/api/appointments/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_missing_appointment_returns_404(client: TestClient) -> None:
    response = client.get("/api/appointments/does-not-exist")
    assert response.status_code == 404


def test_list_appointments(client: TestClient) -> None:
    client.post("/api/appointments", json=sample_payload())
    client.post("/api/appointments", json={**sample_payload(), "patient_name": "John Roe"})
    response = client.get("/api/appointments")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_update_appointment_status(client: TestClient) -> None:
    created = client.post("/api/appointments", json=sample_payload()).json()
    response = client.put(f"/api/appointments/{created['id']}", json={"status": "completed"})
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_update_missing_appointment_returns_404(client: TestClient) -> None:
    response = client.put("/api/appointments/nope", json={"status": "cancelled"})
    assert response.status_code == 404


def test_delete_appointment(client: TestClient) -> None:
    created = client.post("/api/appointments", json=sample_payload()).json()
    response = client.delete(f"/api/appointments/{created['id']}")
    assert response.status_code == 204
    assert client.get(f"/api/appointments/{created['id']}").status_code == 404


def test_delete_missing_appointment_returns_404(client: TestClient) -> None:
    response = client.delete("/api/appointments/nope")
    assert response.status_code == 404


def test_invalid_date_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/appointments", json={**sample_payload(), "appointment_date": "not-a-date"}
    )
    assert response.status_code == 422


def test_invalid_status_is_rejected(client: TestClient) -> None:
    created = client.post("/api/appointments", json=sample_payload()).json()
    response = client.put(f"/api/appointments/{created['id']}", json={"status": "bogus"})
    assert response.status_code == 422
