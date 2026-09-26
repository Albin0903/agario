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

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

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

from sb3_contrib import MaskablePPO
from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv, VecMonitor, VecNormalize
from stable_baselines3.common.utils import set_random_seed

from src.env.gym_wrapper import AgarEnv
from src.training.self_play_pool import SelfPlayPool
from src.training.callbacks import SelfPlayCallback, ProfilingCallback
from src.training.policy_arch import (
    LayerNormMaskablePolicy,
    build_lr_schedule,
    build_policy_kwargs,
    checkpoint_num_timesteps,
    load_trained_model,
)


def make_env_fn(
    rank: int,
    env_config: Dict[str, Any],
    pool: Optional[SelfPlayPool] = None,
    seed: int = 42,
    max_rivals: int = 2,
) -> Callable[[], AgarEnv]:
    """Factory to instantiate vectorized environment instances with self-play opponents."""
    def _init() -> AgarEnv:
        # Prevent CPU thread contention in parallel workers
        try:
            import torch
            torch.set_num_threads(1)
        except Exception:
            pass

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

            # Only rival bots (IDs <= max_rivals) sample from the self-play pool
            if bot_id <= max_rivals and pool is not None and len(pool) > 0:
                if bot_id not in bot_opponents or curr_step % 300 == 0:
                    bot_opponents[bot_id] = pool.sample_opponent()
                    bot_cached_actions.pop(bot_id, None)

                opp = bot_opponents.get(bot_id, None)
                if opp is not None and opp.policy is not None and dummy_env is not None:
                    # Action repeat for opponent AI (query every 4 ticks)
                    if bot_id in bot_cached_actions and (curr_step % 4 != 0):
                        return bot_cached_actions[bot_id]

                    obs = dummy_env._build_observation(player_id=bot_id)
                    masks = dummy_env.action_masks(player_id=bot_id)
                    action = pool.get_action(opp, obs, action_masks=masks)
                    bot_cached_actions[bot_id] = action
                    return action

            # Ultra-fast Numba heuristic bot for all other bots (runs at 10,000 FPS)
            if dummy_env is not None and bot_id in dummy_env.heuristic_bots:
                return dummy_env.heuristic_bots[bot_id].get_action(engine)

            ang = float(np.random.uniform(0, 2 * np.pi))
            return np.array([np.cos(ang), np.sin(ang), -1.0], dtype=np.float32)

        env = AgarEnv(config=env_config, opponent_policy_fn=opponent_controller, seed=seed + rank)
        _init._cached_env = env
        # SubprocVecEnv requires the environment itself to expose action_masks().
        # AgarEnv implements that method directly; ActionMasker is only suitable
        # for single-process wrappers.
        return env

    return _init


