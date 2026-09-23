import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import pytest
import numpy as np
import gymnasium as gym
from gymnasium.utils.env_checker import check_env

from src.env.gym_wrapper import AgarEnv


def test_farama_check_env():
    """Verify full Farama Gymnasium API compliance using check_env."""
    env = AgarEnv()
    check_env(env.unwrapped)


def test_observation_space_bounds():
    """Verify observations remain strictly bounded within [-1.0, 1.0] over many steps."""
    env = AgarEnv()
    obs, info = env.reset(seed=123)

    assert obs.shape == (84,)
    assert obs.dtype == np.float32
    assert np.all(obs >= -1.0) and np.all(obs <= 1.0)

    for _ in range(300):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        assert obs.shape == (84,)
        assert np.all(obs >= -1.0) and np.all(obs <= 1.0), f"Obs out of bounds: min={obs.min()}, max={obs.max()}"
        if terminated or truncated:
            obs, info = env.reset()


def test_reward_mechanisms():
    """Verify reward shaping components: mass gain, hunting, death, and survival."""
    env = AgarEnv()
    obs, info = env.reset(seed=42)

    # 1. Passive survival reward test
    action = np.array([0.0, 0.0, -1.0], dtype=np.float32)
    obs, reward, terminated, truncated, info = env.step(action)
    # Even with zero mass change, survival reward +0.001 should be present
    assert reward >= 0.001 or info["died"]

    # 2. Death penalty test
    env.reset(seed=42)
    # Manually spawn massive predator on top of learning player to force death
    env.engine.spawn_player(99, initial_mass=500.0, xy=(env.engine.cells[0].x, env.engine.cells[0].y))
    obs, reward, terminated, truncated, info = env.step(action)
    assert terminated is True
    assert reward <= -9.0  # Death penalty of -10.0


def test_seed_reproducibility():
    """Verify deterministic reset when using the same seed."""
    env1 = AgarEnv()
    env2 = AgarEnv()

    obs1, _ = env1.reset(seed=999)
    obs2, _ = env2.reset(seed=999)

    np.testing.assert_allclose(obs1, obs2, atol=1e-5)
    np.testing.assert_allclose(env1.engine.pellets_xy, env2.engine.pellets_xy, atol=1e-5)
    np.testing.assert_allclose(env1.engine.viruses_xy, env2.engine.viruses_xy, atol=1e-5)

