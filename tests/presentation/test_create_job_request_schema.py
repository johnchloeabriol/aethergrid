from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.presentation.schemas.create_job_request import (
    MAX_RETRIES_LIMIT,
    CreateJobRequest,
)


def test_create_job_request_allows_missing_command() -> None:
    """
    command is optional. Omitting it entirely must still
    produce a valid request, matching every job created
    before ADR 0028 existed.
    """
    request = CreateJobRequest(
        cpu_cores=1,
        memory_mib=512,
        vram_mib=0,
    )

    assert request.command is None


def test_create_job_request_accepts_valid_command() -> None:
    request = CreateJobRequest(
        cpu_cores=1,
        memory_mib=512,
        vram_mib=0,
        command=["python", "train.py", "--epochs", "5"],
    )

    assert request.command == [
        "python",
        "train.py",
        "--epochs",
        "5",
    ]


def test_create_job_request_rejects_empty_command_list() -> None:
    """
    An empty command list would reach JobExecutionService's
    subprocess.Popen call with no argv at all, failing
    late and unhelpfully deep in a worker's execution loop
    instead of at request time. See ADR 0028.
    """
    with pytest.raises(ValidationError):
        CreateJobRequest(
            cpu_cores=1,
            memory_mib=512,
            vram_mib=0,
            command=[],
        )


def test_create_job_request_rejects_blank_command_argument() -> None:
    with pytest.raises(ValidationError):
        CreateJobRequest(
            cpu_cores=1,
            memory_mib=512,
            vram_mib=0,
            command=["python", "  ", "train.py"],
        )


def test_create_job_request_defaults_max_retries_to_zero() -> None:
    """
    Omitting max_retries keeps the budget every job had before
    the field existed (ADR 0102).
    """
    request = CreateJobRequest(
        cpu_cores=1,
        memory_mib=512,
        vram_mib=0,
    )

    assert request.max_retries == 0


def test_create_job_request_accepts_max_retries_within_limit() -> None:
    request = CreateJobRequest(
        cpu_cores=1,
        memory_mib=512,
        vram_mib=0,
        max_retries=MAX_RETRIES_LIMIT,
    )

    assert request.max_retries == MAX_RETRIES_LIMIT


@pytest.mark.parametrize("value", [-1, MAX_RETRIES_LIMIT + 1])
def test_create_job_request_rejects_max_retries_out_of_range(
    value: int,
) -> None:
    with pytest.raises(ValidationError):
        CreateJobRequest(
            cpu_cores=1,
            memory_mib=512,
            vram_mib=0,
            max_retries=value,
        )
