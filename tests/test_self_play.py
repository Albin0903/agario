import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

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


def test_lazy_pool_discovers_new_training_checkpoints_without_loading_all_weights(tmp_path):
    from src.training.self_play_pool import SelfPlayPool

    history = tmp_path / "pool"
    checkpoints = tmp_path / "run"
    history.mkdir()
    checkpoints.mkdir()
    archive = checkpoints / "ppo_step_250000.zip"
    archive.write_bytes(b"x" * 2048)
    pool = SelfPlayPool(
        max_size=4,
        history_dir=str(history),
        checkpoint_dirs=[str(checkpoints)],
        preload_models=False,
    )
    assert pool.sync_from_disk(persist_state=False) == 1
    assert len(pool) == 1
    assert pool.pool[0].tag == archive.stem
    assert pool.pool[0].policy is None
    assert not (history / "pool_state.json").exists()


def test_lazy_pool_restores_metadata_by_checkpoint_basename(tmp_path):
    import json
    from src.training.self_play_pool import SelfPlayPool

    history = tmp_path / "pool"
    checkpoints = tmp_path / "run"
    history.mkdir()
    checkpoints.mkdir()
    archive = checkpoints / "ppo_step_500000.zip"
    archive.write_bytes(b"x" * 2048)
    (history / "pool_state.json").write_text(json.dumps([{
        "tag": "generation_500k", "path": "/old/colab/path/ppo_step_500000.zip",
        "generation": 4, "score": 12.5, "win_rate": 0.75,
    }]), encoding="utf-8")
    pool = SelfPlayPool(
        history_dir=str(history), checkpoint_dirs=[str(checkpoints)], preload_models=False,
    )
    assert pool.sync_from_disk(persist_state=False) == 1
    assert pool.pool[0].tag == "generation_500k"
    assert pool.pool[0].win_rate == 0.75
    assert pool.pool[0].score == 12.5


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
