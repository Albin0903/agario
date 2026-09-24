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

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="stable_baselines3")
warnings.filterwarnings("ignore", message=".*Gym has been unmaintained.*")
warnings.filterwarnings("ignore", category=UserWarning, module="gym")

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
        bot_cached_actions: Dict[int, np.ndarray] = {}
        step_counters: Dict[int, int] = {}
        last_sync = [0]

        def opponent_controller(bot_id: int, engine) -> np.ndarray:
            dummy_env = getattr(_init, "_cached_env", None)

            # Periodically sync newly saved model checkpoints from disk (every 2000 steps)
            if pool is not None and dummy_env is not None and (dummy_env.current_step - last_sync[0]) > 2000:
                last_sync[0] = dummy_env.current_step
                pool.sync_from_disk()

            curr_step = step_counters.get(bot_id, 0)
            step_counters[bot_id] = curr_step + 1

            # Refresh opponent assignment on death or every 300 steps
            if bot_id not in bot_opponents or curr_step % 300 == 0:
                bot_opponents[bot_id] = pool.sample_opponent() if (pool and len(pool) > 0) else None
                bot_cached_actions.pop(bot_id, None)

            opp = bot_opponents.get(bot_id, None)
            if opp is not None and opp.policy is not None and dummy_env is not None:
                # Frame-skip / action repeat (every 4 ticks) for opponent AI to sustain 500+ training FPS
                if bot_id in bot_cached_actions and (curr_step % 4 != 0):
                    return bot_cached_actions[bot_id]

                obs = dummy_env._build_observation(player_id=bot_id)
                action = pool.get_action(opp, obs)
                bot_cached_actions[bot_id] = action
                return action

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
    parser.add_argument("--pool-interval", type=int, default=50_000, help="Steps between self-play pool updates")
    parser.add_argument("--config", type=str, default="config/ppo_config.yaml", help="Path to PPO config YAML")
    parser.add_argument("--env-config", type=str, default="config/env_config.yaml", help="Path to Env config YAML")
    parser.add_argument("--save-dir", type=str, default="checkpoints/ppo", help="Directory to save checkpoints")
    parser.add_argument("--history-dir", type=str, default="checkpoints/self_play_pool", help="Pool directory")
    parser.add_argument("--device", type=str, default="auto", help="Device ('cpu', 'cuda', 'auto')")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--use-dummy-vec", action="store_true", help="Force DummyVecEnv instead of SubprocVecEnv")
    parser.add_argument("--resume", type=str, default=None, help="Path to checkpoint .zip to resume from, or 'auto'")
    parser.add_argument("--backup-dir", type=str, default=None, help="Directory to mirror checkpoints to (e.g. Google Drive)")
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
    pool.sync_from_disk()

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

    # PPO Policy Architecture: 2x512 MLP (Guide Section 6)
    cfg_net_arch = ppo_cfg.get("policy", {}).get("net_arch", dict(pi=[512, 512], vf=[512, 512]))
    policy_kwargs = {
        "net_arch": cfg_net_arch,
        "activation_fn": torch.nn.ReLU,
    }

    # Check tensorboard availability
    try:
        import tensorboard  # noqa: F401
        tb_log = "logs/tensorboard"
    except ImportError:
        tb_log = None

    # Restore existing checkpoints from backup-dir if available
    if args.backup_dir and os.path.exists(args.backup_dir):
        import shutil, glob
        os.makedirs(args.history_dir, exist_ok=True)
        drive_zips = glob.glob(os.path.join(args.backup_dir, "*.zip"))
        if drive_zips:
            print(f"📁 [Drive Backup] Restoring {len(drive_zips)} checkpoints from Drive to local pool...")
            for dz in drive_zips:
                dest = os.path.join(args.history_dir, os.path.basename(dz))
                if not os.path.exists(dest):
                    shutil.copy2(dz, dest)
            pool.sync_from_disk()

    # Resolve checkpoint to resume from
    resume_path = None
    if args.resume:
        if args.resume == "auto":
            candidates = []
            if os.path.exists(os.path.join(args.save_dir, "ppo_latest.zip")):
                candidates.append(os.path.join(args.save_dir, "ppo_latest.zip"))
            if args.backup_dir and os.path.exists(os.path.join(args.backup_dir, "ppo_latest.zip")):
                candidates.append(os.path.join(args.backup_dir, "ppo_latest.zip"))
            import glob
            pool_ckpts = sorted(glob.glob(os.path.join(args.history_dir, "*.zip")))
            if pool_ckpts:
                candidates.append(pool_ckpts[-1])
            if args.backup_dir:
                drive_ckpts = sorted(glob.glob(os.path.join(args.backup_dir, "*.zip")))
                if drive_ckpts:
                    candidates.append(drive_ckpts[-1])
            if candidates:
                resume_path = candidates[0]
        elif os.path.exists(args.resume):
            resume_path = args.resume
        elif args.backup_dir and os.path.exists(os.path.join(args.backup_dir, os.path.basename(args.resume))):
            resume_path = os.path.join(args.backup_dir, os.path.basename(args.resume))

    if resume_path and os.path.exists(resume_path):
        print(f"\nResuming PPO model from checkpoint: {resume_path}")
        model = PPO.load(
            resume_path,
            env=vec_env,
            device=device,
            tensorboard_log=tb_log,
        )
    else:
        if args.resume and args.resume.lower() not in ("none", "false", "no"):
            print(f"\n⚠️ Checkpoint '{args.resume}' not found. Starting fresh PPO training from scratch.")
        else:
            print("\n🚀 Starting fresh PPO training from scratch (V2 architecture).")
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
        backup_dir=args.backup_dir,
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

    if args.backup_dir:
        try:
            import shutil
            os.makedirs(args.backup_dir, exist_ok=True)
            shutil.copy2(final_path, os.path.join(args.backup_dir, "ppo_final.zip"))
            print(f"📁 [Drive Backup] Final model mirrored to: {os.path.join(args.backup_dir, 'ppo_final.zip')}")
        except Exception as e:
            print(f"⚠️ [Drive Backup] Warning: Could not mirror final model: {e}")

    vec_env.close()


if __name__ == "__main__":
    main()
