"""Unit tests for TaskPipeline registration and execution."""

from worker_python.models import TaskRequest
from worker_python.pipeline import TaskPipeline


def test_pipeline_executes_registered_design_contrast() -> None:
    """Verify end-to-end execution of design.contrast action through pipeline."""
    pipeline = TaskPipeline()
    req = TaskRequest(
        action="design.contrast",
        payload={"foreground": "#000000", "background": "#ffffff"},
    )
    res = pipeline.execute(req)

    assert res.success is True
    assert res.action == "design.contrast"
    assert res.data["wcag_ratio"] == 21.0
    assert res.error is None
    assert res.duration_ms >= 0.0


def test_pipeline_executes_registered_data_summarize() -> None:
    """Verify execution of data.summarize action through pipeline."""
    pipeline = TaskPipeline()
    req = TaskRequest(
        action="data.summarize",
        payload={"values": [1.0, 2.0, 3.0, 4.0, 5.0]},
    )
    res = pipeline.execute(req)

    assert res.success is True
    assert res.data["mean"] == 3.0
    assert res.data["count"] == 5


def test_pipeline_handles_unrecognized_action() -> None:
    """Verify that unrecognized action returns success=False without unhandled exception."""
    pipeline = TaskPipeline()
    req = TaskRequest(action="nonexistent.action", payload={})
    res = pipeline.execute(req)

    assert res.success is False
    assert "Unrecognized action" in str(res.error)


def test_pipeline_custom_handler_registration() -> None:
    """Verify dynamic registration of custom project-specific action handler."""
    pipeline = TaskPipeline()
    pipeline.register("custom.multiplier", lambda p: {"result": p.get("x", 0) * 2})

    req = TaskRequest(action="custom.multiplier", payload={"x": 21})
    res = pipeline.execute(req)

    assert res.success is True
    assert res.data["result"] == 42
