"""Unit tests for DataHandler statistical summaries and normalization."""

import pytest

from worker_python.handlers.data import DataHandler


def test_summarize_odd_length_list() -> None:
    """Verify statistical summary on odd-length dataset."""
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    summary = DataHandler.summarize(values)
    assert summary.count == 5
    assert summary.mean == 30.0
    assert summary.median == 30.0
    assert summary.min_value == 10.0
    assert summary.max_value == 50.0


def test_summarize_even_length_list() -> None:
    """Verify median calculation on even-length dataset."""
    values = [10.0, 20.0, 30.0, 40.0]
    summary = DataHandler.summarize(values)
    assert summary.count == 4
    assert summary.mean == 25.0
    assert summary.median == 25.0


def test_summarize_empty_list_raises_error() -> None:
    """Verify ValueError on empty list input."""
    with pytest.raises(ValueError, match="Cannot summarize empty dataset"):
        DataHandler.summarize([])


def test_normalize_minmax() -> None:
    """Verify min-max normalization scales to [0.0, 1.0]."""
    values = [0.0, 50.0, 100.0]
    normalized = DataHandler.normalize_minmax(values)
    assert normalized == [0.0, 0.5, 1.0]


def test_filter_records() -> None:
    """Verify record filtering based on numeric attribute threshold."""
    records = [
        {"id": "a", "score": 85},
        {"id": "b", "score": 40},
        {"id": "c", "score": 92},
        {"id": "d", "score": "invalid"},
    ]
    filtered = DataHandler.filter_records(records, "score", 80.0)
    assert len(filtered) == 2
    assert filtered[0]["id"] == "a"
    assert filtered[1]["id"] == "c"
