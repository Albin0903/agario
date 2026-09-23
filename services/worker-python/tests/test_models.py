"""Unit tests for core worker-python data models."""

import pytest
from pydantic import ValidationError

from worker_python.models import ColorSpec, DatasetSummary, TaskRequest, TaskResponse


def test_task_request_validation() -> None:
    """Verify that TaskRequest validates required action and allows optional payload."""
    req = TaskRequest(action="design.contrast", payload={"foreground": "#000000"})
    assert req.action == "design.contrast"
    assert req.payload["foreground"] == "#000000"


def test_task_request_rejects_empty_action() -> None:
    """Verify that an empty action raises a validation error."""
    with pytest.raises(ValidationError):
        TaskRequest(action="")


def test_color_spec_hex_parsing() -> None:
    """Verify parsing of 3-digit and 6-digit hex color representations."""
    white = ColorSpec.from_hex("#fff")
    assert white.r == 255 and white.g == 255 and white.b == 255
    assert white.to_hex() == "#ffffff"

    black = ColorSpec.from_hex("000000")
    assert black.r == 0 and black.g == 0 and black.b == 0
    assert black.to_hex() == "#000000"


def test_color_spec_rejects_invalid_hex() -> None:
    """Verify that invalid hex strings raise ValueError."""
    with pytest.raises(ValueError, match="Invalid hex color"):
        ColorSpec.from_hex("zzzzzz")


def test_dataset_summary_validation() -> None:
    """Verify valid DatasetSummary construction."""
    summary = DatasetSummary(
        count=10,
        mean=25.5,
        std_dev=3.2,
        min_value=12.0,
        max_value=40.0,
        median=25.0,
    )
    assert summary.count == 10
    assert summary.mean == 25.5


def test_task_response_defaults() -> None:
    """Verify TaskResponse default values."""
    res = TaskResponse(success=True, action="test.action", data={"result": 42})
    assert res.success is True
    assert res.error is None
    assert res.duration_ms == 0.0
