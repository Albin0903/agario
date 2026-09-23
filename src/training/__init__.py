"""Training pipeline package for AGAR-RL."""

from src.training.self_play_pool import SelfPlayPool
from src.training.callbacks import SelfPlayCallback

__all__ = ["SelfPlayPool", "SelfPlayCallback"]

