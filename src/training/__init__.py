"""Training pipeline package.

Keep package imports lazy: importing a single training helper from inference
must not eagerly import SB3, TensorBoard, or the self-play training stack.
"""

from __future__ import annotations

from typing import Any

_EXPORTS = {
    "SelfPlayPool": ("src.training.self_play_pool", "SelfPlayPool"),
    "V11TrainingCallback": ("src.training.callbacks_v11", "V11TrainingCallback"),
    "LayerNormExtractor": ("src.training.policy_arch", "LayerNormExtractor"),
    "LayerNormMaskablePolicy": ("src.training.policy_arch", "LayerNormMaskablePolicy"),
    "make_cosine_annealing_lr": ("src.training.policy_arch", "make_cosine_annealing_lr"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load public helpers on demand while preserving package-level imports."""
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    from importlib import import_module

    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
