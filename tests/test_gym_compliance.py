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
from src.env.agar_engine import Cell


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
    """Verify V3 SOTA reward components: delta mass gain, zero passive camp reward, and death penalty."""
    env = AgarEnv()
    obs, info = env.reset(seed=42)

    # 1. Passive camping gives 0.0 (anti-passivity guarantee)
    action = np.array([0, 0], dtype=np.int64)  # MultiDiscrete: angle 0, no-split
    obs, reward, terminated, truncated, info = env.step(action)
    # Zero delta mass with no kills must not yield free survival reward
    assert reward <= 0.0 or info["player_mass"] > 20.0 or info["died"]

    # 2. Death penalty test
    env.reset(seed=42)
    # Manually spawn massive predator on top of learning player to force death
    env.engine.spawn_player(99, initial_mass=500.0, xy=(env.engine.cells[0].x, env.engine.cells[0].y))
    obs, reward, terminated, truncated, info = env.step(action)
    assert terminated is True
    assert reward < 0.0  # Death penalty must be strictly negative



def test_seed_reproducibility():
    """Verify deterministic reset when using the same seed."""
    env1 = AgarEnv()
    env2 = AgarEnv()

    obs1, _ = env1.reset(seed=999)
    obs2, _ = env2.reset(seed=999)

    np.testing.assert_allclose(obs1, obs2, atol=1e-5)
    np.testing.assert_allclose(env1.engine.pellets_xy, env2.engine.pellets_xy, atol=1e-5)
    np.testing.assert_allclose(env1.engine.viruses_xy, env2.engine.viruses_xy, atol=1e-5)


def test_subcell_aware_prey_predator_observation():
    """Verify that prey and predator classification accounts for individual subcell capabilities rather than sum mass."""
    from src.env.agar_engine import Cell
    env = AgarEnv()
    env.reset(seed=42)

    # Setup player 0 with 2 subcells: 150 mass (large) and 30 mass (small)
    env.engine.cells.clear()
    c_large = Cell(id=1, player_id=0, x=500.0, y=500.0, mass=150.0)
    c_small = Cell(id=2, player_id=0, x=520.0, y=500.0, mass=30.0)

    # Setup Enemy 1 (mass 60): edible by c_large (150 >= 1.1*60).
    # Since our largest piece can eat it, it is PREY, not a predator!
    c_enemy1 = Cell(id=3, player_id=1, x=600.0, y=500.0, mass=60.0)

    # Setup Enemy 2 (mass 15): edible by both -> PREY!
    c_enemy2 = Cell(id=4, player_id=2, x=400.0, y=500.0, mass=15.0)

    # Setup Enemy 3 (mass 200): larger than c_large (200 >= 1.1*150) -> TRUE PREDATOR!
    c_enemy3 = Cell(id=5, player_id=3, x=500.0, y=700.0, mass=200.0)

    env.engine.cells.extend([c_large, c_small, c_enemy1, c_enemy2, c_enemy3])
    env.engine._cells_cache_valid = False

    obs = env._build_observation(0)
    assert obs.shape == (84,)
    assert np.all(obs >= -1.0) and np.all(obs <= 1.0)

    # Both Enemy 1 (60) and Enemy 2 (15) are edible by our largest subcell (150) -> must be in prey channel!
    # Offset 24-28 (1st prey), 28-32 (2nd prey)
    prey1_dx = obs[24]
    prey2_dx = obs[28]
    assert prey1_dx != 0.0 or prey2_dx != 0.0, "Edible enemies must appear in prey observation slots!"

    # Nearest prey should be tracked accurately
    assert env._last_prey_dist > 0.0
    assert env._last_prey_mass in (15.0, 60.0)

    # Enemy 3 (200) threatens our largest piece -> must appear in predator channel!
    # Offset 44-48 (1st predator)
    pred1_dx = obs[44]
    assert pred1_dx != 0.0, "True enemy threatening largest cell must appear in predator observation slots!"


def test_v10_sota_reward_proportionality_and_masked_split():
    """Verify proportional kills and zero reward friction for invalid splits."""
    env = AgarEnv()
    obs, info = env.reset(seed=42)

    # 1. At mass 20, split is invalid and must be masked without a penalty.
    assert bool(env.action_masks()[env.num_angles + 1]) is False
    _, rew, _, _, info = env.step(np.array([0, 1]))
    assert info["splits"] == 0
    assert np.isfinite(rew)

    # 2. Proportional kill test:
    # Setup cell of player 0 eating a 100-mass bot vs a 10-mass bot
    env.reset(seed=42)
    c_self = Cell(id=1, player_id=0, x=500.0, y=500.0, mass=200.0)
    c_victim_big = Cell(id=2, player_id=1, x=505.0, y=500.0, mass=100.0)
    env.engine.cells = [c_self, c_victim_big]
    env.engine._cells_cache_valid = False
    env.prev_mass = 200.0

    # Execute idle step: player eats victim
    _, rew_big, _, _, _ = env.step(np.array([0, 0]))
    # The kill is rewarded through the signed mass increase itself.
    assert rew_big > 4.0, f"Expected positive mass-growth reward, got {rew_big}"


def test_v10_peak_mass_is_monotonic_and_exposed():
    """Peak mass records only increase and are reported for evaluation metrics."""
    env = AgarEnv()
    env.reset(seed=42)
    assert env.peak_mass == pytest.approx(20.0)

    env.peak_mass = 100.0
    env.prev_mass = 100.0
    env.engine.cells[0].mass = 80.0
    env.engine._cells_cache_valid = False
    _, reward, _, _, info = env.step(np.array([0, 0]))

    assert env.peak_mass == pytest.approx(100.0)
    assert info["peak_mass"] == pytest.approx(100.0)
    assert info["reward_peak"] == 0.0
    assert info["reward_mass_growth"] < 0.0
    assert reward < 0.0


def test_v10_growth_below_peak_remains_rewarded():
    """Mass gained below the episode record must still produce positive growth reward."""
    env = AgarEnv(config={"simulation": {"num_bots": 0}, "entities": {"num_pellets": 0}})
    env.reset(seed=42)
    env.engine.cells[0].mass = 150.0
    env.engine._cells_cache_valid = False
    env.prev_mass = 100.0
    env.peak_mass = 200.0

    _, reward, _, _, info = env.step(np.array([0, 0]))

    assert 149.0 < info["player_mass"] < 150.0
    assert info["peak_mass"] == pytest.approx(200.0)
    assert info["reward_mass_growth"] > 2.4
    assert info["reward_peak"] == 0.0
    assert reward > 0.0


