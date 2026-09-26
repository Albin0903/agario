from types import SimpleNamespace

import pytest
import torch
import gymnasium as gym
import numpy as np
from gymnasium import spaces

from src.training.warm_start import transfer_policy_weights


class TinyPolicy(torch.nn.Module):
    def __init__(self, output_size=3):
        super().__init__()
        self.linear = torch.nn.Linear(4, output_size)


def _model(policy, action_space=None, num_timesteps=0):
    return SimpleNamespace(
        policy=policy,
        observation_space=spaces.Box(-1, 1, shape=(4,), dtype=float),
        action_space=action_space or spaces.Discrete(3),
        num_timesteps=num_timesteps,
    )


def test_transfer_copies_only_policy_weights_and_keeps_v11_counter():
    source = _model(TinyPolicy(), num_timesteps=18_798_064)
    target = _model(TinyPolicy(), num_timesteps=0)
    before = target.policy.linear.weight.detach().clone()

    result = transfer_policy_weights(source, target)

    assert result["tensors"] == 2
    assert torch.equal(source.policy.linear.weight, target.policy.linear.weight)
    assert not torch.equal(before, target.policy.linear.weight)
    assert target.num_timesteps == 0


def test_transfer_rejects_action_space_mismatch():
    source = _model(TinyPolicy())
    target = _model(TinyPolicy(), action_space=spaces.Discrete(4))
    with pytest.raises(ValueError, match="action spaces differ"):
        transfer_policy_weights(source, target)


def test_transfer_rejects_policy_shape_mismatch():
    with pytest.raises(ValueError, match="shape mismatch"):
        transfer_policy_weights(_model(TinyPolicy(3)), _model(TinyPolicy(4)))


class _TinyMaskedEnv(gym.Env):
    observation_space = spaces.Box(-1.0, 1.0, shape=(84,), dtype=np.float32)
    action_space = spaces.MultiDiscrete([24, 3])

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        return np.zeros(84, dtype=np.float32), {}

    def step(self, action):
        return np.zeros(84, dtype=np.float32), 0.0, False, False, {}

    def action_masks(self):
        return np.ones(27, dtype=np.bool_)


def test_v10_policy_archive_warm_starts_new_maskableppo_without_resume_state(tmp_path):
    pytest.importorskip("sb3_contrib")
    from sb3_contrib import MaskablePPO
    from stable_baselines3.common.vec_env import DummyVecEnv
    from src.training.policy_arch import LayerNormMaskablePolicy, build_policy_kwargs
    from src.training.warm_start import initialize_v11_from_v10

    env_factory = lambda: _TinyMaskedEnv()
    policy_kwargs = build_policy_kwargs({})
    source = MaskablePPO(
        LayerNormMaskablePolicy,
        DummyVecEnv([env_factory]),
        n_steps=8,
        batch_size=8,
        n_epochs=1,
        policy_kwargs=policy_kwargs,
        device="cpu",
        verbose=0,
    )
    source.learn(total_timesteps=8)
    assert source.policy.optimizer.state
    checkpoint = tmp_path / "synthetic_v10.zip"
    source.save(checkpoint)

    target = MaskablePPO(
        LayerNormMaskablePolicy,
        DummyVecEnv([env_factory]),
        n_steps=8,
        batch_size=8,
        n_epochs=1,
        policy_kwargs=policy_kwargs,
        device="cpu",
        verbose=0,
    )
    result = initialize_v11_from_v10(str(checkpoint), target)

    assert result["source_num_timesteps"] == 8
    assert target.num_timesteps == 0
    assert not target.policy.optimizer.state
    for name, weight in source.policy.state_dict().items():
        torch.testing.assert_close(weight, target.policy.state_dict()[name])
    target.get_env().close()
    source.get_env().close()

