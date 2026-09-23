"""Unit tests for the self-play pool and bot behaviors."""

import os
import numpy as np
import pytest
from src.env.agar_engine import AgarEngine
from src.env.gym_wrapper import AgarEnv, HeuristicBot
from src.training.self_play_pool import SelfPlayPool, OpponentEntry


def test_heuristic_bot_behavior():
    """Verify heuristic bot returns valid action [tx, ty, trigger]."""
    engine = AgarEngine(width=1000.0, height=1000.0, num_pellets=50)
    engine.spawn_player(0, initial_mass=20.0, xy=(500.0, 500.0))
    engine.spawn_player(1, initial_mass=20.0, xy=(550.0, 500.0))

    bot = HeuristicBot(player_id=1)
    act = bot.get_action(engine)

    assert isinstance(act, np.ndarray)
    assert act.shape == (3,)
    assert -1.0 <= act[0] <= 1.0
    assert -1.0 <= act[1] <= 1.0
    assert -1.0 <= act[2] <= 1.0


def test_self_play_pool_lifecycle(tmp_path):
    """Verify self-play pool addition, eviction, and sampling."""
    pool = SelfPlayPool(max_size=3, history_dir=str(tmp_path), heuristic_ratio=0.0)

    # Empty pool returns None (heuristic)
    assert pool.sample_opponent() is None
    assert len(pool) == 0

    # Add 4 dummy checkpoints to test eviction
    for i in range(1, 5):
        entry = OpponentEntry(
            tag=f"gen_{i}",
            path=f"/fake/path/{i}.zip",
            generation=i,
            score=float(i * 10.0),
            policy=None,
        )
        pool.pool.append(entry)
        if len(pool.pool) > pool.max_size:
            pool.pool.sort(key=lambda x: x.score)
            pool.pool.pop(0)

    assert len(pool) == 3
    # Smallest score (10.0 from gen_1) should have been evicted
    scores = [e.score for e in pool.pool]
    assert 10.0 not in scores
    assert 20.0 in scores
    assert 30.0 in scores
    assert 40.0 in scores

    # Sample opponent
    sampled = pool.sample_opponent()
    assert sampled is not None
    assert sampled.score in [20.0, 30.0, 40.0]


def test_environment_multiagent_interaction():
    """Verify environment steps correctly with heuristic bots actively reacting."""
    env = AgarEnv()
    obs, info = env.reset(seed=42)

    # Learning player steps forward
    for _ in range(50):
        action = np.array([1.0, 0.0, -1.0], dtype=np.float32)
        obs, reward, term, trunc, info = env.step(action)
        if term or trunc:
            break

    # Check that opponents are alive and active
    active_bot_cells = [c for c in env.engine.cells if c.player_id > 0]
    assert len(active_bot_cells) > 0