def parse_args():
    parser = argparse.ArgumentParser(description="AGAR-RL Distributed Self-Play Training")
    parser.add_argument("--n-envs", "--num-envs", dest="n_envs", type=int, default=24, help="Number of parallel environments (default: 24 for GPU L4)")
    parser.add_argument("--total-timesteps", "--total-steps", dest="total_timesteps", type=int, default=15_000_000, help="Total training steps")
    parser.add_argument("--additional-timesteps", action="store_true", help="Treat --total-timesteps as steps to add after a resumed checkpoint")
    parser.add_argument("--batch-size", type=int, default=None, help="PPO mini-batch size (defaults to config value)")
    parser.add_argument("--n-epochs", type=int, default=None, help="PPO update epochs (defaults to config value)")
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
    parser.add_argument("--fresh", action="store_true", help="Force starting from scratch (wipe local & drive checkpoints and start clean at step 0)")
    parser.add_argument("--max-rivals", type=int, default=2, help="Max neural rival bots per env (default: 2 neural rivals; rest use microsecond Numba)")
    parser.add_argument("--warm-start", action="store_true", default=True, help="Warm-start policy network via behavioral cloning on HeuristicBot")
    parser.add_argument("--no-warm-start", action="store_false", dest="warm_start", help="Disable BC warm-start")
    parser.add_argument("--min-pool-step", type=int, default=200_000, help="Minimum step before expanding self-play pool")
    parser.add_argument("--backup-dir", type=str, default=None, help="Directory to mirror checkpoints to (e.g. Google Drive)")
    parser.add_argument("--log-level", choices=("quiet", "normal", "verbose"), default="normal", help="Training log verbosity")
    parser.add_argument("--profile-run", action="store_true", help="Print one machine-readable throughput line for profile selection")
    parser.add_argument("--log-interval", type=int, default=25_000, help="Steps between concise training metric lines")
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

    if device.startswith("cuda") and torch.cuda.is_available():
        # A100 Tensor Cores accelerate these matmuls while preserving the
        # float32 policy/value numerics used by PPO.
        torch.set_float32_matmul_precision("high")
        torch.backends.cudnn.allow_tf32 = True

    print("=" * 65)
    print("  AGAR-RL: Autonomous Multi-Agent Deep Reinforcement Learning")
    print(f"  Device: {device} (CUDA Available: {torch.cuda.is_available()})")
    print(f"  Parallel Envs: {args.n_envs}")
    print(f"  Total Timesteps: {args.total_timesteps:,}")
    print(f"  Self-Play Pool Interval: {args.pool_interval:,} steps")
    print("=" * 65)

    set_random_seed(args.seed)

    # 1. Manage Checkpoint Cleanup, Drive Restoration, and Auto-Resume Resolution
    import shutil, glob, re

    def extract_step(path: str) -> int:
        saved_step = checkpoint_num_timesteps(path)
        if saved_step is not None:
            return saved_step
        m = re.search(r"step_(\d+)", path)
        return int(m.group(1)) if m else 0

    resume_path = None
    teacher_path = None

    if args.fresh:
        print("🧹 [--fresh flag active] Purging local checkpoints to start clean from Step 0...")
        for clean_dir in [args.history_dir, args.save_dir]:
            if os.path.exists(clean_dir):
                for old_zip in glob.glob(os.path.join(clean_dir, "*.zip")):
                    try:
                        os.remove(old_zip)
                        print(f"   🧹 Purged local checkpoint: {old_zip}")
                    except Exception:
                        pass
            stale_normalization = os.path.join(args.save_dir, "vec_normalize.pkl")
            if os.path.exists(stale_normalization):
                os.remove(stale_normalization)
        # Also clean accidental early checkpoints in backup_dir
        if args.backup_dir and os.path.exists(args.backup_dir):
            for old_zip in glob.glob(os.path.join(args.backup_dir, "*.zip")):
                try:
                    os.remove(old_zip)
                    print(f"   🧹 Purged from Drive backup: {old_zip}")
                except Exception:
                    pass
        resume_path = None
    else:
        # Check if explicit resume checkpoint was provided
        resume_path = None
        if args.resume and args.resume.lower() not in ("none", "false", "no"):
            if os.path.exists(args.resume):
                resume_path = args.resume
                print(f"🎯 [Explicit Resume] Resuming directly from specified checkpoint: {resume_path}")
            elif args.backup_dir and os.path.exists(os.path.join(args.backup_dir, os.path.basename(args.resume))):
                resume_path = os.path.join(args.backup_dir, os.path.basename(args.resume))
                print(f"🎯 [Explicit Resume] Found checkpoint in backup dir: {resume_path}")

        if args.backup_dir:
            os.makedirs(args.backup_dir, exist_ok=True)
            drive_zips = [
                z for z in glob.glob(os.path.join(args.backup_dir, "*.zip"))
                if os.path.getsize(z) > 1000 and not os.path.basename(z).startswith("._") and "bc_pretrained" not in os.path.basename(z)
            ]

            if not drive_zips:
                print(f"📁 [Drive Backup] '{args.backup_dir}' has 0 checkpoints.")
                if resume_path is None and not args.fresh:
                    print("   🧹 Purging stale local VM checkpoints to start clean from Step 0...")
                    for clean_dir in [args.history_dir, args.save_dir]:
                        if os.path.exists(clean_dir):
                            for old_zip in glob.glob(os.path.join(clean_dir, "*.zip")):
                                try:
                                    os.remove(old_zip)
                                    print(f"   🧹 Purged stale local checkpoint: {old_zip}")
                                except Exception:
                                    pass
            else:
                # Checkpoints exist in Drive backup -> Restore them into local pool
                os.makedirs(args.history_dir, exist_ok=True)
                print(f"📁 [Drive Backup] Found {len(drive_zips)} checkpoints in Drive backup. Restoring...")
                drive_pool_state = os.path.join(args.backup_dir, "pool_state.json")
                local_pool_state = os.path.join(args.history_dir, "pool_state.json")
                if os.path.exists(drive_pool_state) and not os.path.exists(local_pool_state):
                    shutil.copy2(drive_pool_state, local_pool_state)
                for dz in drive_zips:
                    dest = os.path.join(args.history_dir, os.path.basename(dz))
                    if not os.path.exists(dest):
                        shutil.copy2(dz, dest)

                if resume_path is None and args.resume and args.resume.lower() == "auto":
                    drive_zips.sort(key=extract_step, reverse=True)
                    resume_path = drive_zips[0]
                    print(f"🔍 [Auto-Resume] Selected latest Drive checkpoint: {resume_path} (step: {extract_step(resume_path):,})")
        else:
            # No backup_dir specified (e.g. local PC execution)
            if resume_path is None and args.resume and args.resume.lower() not in ("none", "false", "no"):
                if args.resume == "auto":
                    local_zips = [
                        z for z in (glob.glob(os.path.join(args.history_dir, "*.zip")) + glob.glob(os.path.join(args.save_dir, "*.zip")))
                        if os.path.getsize(z) > 1000 and not os.path.basename(z).startswith("._") and "bc_pretrained" not in os.path.basename(z)
                    ]
                    if local_zips:
                        local_zips.sort(key=extract_step, reverse=True)
                        resume_path = local_zips[0]
                        print(f"🔍 [Auto-Resume] Found {len(local_zips)} local checkpoints. Selected latest: {resume_path}")
                elif os.path.exists(args.resume):
                    resume_path = args.resume

    # Initialize Self-Play Pool (workers run opponent inference on CPU for multi-process safety)
    pool = SelfPlayPool(
        max_size=int(ppo_cfg.get("self_play", {}).get("max_pool_size", 10)),
        history_dir=args.history_dir,
        heuristic_ratio=float(ppo_cfg.get("self_play", {}).get("heuristic_opponent_ratio", 0.3)),
        current_ratio=float(ppo_cfg.get("self_play", {}).get("current_opponent_ratio", 0.2)),
        pfsp_power=float(ppo_cfg.get("self_play", {}).get("pfsp_power", 1.5)),
        seed=args.seed,
        device="cpu",
        verbose=2 if args.log_level == "verbose" else 0,
    )
    pool.sync_from_disk()

    # Build Vectorized Environments (only max_rivals bots per env query neural net, others use microsecond Numba)
    env_fns = [
        make_env_fn(rank=i, env_config=env_cfg, pool=pool, seed=args.seed, max_rivals=args.max_rivals)
        for i in range(args.n_envs)
    ]

    # Use SubprocVecEnv on Linux/Colab, with fallback to DummyVecEnv on Windows if requested
    use_dummy = args.use_dummy_vec or (sys.platform == "win32" and args.n_envs <= 4)
    if use_dummy:
        print(f"Instantiating DummyVecEnv with {args.n_envs} instances...")
        vec_env = DummyVecEnv(env_fns)
    else:
        print(f"Instantiating SubprocVecEnv with {args.n_envs} instances...")
        vec_env = SubprocVecEnv(env_fns)

    vec_env = VecMonitor(vec_env)

    gamma = float(ppo_cfg.get("ppo", {}).get("gamma", args.gamma))

    # SOTA 2026 Stability: VecNormalize running reward variance stabilizer
    # Normalizes return variance so late-game multi-kill combat doesn't destabilize early representations
    vn_path = os.path.join(args.save_dir, "vec_normalize.pkl")
    if args.backup_dir and os.path.exists(os.path.join(args.backup_dir, "vec_normalize.pkl")):
        import shutil
        os.makedirs(args.save_dir, exist_ok=True)
        shutil.copy2(os.path.join(args.backup_dir, "vec_normalize.pkl"), vn_path)

    if os.path.exists(vn_path):
        print(f"📊 [VecNormalize] Restoring running normalization stats from {vn_path}")
        vec_env = VecNormalize.load(vn_path, vec_env)
    else:
        print("📊 [VecNormalize] Initializing running reward normalization (norm_obs=False, norm_reward=True, clip=10.0)")
        vec_env = VecNormalize(vec_env, norm_obs=False, norm_reward=True, clip_reward=10.0, gamma=gamma)
    gae_lambda = float(ppo_cfg.get("ppo", {}).get("gae_lambda", args.gae_lambda))
    target_kl = ppo_cfg.get("ppo", {}).get("target_kl", 0.05)
    target_kl = float(target_kl) if target_kl is not None else None
    ent_coef = float(ppo_cfg.get("ppo", {}).get("ent_coef", args.ent_coef))
    ent_coef_end = float(ppo_cfg.get("ppo", {}).get("ent_coef_end", 0.001))
    n_steps = int(args.n_steps if args.n_steps is not None else ppo_cfg.get("ppo", {}).get("n_steps", 2048))
    batch_size = int(args.batch_size if args.batch_size is not None else ppo_cfg.get("ppo", {}).get("batch_size", 1024))
    n_epochs = int(args.n_epochs if args.n_epochs is not None else ppo_cfg.get("ppo", {}).get("n_epochs", 8))
    lr_start = float(ppo_cfg.get("ppo", {}).get("learning_rate", args.learning_rate))
    lr_end = float(ppo_cfg.get("ppo", {}).get("learning_rate_end", 1e-5))
    lr = build_lr_schedule(ppo_cfg, lr_start)
    policy_kwargs = build_policy_kwargs(ppo_cfg)
    print(
        f"  V10: MaskablePPO + {ppo_cfg.get('policy', {}).get('norm', 'layernorm')}(512) "
        f"+ cosine LR {lr_start:.1e} → {lr_end:.1e} | "
        f"rollout={n_steps}×{args.n_envs}, batch={batch_size}, epochs={n_epochs}"
    )

    # Check tensorboard availability
    try:
        import tensorboard  # noqa: F401
        tb_log = "logs/tensorboard"
    except ImportError:
        tb_log = None

    is_resumed = False
    if resume_path and os.path.exists(resume_path):
        print(f"\n🔄 Resuming MaskablePPO model from checkpoint: {resume_path}")
        try:
            model = load_trained_model(
                resume_path,
                env=vec_env,
                device=device,
                tensorboard_log=tb_log,
                learning_rate=lr,
            )
            if not isinstance(model, MaskablePPO):
                raise TypeError("checkpoint is vanilla PPO, not MaskablePPO")
            # Updating PPO's minibatch/epoch knobs is safe on resume; n_steps
            # remains the serialized value because the rollout buffer was built
            # with that size during load.
            if args.batch_size is not None:
                model.batch_size = batch_size
            if args.n_epochs is not None:
                model.n_epochs = n_epochs
            is_resumed = True
            manifest_path = os.path.join(os.path.dirname(resume_path), "v10_manifest.json")
            if os.path.exists(manifest_path):
                try:
                    import json
                    with open(manifest_path, encoding="utf-8") as handle:
                        manifest_step = int(json.load(handle).get("timesteps", model.num_timesteps))
                    if manifest_step != int(model.num_timesteps):
                        print(
                            f"⚠️ Manifest says {manifest_step:,}, checkpoint stores "
                            f"{model.num_timesteps:,}; using the checkpoint's internal counter."
                        )
                except (OSError, ValueError, TypeError):
                    pass
        except Exception as e:
            if args.resume and args.resume.lower() not in ("auto", "none", "false", "no"):
                vec_env.close()
                raise RuntimeError(
                    f"Explicit checkpoint '{resume_path}' could not be resumed as V10. "
                    "No files were overwritten; choose a compatible V10 checkpoint or explicitly configure a teacher warm-start."
                ) from e
            print(
                f"⚠️ V10 cannot resume '{resume_path}' ({e}). "
                "Architecture changed (MaskablePPO + LayerNorm). Starting a fresh V10 run. "
                "Use --fresh to skip this warning."
            )
            teacher_path = resume_path
            resume_path = None
    if not is_resumed:
        # Check if warm-start BC model is requested or available
        bc_filename = "ppo_v9_teacher_bc.zip" if teacher_path else "ppo_bc_pretrained.zip"
        bc_path = os.path.join(args.save_dir, bc_filename)
        if args.backup_dir and os.path.exists(os.path.join(args.backup_dir, bc_filename)):
            import shutil
            os.makedirs(args.save_dir, exist_ok=True)
            shutil.copy2(os.path.join(args.backup_dir, bc_filename), bc_path)

        if args.warm_start and not os.path.exists(bc_path):
            print("\n🎓 [Warm-Start] Pre-training policy network on HeuristicBot demonstrations (60s)...")
            from src.training.pretrain_bc import pretrain_policy
            pretrain_policy(
                output_path=bc_path,
                num_samples=25000,
                epochs=6,
                config_path=args.config,
                env_config_path=args.env_config,
                device=device,
                seed=args.seed,
                teacher_path=teacher_path,
            )
            if args.backup_dir and os.path.exists(args.backup_dir):
                try:
                    import shutil
                    shutil.copy2(bc_path, os.path.join(args.backup_dir, bc_filename))
                except Exception:
                    pass

        if os.path.exists(bc_path):
            print(f"\n🚀 Initializing MaskablePPO from warm-started BC policy: {bc_path}")
            try:
                model = load_trained_model(
                    bc_path,
                    env=vec_env,
                    device=device,
                    tensorboard_log=tb_log,
                    learning_rate=lr,
                    n_steps=n_steps,
                    batch_size=batch_size,
                    n_epochs=n_epochs,
                    gamma=gamma,
                    gae_lambda=gae_lambda,
                    target_kl=target_kl,
                    ent_coef=ent_coef,
                    vf_coef=0.5,
                    max_grad_norm=0.5,
                )
            except Exception as e:
                print(f"⚠️ BC checkpoint incompatible with V10 ({e}). Training from scratch.")
                model = None
        else:
            model = None
        if model is None:
            print("\n🚀 Starting fresh MaskablePPO training (V10 LayerNorm + action masking).")
            model = MaskablePPO(
                policy=LayerNormMaskablePolicy,
                env=vec_env,
                learning_rate=lr,
                n_steps=n_steps,
                batch_size=batch_size,
                n_epochs=n_epochs,
                gamma=gamma,
                gae_lambda=gae_lambda,
                target_kl=target_kl,
                ent_coef=ent_coef,
                vf_coef=0.5,
                max_grad_norm=0.5,
                policy_kwargs=policy_kwargs,
                tensorboard_log=tb_log,
                verbose=0 if args.log_level == "quiet" else 1,
                device=device,
            )

    # Self-Play Callback & Profiling Callback
    self_play_callback = SelfPlayCallback(
        pool=pool,
        update_interval_steps=args.pool_interval,
        save_dir=args.save_dir,
        log_interval_steps=max(args.log_interval, args.n_envs),
        min_pool_step=args.min_pool_step,
        backup_dir=args.backup_dir,
        ent_coef_start=ent_coef,
        ent_coef_end=ent_coef_end,
        verbose=2 if args.log_level == "verbose" else (0 if args.log_level == "quiet" else 1),
    )
    profiler_callback = ProfilingCallback()

    start_timesteps = int(getattr(model, "num_timesteps", 0)) if is_resumed else 0
    requested_target = args.total_timesteps
    if is_resumed and args.additional_timesteps:
        requested_target += start_timesteps
    remaining_timesteps = max(0, requested_target - start_timesteps)
    training_started = __import__("time").perf_counter()
    print(
        f"\nTraining progress: {start_timesteps:,} / {requested_target:,} timesteps "
        f"({remaining_timesteps:,} remaining; resume={'yes' if is_resumed else 'no'})."
    )
    try:
        if remaining_timesteps > 0:
            model.learn(
                total_timesteps=requested_target,
                callback=[self_play_callback, profiler_callback],
                progress_bar=False,
                reset_num_timesteps=not is_resumed,
            )
        else:
            print("Requested training target is already reached; saving resumed model without another rollout.")
    except KeyboardInterrupt:
        print("\nTraining interrupted by user. Saving current checkpoint...")

    if args.profile_run:
        elapsed_training = max(1e-6, __import__("time").perf_counter() - training_started)
        trained_steps = max(0, int(model.num_timesteps) - start_timesteps)
        print(f"PROFILE_RESULT steps_per_second={trained_steps / elapsed_training:.3f} trained_steps={trained_steps}")

    # Save final model
    final_path = os.path.join(args.save_dir, "ppo_final.zip")
    model.save(final_path)
    last_path = os.path.join(args.save_dir, "ppo_last.zip")
    model.save(last_path)
    if isinstance(vec_env, VecNormalize):
        vec_env.save(os.path.join(args.save_dir, "vec_normalize.pkl"))
    if args.backup_dir:
        os.makedirs(args.backup_dir, exist_ok=True)
        for source in (final_path, last_path, os.path.join(args.save_dir, "vec_normalize.pkl")):
            if os.path.exists(source):
                SelfPlayCallback._mirror_file(source, os.path.join(args.backup_dir, os.path.basename(source)))
        import json
        manifest_path = os.path.join(args.save_dir, "v10_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump({"version": "v10", "timesteps": int(model.num_timesteps),
                       "checkpoint": "ppo_last.zip", "vec_normalize": "vec_normalize.pkl"}, handle, indent=2)
        SelfPlayCallback._mirror_file(manifest_path, os.path.join(args.backup_dir, "v10_manifest.json"))
    print(f"\nTraining complete! Final model saved to: {final_path}")

    vec_env.close()


if __name__ == "__main__":
    main()
