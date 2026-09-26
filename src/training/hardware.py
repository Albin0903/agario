"""Host CPU budget detection shared by the trainer and Colab profile."""

from __future__ import annotations

import math
import os
from pathlib import Path


def effective_cpu_count() -> int:
    """Return CPUs available to this process, respecting affinity/cgroup limits."""
    allowed = os.cpu_count() or 1
    if hasattr(os, "sched_getaffinity"):
        try:
            allowed = min(allowed, max(1, len(os.sched_getaffinity(0))))
        except OSError:
            pass

    # cgroup v2 CPU quota (Colab and many containers).
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()[:2]
        if quota != "max":
            allowed = min(allowed, max(1, math.ceil(int(quota) / int(period))))
    except (OSError, ValueError, ZeroDivisionError):
        pass

    # cgroup v1 fallback.
    try:
        quota = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read_text())
        period = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read_text())
        if quota > 0:
            allowed = min(allowed, max(1, math.ceil(quota / period)))
    except (OSError, ValueError, ZeroDivisionError):
        pass
    return max(1, allowed)


def configure_worker_thread_limits() -> None:
    """Prevent each CPU env worker from creating nested BLAS/OpenMP pools."""
    for name in (
        "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS", "NUMBA_NUM_THREADS",
    ):
        os.environ[name] = "1"
    # Training/replay use JSONL logs, never the optional event writer.
    os.environ["AGARIO_DISABLE_TENSORBOARD"] = "1"
