"""V10 policy architecture: action masking, LayerNorm/RMSNorm, cosine LR.

Does not change the environment reward function. Split legality is enforced
by masking the split logit to -inf instead of waiting for the agent to learn it.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, Optional, Type, Union

import numpy as np
import torch
import torch.nn as nn
from gymnasium import spaces
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor

try:
    from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
except ImportError as exc:  # pragma: no cover - optional until requirements install
    MaskableActorCriticPolicy = None  # type: ignore[misc, assignment]
    _SB3_CONTRIB_IMPORT_ERROR = exc
else:
    _SB3_CONTRIB_IMPORT_ERROR = None


class RMSNorm(nn.Module):
    """RMSNorm with a learnable scale; used when torch.nn.RMSNorm is unavailable."""

    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        rms = x.pow(2).mean(dim=-1, keepdim=True).add(self.eps).rsqrt()
        return self.weight * x * rms


def make_norm(dim: int, norm_type: str = "layernorm") -> nn.Module:
    """Factory for LayerNorm or RMSNorm after a hidden width `dim`."""
    key = (norm_type or "layernorm").lower()
    if key == "rmsnorm":
        if hasattr(nn, "RMSNorm"):
            return nn.RMSNorm(dim)
        return RMSNorm(dim)
    return nn.LayerNorm(dim)


class LayerNormExtractor(BaseFeaturesExtractor):
    """Observation trunk: Linear(obs, 512) -> Norm(512) -> SiLU."""

    def __init__(
        self,
        observation_space: spaces.Space,
        features_dim: int = 512,
        norm_type: str = "layernorm",
    ):
        super().__init__(observation_space, features_dim)
        n_input = int(np.prod(observation_space.shape))
        self.net = nn.Sequential(
            nn.Linear(n_input, features_dim),
            make_norm(features_dim, norm_type),
            nn.SiLU(),
        )

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        return self.net(observations)


class LayerNormMlpExtractor(nn.Module):
    """Actor/critic MLPs with Norm after each hidden Linear (stabilizes self-play)."""

    def __init__(
        self,
        feature_dim: int,
        net_arch: Union[list, dict],
        activation_fn: Type[nn.Module],
        norm_type: str = "layernorm",
    ):
        super().__init__()
        if isinstance(net_arch, dict):
            pi_dims = list(net_arch.get("pi", []))
            vf_dims = list(net_arch.get("vf", []))
        else:
            pi_dims = list(net_arch)
            vf_dims = list(net_arch)

        self.policy_net = self._mlp(feature_dim, pi_dims, activation_fn, norm_type)
        self.value_net = self._mlp(feature_dim, vf_dims, activation_fn, norm_type)
        self.latent_dim_pi = pi_dims[-1] if pi_dims else feature_dim
        self.latent_dim_vf = vf_dims[-1] if vf_dims else feature_dim

    @staticmethod
    def _mlp(
        in_dim: int,
        hidden: list,
        activation_fn: Type[nn.Module],
        norm_type: str,
    ) -> nn.Sequential:
        layers: list = []
        last = in_dim
        for width in hidden:
            layers.append(nn.Linear(last, width))
            layers.append(make_norm(width, norm_type))
            layers.append(activation_fn())
            last = width
        return nn.Sequential(*layers)

    def forward(self, features: torch.Tensor):
        return self.forward_actor(features), self.forward_critic(features)

    def forward_actor(self, features: torch.Tensor) -> torch.Tensor:
        return self.policy_net(features)

    def forward_critic(self, features: torch.Tensor) -> torch.Tensor:
        return self.value_net(features)


if MaskableActorCriticPolicy is not None:

    class LayerNormMaskablePolicy(MaskableActorCriticPolicy):
        """Maskable actor-critic whose hidden layers are LayerNorm/RMSNorm MLPs."""

        def __init__(self, *args, **kwargs):
            self._norm_type = kwargs.pop("norm_type", "layernorm")
            super().__init__(*args, **kwargs)

        def _build_mlp_extractor(self) -> None:
            self.mlp_extractor = LayerNormMlpExtractor(
                self.features_dim,
                net_arch=self.net_arch,
                activation_fn=self.activation_fn,
                norm_type=self._norm_type,
            )

else:  # pragma: no cover

    class LayerNormMaskablePolicy(nn.Module):  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "sb3-contrib is required for LayerNormMaskablePolicy. "
                "Install with: pip install sb3-contrib"
            ) from _SB3_CONTRIB_IMPORT_ERROR


def agar_action_mask_fn(env) -> np.ndarray:
    """Top-level mask fn for ActionMasker (must be picklable by SubprocVecEnv)."""
    inner = getattr(env, "unwrapped", env)
    return inner.action_masks()


def wrap_action_masker(env):
    """Wrap a Gymnasium env so MaskablePPO can read MultiDiscrete action masks."""
    from sb3_contrib.common.wrappers import ActionMasker

    return ActionMasker(env, agar_action_mask_fn)


def make_cosine_annealing_lr(lr_start: float, lr_end: float) -> Callable[[float], float]:
    """SB3 schedule: progress_remaining goes from 1 (start) to 0 (end)."""

    def schedule(progress_remaining: float) -> float:
        cosine = 0.5 * (1.0 + math.cos(math.pi * (1.0 - float(progress_remaining))))
        return float(lr_end + (lr_start - lr_end) * cosine)

    return schedule


def build_lr_schedule(ppo_cfg: Dict[str, Any], lr_start: float) -> Union[float, Callable[[float], float]]:
    ppo = ppo_cfg.get("ppo", {}) if ppo_cfg else {}
    schedule_name = str(ppo.get("lr_schedule", "cosine")).lower()
    lr_end = float(ppo.get("learning_rate_end", 1e-5))
    if schedule_name in ("cosine", "cosine_annealing"):
        return make_cosine_annealing_lr(lr_start, lr_end)
    return lr_start


def build_policy_kwargs(ppo_cfg: Dict[str, Any]) -> Dict[str, Any]:
    policy_cfg = ppo_cfg.get("policy", {}) if ppo_cfg else {}
    cfg_net_arch = policy_cfg.get("net_arch", dict(pi=[512, 512, 512], vf=[512, 512, 512]))
    features_dim = int(policy_cfg.get("features_dim", 512))
    norm_type = str(policy_cfg.get("norm", "layernorm")).lower()
    return {
        "net_arch": cfg_net_arch,
        "activation_fn": torch.nn.SiLU,
        "norm_type": norm_type,
        "features_extractor_class": LayerNormExtractor,
        "features_extractor_kwargs": dict(features_dim=features_dim, norm_type=norm_type),
    }


def _v10_custom_objects() -> Dict[str, Any]:
    """Classes custom à injecter au chargement d'un checkpoint V10 MaskablePPO.

    SB3 sérialise la classe de politique par référence ; sans `custom_objects`,
    `MaskablePPO.load()` échoue avec `Policy must subclass
    MaskableActorCriticPolicy` dès que le checkpoint a été sauvé avec
    `LayerNormMaskablePolicy`.
    """
    objects: Dict[str, Any] = {
        "policy_class": LayerNormMaskablePolicy,
        "features_extractor_class": LayerNormExtractor,
    }
    try:
        from stable_baselines3.common.policies import ActorCriticPolicy  # noqa: F401
        from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy  # noqa: F401

        objects.setdefault("base_policy_class", MaskableActorCriticPolicy)
    except Exception:
        pass
    return objects


def load_trained_model(path: str, allow_legacy: bool = True, **kwargs):
    """Load MaskablePPO, optionally allowing legacy vanilla PPO checkpoints."""
    last_error: Optional[Exception] = None
    try:
        from sb3_contrib import MaskablePPO

        # D'abord avec les classes V10 (LayerNorm), sinon chargement standard.
        try:
            return MaskablePPO.load(path, custom_objects=_v10_custom_objects(), **kwargs)
        except Exception:
            return MaskablePPO.load(path, **kwargs)
    except Exception as exc:
        last_error = exc
    if not allow_legacy:
        raise RuntimeError(f"'{path}' is not a V10 MaskablePPO checkpoint") from last_error
    try:
        from stable_baselines3 import PPO

        return PPO.load(path, **kwargs)
    except Exception as exc:
        raise RuntimeError(
            f"Could not load '{path}' as MaskablePPO ({last_error}) or PPO ({exc})"
        ) from exc


def predict_action(
    model,
    obs: np.ndarray,
    action_masks: Optional[np.ndarray] = None,
    deterministic: bool = False,
) -> np.ndarray:
    """Predict with optional masks; ignores the kwarg on vanilla PPO policies."""
    if action_masks is not None:
        try:
            return model.predict(obs, deterministic=deterministic, action_masks=action_masks)[0]
        except TypeError:
            pass
    return model.predict(obs, deterministic=deterministic)[0]
