"""
The retry budget through the public API (ADR 0102).

Before ADR 0102 every job created through POST /jobs had
max_retries = 0, so a reclaimed job always failed outright and
POST /jobs/{id}/retry could never requeue it.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.domain.entities.job import Job
from app.domain.entities.tenant import DEFAULT_TENANT_ID
from app.domain.enums.job_status import JobStatus
from app.domain.value_objects.job_id import JobId
from app.domain.value_objects.resource_requirements import (
    ResourceRequirements,
)
from app.presentation.api import app

client = TestClient(app)


def _failed_job(max_retries: int, retry_count: int) -> Job:
    """
    Save a FAILED job straight into the repository the API reads,
    as reconciliation leaves one after it reclaims the job.
    """
    from app.presentation.dependencies import _job_repository

    job = Job(
        id=JobId.new(),
        resources=ResourceRequirements(
            cpu_cores=1,
            memory_mib=512,
            vram_mib=0,
        ),
        tenant_id=DEFAULT_TENANT_ID,
        max_retries=max_retries,
        retry_count=retry_count,
        status=JobStatus.FAILED,
    )
    _job_repository.save(job)
    return job


def test_create_job_stores_the_retry_budget() -> None:
    created = client.post(
        "/jobs",
        json={
            "cpu_cores": 1,
            "memory_mib": 512,
            "vram_mib": 0,
            "max_retries": 2,
        },
    )

    assert created.status_code == 201

    body = client.get(f"/jobs/{created.json()['id']}").json()

    assert body["max_retries"] == 2
    assert body["retry_count"] == 0


def test_create_job_without_a_budget_keeps_zero() -> None:
    created = client.post(
        "/jobs",
        json={
            "cpu_cores": 1,
            "memory_mib": 512,
            "vram_mib": 0,
        },
    )

    body = client.get(f"/jobs/{created.json()['id']}").json()

    assert body["max_retries"] == 0
    assert body["retry_count"] == 0


def test_create_job_rejects_a_budget_above_the_limit() -> None:
    response = client.post(
        "/jobs",
        json={
            "cpu_cores": 1,
            "memory_mib": 512,
            "vram_mib": 0,
            "max_retries": 11,
        },
    )

    assert response.status_code == 422


def test_retry_requeues_a_failed_job_with_budget_left() -> None:
    job = _failed_job(max_retries=1, retry_count=0)

    response = client.post(f"/jobs/{job.id}/retry")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "QUEUED"
    assert body["retry_count"] == 1
    assert body["max_retries"] == 1


def test_retry_of_an_exhausted_job_shows_why_nothing_changed() -> None:
    """
    The route still answers 200 and leaves the job FAILED, as it
    always has. The two budget fields now say why.
    """
    job = _failed_job(max_retries=1, retry_count=1)

    response = client.post(f"/jobs/{job.id}/retry")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["retry_count"] == body["max_retries"] == 1
