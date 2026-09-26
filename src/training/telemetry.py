"""Small shared telemetry helpers for training and fixed-seed evaluation."""

from __future__ import annotations

from collections import deque


class SplitKillAttributor:
    """Credit a split decision when it is followed by a kill within a horizon.

    Each kill credits the most recent still-open split. A split is labelled
    without a kill after ``horizon`` decisions or at episode end. This is a
    behavioral diagnostic, not a reward term.
    """

    def __init__(self, horizon: int = 30):
        if horizon < 1:
            raise ValueError("horizon must be positive")
        self.horizon = int(horizon)
        self.step = 0
        self.pending: deque[int] = deque()

    def observe(self, split_requested: bool, kills: int, done: bool = False) -> tuple[int, int]:
        now = self.step
        self.step += 1
        without_kill = 0
        while self.pending and now - self.pending[0] > self.horizon:
            self.pending.popleft()
            without_kill += 1
        if split_requested:
            self.pending.append(now)

        with_kill = 0
        if kills > 0 and self.pending:
            self.pending.pop()
            with_kill = 1

        if done:
            without_kill += len(self.pending)
            self.pending.clear()
            self.step = 0
        return with_kill, without_kill

    def reset(self) -> int:
        """Close pending splits as unsuccessful and reset episode time."""
        unresolved = len(self.pending)
        self.pending.clear()
        self.step = 0
        return unresolved
