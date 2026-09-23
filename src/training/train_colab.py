"""Standalone distributed PPO and Self-Play training script for AGAR-RL.

Compatible with Google Colab (GPU accelerated) and local execution:
    python src/training/train_colab.py --n-envs 16 --total-timesteps 10000000
"""

from __future__ import annotations
import os
import sys

# Ensure repository root is in python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Prevent tensorboard from hanging on heavy tensorflow load on Colab/Python 3.13
sys.modules["tensorflow"] = None
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import argparse
import yaml
from typing import Callable, Optional, Dict, Any
import numpy as np
import torch

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv, VecMonitor
from stable_baselines3.common.utils import set_random_seed

from src.env.gym_wrapper import AgarEnv
from src.training.self_play_pool import SelfPlayPool
from src.training.callbacks import SelfPlayCallback


def make_env_fn(
    rank: int,
    env_config: Dict[str, Any],
    pool: Optional[SelfPlayPool] = None,
    seed: int = 42,
) -> Callable[[], AgarEnv]:
    """Factory to instantiate vectorized environment instances with self-play opponents."""
    def _init() -> AgarEnv:
        bot_opponents: Dict[int, Any] = {}
        step_counters: Dict[int, int] = {}
        last_sync = [0]

        def opponent_controller(bot_id: int, engine) -> np.ndarray:
            dummy_env = getattr(_init, "_cached_env", None)

            # Periodically sync newly saved model checkpoints from disk
            if pool is not None and dummy_env is not None and (dummy_env.current_step - last_sync[0]) > 300:
                last_sync[0] = dummy_env.current_step
                pool.sync_from_disk()

            # Refresh opponent assignment on death or every 300 steps
            curr_step = step_counters.get(bot_id, 0)
            step_counters[bot_id] = curr_step + 1
            if bot_id not in bot_opponents or curr_step % 300 == 0:
                bot_opponents[bot_id] = pool.sample_opponent() if (pool and len(pool) > 0) else None

            opp = bot_opponents.get(bot_id, None)
            if opp is not None and opp.policy is not None and dummy_env is not None:
                obs = dummy_env._build_observation(player_id=bot_id)
                return pool.get_action(opp, obs)

            # Fallback to heuristic action
            if dummy_env is not None and bot_id in dummy_env.heuristic_bots:
                return dummy_env.heuristic_bots[bot_id].get_action(engine)

            ang = float(np.random.uniform(0, 2 * np.pi))
            return np.array([np.cos(ang), np.sin(ang), -1.0], dtype=np.float32)

        env = AgarEnv(config=env_config, opponent_policy_fn=opponent_controller, seed=seed + rank)
        _init._cached_env = env
        return env

    return _init


def parse_args():
    parser = argparse.ArgumentParser(description="AGAR-RL Distributed Self-Play Training")
    parser.add_argument("--n-envs", type=int, default=16, help="Number of parallel environments")
    parser.add_argument("--total-timesteps", type=int, default=10_000_000, help="Total training steps")
    parser.add_argument("--batch-size", type=int, default=128, help="PPO mini-batch size")
    parser.add_argument("--n-steps", type=int, default=2048, help="Steps per rollout per env")
    parser.add_argument("--learning-rate", type=float, default=3e-4, help="Learning rate")
    parser.add_argument("--gamma", type=float, default=0.99, help="Discount factor")
    parser.add_argument("--gae-lambda", type=float, default=0.95, help="GAE lambda parameter")
    parser.add_argument("--ent-coef", type=float, default=0.005, help="Entropy coefficient")
    parser.add_argument("--pool-interval", type=int, default=500_000, help="Steps between self-play pool updates")
    parser.add_argument("--config", type=str, default="config/ppo_config.yaml", help="Path to PPO config YAML")
    parser.add_argument("--env-config", type=str, default="config/env_config.yaml", help="Path to Env config YAML")
    parser.add_argument("--save-dir", type=str, default="checkpoints/ppo", help="Directory to save checkpoints")
    parser.add_argument("--history-dir", type=str, default="checkpoints/self_play_pool", help="Pool directory")
    parser.add_argument("--device", type=str, default="auto", help="Device ('cpu', 'cuda', 'auto')")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--use-dummy-vec", action="store_true", help="Force DummyVecEnv instead of SubprocVecEnv")
    return parser.parse_args()


