"""Data processing handler performing numeric transformations, aggregations, and summaries."""

import math
from typing import Any

from worker_python.models import DatasetSummary


class DataHandler:
    """Handler executing dataset summarization, normalization, and filtering."""

    @staticmethod
    def summarize(values: list[float]) -> DatasetSummary:
        """Calculate descriptive statistics for a list of numeric values."""
        if not values:
            raise ValueError("Cannot summarize empty dataset")

        n = len(values)
        sorted_vals = sorted(values)
        mean = sum(values) / n

        variance = sum((x - mean) ** 2 for x in values) / n
        std_dev = math.sqrt(variance)

        if n % 2 == 1:
            median = sorted_vals[n // 2]
        else:
            median = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0

        return DatasetSummary(
            count=n,
            mean=round(mean, 4),
            std_dev=round(std_dev, 4),
            min_value=round(sorted_vals[0], 4),
            max_value=round(sorted_vals[-1], 4),
            median=round(median, 4),
        )

    @staticmethod
    def normalize_minmax(values: list[float]) -> list[float]:
        """Scale values linearly between 0.0 and 1.0."""
        if not values:
            return []
        min_v = min(values)
        max_v = max(values)
        if math.isclose(min_v, max_v):
            return [0.5 for _ in values]
        span = max_v - min_v
        return [round((x - min_v) / span, 4) for x in values]

    @staticmethod
    def filter_records(
        records: list[dict[str, Any]],
        field_name: str,
        min_value: float,
    ) -> list[dict[str, Any]]:
        """Filter a collection of record dictionaries by a numeric attribute threshold."""
        return [
            r
            for r in records
            if isinstance(r.get(field_name), int | float) and float(r[field_name]) >= min_value
        ]
