"""Environment factories shared by V11 training and short hardware profiles."""

from __future__ import annotations

from typing import Any, Callable, Optional

from src.training.hardware import configure_worker_thread_limits

configure_worker_thread_limits()

import numpy as np

from src.env.gym_wrapper import AgarEnv
from src.training.self_play_pool import SelfPlayPool


def make_env_fn(
    rank: int,
    env_config: dict[str, Any],
    pool: Optional[SelfPlayPool] = None,
    seed: int = 42,
    max_rivals: int = 2,
) -> Callable[[], AgarEnv]:
    """Build a picklable factory with cached actions and sparse pool refreshes."""
    def _init() -> AgarEnv:
        bot_opponents: dict[int, Any] = {}
        bot_cached_actions: dict[int, np.ndarray] = {}
        step_counters: dict[int, int] = {}
        last_sync = [0]

        def opponent_controller(bot_id: int, engine) -> np.ndarray:
            dummy_env = getattr(_init, "_cached_env", None)
            if (
                pool is not None
                and dummy_env is not None
                and dummy_env.current_step - last_sync[0] >= 20_000
            ):
                last_sync[0] = dummy_env.current_step
                pool.sync_from_disk(persist_state=False)

            current_step = step_counters.get(bot_id, 0)
            step_counters[bot_id] = current_step + 1
            if bot_id <= max_rivals and pool is not None and len(pool) > 0:
                if bot_id not in bot_opponents or current_step % 300 == 0:
                    bot_opponents[bot_id] = pool.sample_opponent()
                    bot_cached_actions.pop(bot_id, None)

                opponent = bot_opponents.get(bot_id)
                if opponent is not None and dummy_env is not None:
                    if bot_id in bot_cached_actions and current_step % 4 != 0:
                        return bot_cached_actions[bot_id]
                    obs = dummy_env._build_observation(player_id=bot_id)
                    action = pool.get_action(
                        opponent,
                        obs,
                        action_masks=dummy_env.action_masks(player_id=bot_id),
                    )
                    bot_cached_actions[bot_id] = action
                    return action

            if dummy_env is not None and bot_id in dummy_env.heuristic_bots:
                return dummy_env.heuristic_bots[bot_id].get_action(engine)

            angle = float(np.random.uniform(0.0, 2.0 * np.pi))
            return np.array([np.cos(angle), np.sin(angle), -1.0], dtype=np.float32)

        env = AgarEnv(config=env_config, opponent_policy_fn=opponent_controller, seed=seed + rank)
        _init._cached_env = env
        return env

    return _init
