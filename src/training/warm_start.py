"""Strict V10-to-V11 policy weight transfer.

This is a warm start, not a training resume: only actor/critic policy weights
are copied. V11 creates its own optimizer, timestep counter, schedules,
normalization statistics, and self-play league.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def transfer_policy_weights(source_model: Any, target_model: Any) -> dict[str, int]:
    """Copy a compatible policy state dict, rejecting every shape/key mismatch."""
    if source_model.observation_space != target_model.observation_space:
        raise ValueError("V10 and V11 observation spaces differ; policy transfer is unsafe")
    if source_model.action_space != target_model.action_space:
        raise ValueError("V10 and V11 action spaces differ; policy transfer is unsafe")

    source_state = source_model.policy.state_dict()
    target_state = target_model.policy.state_dict()
    if source_state.keys() != target_state.keys():
        missing = sorted(source_state.keys() - target_state.keys())
        extra = sorted(target_state.keys() - source_state.keys())
        raise ValueError(f"Policy structure mismatch (missing={missing}, extra={extra})")

    mismatched = [
        (key, tuple(source_state[key].shape), tuple(target_state[key].shape))
        for key in source_state
        if source_state[key].shape != target_state[key].shape
    ]
    if mismatched:
        raise ValueError(f"Policy tensor shape mismatch: {mismatched}")

    target_model.policy.load_state_dict(source_state, strict=True)
    return {
        "tensors": len(source_state),
        "parameters": sum(t.numel() for t in source_state.values()),
    }


def initialize_v11_from_v10(checkpoint_path: str, target_model: Any, device: str = "cpu") -> dict[str, Any]:
    """Load a V10 MaskablePPO checkpoint and transfer policy weights only."""
    path = Path(checkpoint_path)
    if not path.is_file() or path.suffix.lower() != ".zip":
        raise FileNotFoundError(f"Expected a V10 .zip checkpoint file, got: {path}")

    from sb3_contrib import MaskablePPO
    from src.training.policy_arch import load_trained_model

    source_model = load_trained_model(str(path), device=device)
    if not isinstance(source_model, MaskablePPO):
        raise TypeError("V11 initialization accepts MaskablePPO checkpoints only")

    copied = transfer_policy_weights(source_model, target_model)
    return {
        "source_checkpoint": str(path.resolve()),
        "source_num_timesteps": int(source_model.num_timesteps),
        **copied,
    }