def load_yaml(path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def main():
    args = parse_args()

    # Load configuration files if present
    ppo_cfg = load_yaml(args.config)
    env_cfg = load_yaml(args.env_config)

    # Resolve device (GPU if available on Colab)
    if args.device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device

    print("=" * 65)
    print("  AGAR-RL: Autonomous Multi-Agent Deep Reinforcement Learning")
    print(f"  Device: {device} (CUDA Available: {torch.cuda.is_available()})")
    print(f"  Parallel Envs: {args.n_envs}")
    print(f"  Total Timesteps: {args.total_timesteps:,}")
    print(f"  Self-Play Pool Interval: {args.pool_interval:,} steps")
    print("=" * 65)

    set_random_seed(args.seed)

    # Initialize Self-Play Pool
    pool = SelfPlayPool(
        max_size=int(ppo_cfg.get("self_play", {}).get("max_pool_size", 10)),
        history_dir=args.history_dir,
        heuristic_ratio=float(ppo_cfg.get("self_play", {}).get("heuristic_opponent_ratio", 0.3)),
        device=device,
    )

    # Build Vectorized Environments
    env_fns = [make_env_fn(rank=i, env_config=env_cfg, pool=pool, seed=args.seed) for i in range(args.n_envs)]

    # Use SubprocVecEnv on Linux/Colab, with fallback to DummyVecEnv on Windows if requested
    use_dummy = args.use_dummy_vec or (sys.platform == "win32" and args.n_envs <= 4)
    if use_dummy:
        print(f"Instantiating DummyVecEnv with {args.n_envs} instances...")
        vec_env = DummyVecEnv(env_fns)
    else:
        print(f"Instantiating SubprocVecEnv with {args.n_envs} instances...")
        vec_env = SubprocVecEnv(env_fns)

    vec_env = VecMonitor(vec_env)

    # Setup PPO hyperparameters
    n_steps = int(ppo_cfg.get("ppo", {}).get("n_steps", args.n_steps))
    batch_size = int(ppo_cfg.get("ppo", {}).get("batch_size", args.batch_size))
    gamma = float(ppo_cfg.get("ppo", {}).get("gamma", args.gamma))
    gae_lambda = float(ppo_cfg.get("ppo", {}).get("gae_lambda", args.gae_lambda))
    ent_coef = float(ppo_cfg.get("ppo", {}).get("ent_coef", args.ent_coef))
    lr = float(ppo_cfg.get("ppo", {}).get("learning_rate", args.learning_rate))

    # PPO Policy Architecture: 2x256 MLP
    policy_kwargs = {
        "net_arch": dict(pi=[256, 256], vf=[256, 256]),
        "activation_fn": torch.nn.ReLU,
    }

    # Check tensorboard availability
    try:
        import tensorboard  # noqa: F401
        tb_log = "logs/tensorboard"
    except ImportError:
        tb_log = None

    model = PPO(
        policy="MlpPolicy",
        env=vec_env,
        learning_rate=lr,
        n_steps=n_steps,
        batch_size=batch_size,
        gamma=gamma,
        gae_lambda=gae_lambda,
        ent_coef=ent_coef,
        vf_coef=0.5,
        max_grad_norm=0.5,
        policy_kwargs=policy_kwargs,
        tensorboard_log=tb_log,
        verbose=1,
        device=device,
    )

    # Self-Play Callback
    self_play_callback = SelfPlayCallback(
        pool=pool,
        update_interval_steps=args.pool_interval,
        save_dir=args.save_dir,
        log_interval_steps=5_000,
        verbose=1,
    )

    print(f"\nStarting PPO optimization loop for {args.total_timesteps:,} timesteps...")
    try:
        model.learn(
            total_timesteps=args.total_timesteps,
            callback=self_play_callback,
            progress_bar=False,
        )
    except KeyboardInterrupt:
        print("\nTraining interrupted by user. Saving current checkpoint...")

    # Save final model
    final_path = os.path.join(args.save_dir, "ppo_final.zip")
    model.save(final_path)
    print(f"\nTraining complete! Final model saved to: {final_path}")

    vec_env.close()


if __name__ == "__main__":
    main()
