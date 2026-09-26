"""Train V11 from V10 policy weights or resume a V11 training checkpoint.

V10 inputs are weights-only warm starts. V11 resume checkpoints restore the
V11 optimizer/counter and VecNormalize state. The two modes are exclusive.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.training.hardware import configure_worker_thread_limits, effective_cpu_count

configure_worker_thread_limits()

import torch
import yaml
# V11 stores concise JSONL metrics and does not use event files. Prevent SB3's
# optional TensorBoard import from probing Colab's TensorFlow installation.
sys.modules["torch.utils.tensorboard"] = None
from sb3_contrib import MaskablePPO
from stable_baselines3.common.utils import set_random_seed
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecMonitor, VecNormalize

from src.training.callbacks_v11 import V11TrainingCallback
from src.training.env_factory import make_env_fn
from src.training.policy_arch import LayerNormMaskablePolicy, build_lr_schedule, build_policy_kwargs
from src.training.self_play_pool import SelfPlayPool
from src.training.warm_start import initialize_v11_from_v10


def _load_yaml(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--v10-checkpoint", help="Explicit V10 MaskablePPO .zip; imports policy weights only")
    source.add_argument("--resume-v11", help="V11 checkpoint .zip, or 'auto' in the output/backup directory")
    parser.add_argument("--config", default="config/ppo_v11.yaml")
    parser.add_argument("--env-config", default="config/env_config.yaml")
    parser.add_argument("--n-envs", type=int, default=8)
    parser.add_argument("--n-steps", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--n-epochs", type=int, default=None)
    parser.add_argument("--total-timesteps", type=int, default=None)
    parser.add_argument("--save-dir", default="checkpoints/v11")
    parser.add_argument("--history-dir", default="checkpoints/v11/self_play_pool")
    parser.add_argument("--backup-dir", default=None)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-rivals", type=int, default=2)
    parser.add_argument("--dummy-vec", action="store_true")
    parser.add_argument("--profile-run", action="store_true")
    return parser.parse_args()


def _restore_drive_files(save_dir: Path, history_dir: Path, backup_dir: Path) -> None:
    save_dir.mkdir(parents=True, exist_ok=True)
    history_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "ppo_latest.zip", "vec_normalize.pkl", "v11_manifest.json", "metrics.jsonl",
        "scenario_evaluations.jsonl",
    ):
        source = backup_dir / name
        target = save_dir / name
        if source.is_file() and not target.exists():
            shutil.copy2(source, target)
    manifest_path = save_dir / "v11_manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for key in ("step_checkpoint", "vec_normalize_checkpoint"):
                name = manifest.get(key)
                if name:
                    source = backup_dir / Path(name).name
                    target = save_dir / Path(name).name
                    if source.is_file() and not target.exists():
                        shutil.copy2(source, target)
        except (OSError, ValueError, TypeError):
            pass
    pool_state = backup_dir / "pool_state.json"
    if pool_state.is_file() and not (history_dir / pool_state.name).exists():
        shutil.copy2(pool_state, history_dir / pool_state.name)

    # Only fetch immutable checkpoints needed for the active league and resume.
    # Copying every historical archive from Drive can waste minutes and disk.
    required: set[str] = set()
    manifest_path = save_dir / "v11_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("step_checkpoint"):
            required.add(Path(manifest["step_checkpoint"]).name)
    except (OSError, ValueError, TypeError):
        pass
    if pool_state.is_file():
        try:
            entries = json.loads(pool_state.read_text(encoding="utf-8"))
            required.update(
                Path(str(entry.get("path", ""))).name
                for entry in entries
                if str(entry.get("path", "")).endswith(".zip")
            )
        except (OSError, ValueError, TypeError, AttributeError):
            pass
    if not required:
        checkpoints = sorted(
            backup_dir.glob("ppo_step_*.zip"),
            key=lambda path: int(path.stem.rsplit("_", 1)[-1]) if path.stem.rsplit("_", 1)[-1].isdigit() else -1,
        )
        required.update(path.name for path in checkpoints[-20:])
    for name in required:
        source, target = backup_dir / name, save_dir / name
        if source.is_file() and not target.exists():
            shutil.copy2(source, target)


def _resolve_v11_checkpoint(arg: str, save_dir: Path, backup_dir: Path | None) -> Path:
    if arg.lower() == "auto":
        candidates = []
        for folder in (save_dir, backup_dir):
            if not folder:
                continue
            manifest_path = folder / "v11_manifest.json"
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                step_name = manifest.get("step_checkpoint")
                if step_name:
                    candidates.append(folder / Path(step_name).name)
            except (OSError, ValueError, TypeError):
                pass
            candidates.append(folder / "ppo_latest.zip")
        for path in candidates:
            if path.is_file() and path.stat().st_size > 1024:
                return path
        raise FileNotFoundError("No valid V11 ppo_latest.zip found for --resume-v11 auto")
    path = Path(arg)
    if path.is_file():
        return path
    if backup_dir and (backup_dir / path.name).is_file():
        return backup_dir / path.name
    raise FileNotFoundError(f"V11 checkpoint not found: {arg}")


def _load_custom_v11(path: Path, env, device: str) -> MaskablePPO:
    from src.training.policy_arch import custom_policy_objects

    model = MaskablePPO.load(
        str(path),
        env=env,
        device=device,
        tensorboard_log=None,
        custom_objects=custom_policy_objects(),
    )
    if not isinstance(model, MaskablePPO):
        raise TypeError(f"V11 resume must be MaskablePPO, received {type(model).__name__}")
    return model


def main() -> None:
    args = _args()
    ppo_cfg = _load_yaml(args.config)
    env_cfg = _load_yaml(args.env_config)
    ppo = ppo_cfg.get("ppo", {})
    self_play_cfg = ppo_cfg.get("self_play", {})
    logging_cfg = ppo_cfg.get("logging", {})

    if args.n_envs < 1:
        raise ValueError("--n-envs must be at least 1")
    cpu_budget = effective_cpu_count()
    if args.n_envs > cpu_budget:
        print(f"[V11 hardware] warning: n_envs={args.n_envs} exceeds available CPU budget={cpu_budget}")
    n_steps = int(args.n_steps or ppo.get("n_steps", 2048))
    batch_size = int(args.batch_size or ppo.get("batch_size", 1024))
    n_epochs = int(args.n_epochs or ppo.get("n_epochs", 8))
    total_timesteps = int(args.total_timesteps or ppo.get("total_timesteps", 20_000_000))
    rollout_size = n_steps * args.n_envs
    if batch_size > rollout_size or rollout_size % batch_size:
        raise ValueError(
            f"PPO batch_size={batch_size} must divide n_steps*n_envs={rollout_size} exactly"
        )
    if args.profile_run:
        total_timesteps = min(total_timesteps, rollout_size * 2)

    save_dir = Path(args.save_dir).resolve()
    history_dir = Path(args.history_dir).resolve()
    backup_dir = Path(args.backup_dir).resolve() if args.backup_dir else None
    save_dir.mkdir(parents=True, exist_ok=True)
    history_dir.mkdir(parents=True, exist_ok=True)

    if args.resume_v11:
        if backup_dir:
            _restore_drive_files(save_dir, history_dir, backup_dir)
        resume_path = _resolve_v11_checkpoint(args.resume_v11, save_dir, backup_dir)
        manifest_path = resume_path.parent / "v11_manifest.json"
        if backup_dir and not manifest_path.exists() and (backup_dir / manifest_path.name).exists():
            shutil.copy2(backup_dir / manifest_path.name, manifest_path)
        if not manifest_path.is_file():
            raise FileNotFoundError(f"V11 manifest is required beside checkpoint: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("version") != "v11":
            raise ValueError("Refusing to resume a checkpoint without a V11 manifest")
        for key, requested in (("n_envs", args.n_envs), ("n_steps", n_steps)):
            if int(manifest[key]) != int(requested):
                raise ValueError(
                    f"V11 resume requires the saved {key}={manifest[key]}, got {requested}; "
                    "use the same rollout geometry when resuming"
                )
        source_v10 = manifest.get("source_v10_checkpoint")
    else:
        resume_path = None
        source_v10 = str(Path(args.v10_checkpoint).resolve())
        if not Path(source_v10).is_file():
            raise FileNotFoundError(f"Explicit V10 checkpoint does not exist: {source_v10}")
        if save_dir.joinpath("v11_manifest.json").exists():
            raise FileExistsError(
                f"{save_dir} already contains a V11 run. Use --resume-v11 auto or choose a new output directory."
            )

    device = args.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    if device.startswith("cuda") and torch.cuda.is_available():
        torch.set_float32_matmul_precision("high")

    set_random_seed(args.seed)
    pool = SelfPlayPool(
        max_size=int(self_play_cfg.get("max_pool_size", 20)),
        history_dir=str(history_dir),
        heuristic_ratio=float(self_play_cfg.get("heuristic_opponent_ratio", 0.3)),
        current_ratio=float(self_play_cfg.get("current_opponent_ratio", 0.2)),
        pfsp_power=float(self_play_cfg.get("pfsp_power", 1.5)),
        seed=args.seed,
        device="cpu",
        verbose=0,
        checkpoint_dirs=[str(save_dir)],
        preload_models=False,
        max_cached_models=max(2, args.max_rivals * 2),
    )
    pool.sync_from_disk()

    env_fns = [
        make_env_fn(i, env_cfg, pool=pool, seed=args.seed, max_rivals=args.max_rivals)
        for i in range(args.n_envs)
    ]
    if args.dummy_vec or args.n_envs == 1:
        vec_env = DummyVecEnv(env_fns)
    else:
        vec_env = SubprocVecEnv(env_fns)
    vec_env = VecMonitor(vec_env)

    norm_path = save_dir / "vec_normalize.pkl"
    if resume_path:
        norm_name = (
            manifest.get("vec_normalize_checkpoint") or manifest.get("vec_normalize")
            or "vec_normalize.pkl"
        )
        norm_path = save_dir / Path(norm_name).name
        if not norm_path.exists() and backup_dir:
            drive_norm = backup_dir / norm_path.name
            if drive_norm.is_file():
                shutil.copy2(drive_norm, norm_path)
        if not norm_path.exists():
            raise FileNotFoundError(f"V11 resume requires its VecNormalize state: {norm_path.name}")
        vec_env = VecNormalize.load(str(norm_path), vec_env)
        vec_env.training = True
        vec_env.norm_reward = bool(ppo.get("reward_normalization", True))
    else:
        vec_env = VecNormalize(
            vec_env,
            norm_obs=False,
            norm_reward=bool(ppo.get("reward_normalization", True)),
            clip_reward=10.0,
            gamma=float(ppo.get("gamma", 0.997)),
        )

    lr_start = float(ppo.get("learning_rate", 3e-4))
    lr = build_lr_schedule(ppo_cfg, lr_start)
    policy_kwargs = build_policy_kwargs(ppo_cfg)
    if resume_path:
        model = _load_custom_v11(resume_path, vec_env, device)
        expected_step = int(manifest["timesteps"])
        actual_step = int(model.num_timesteps)
        if actual_step != expected_step:
            vec_env.close()
            raise ValueError(
                f"V11 manifest says step {expected_step:,}, but checkpoint {resume_path.name} "
                f"stores {actual_step:,}. Refusing an ambiguous resume."
            )
        model.batch_size = batch_size
        model.n_epochs = n_epochs
    else:
        model = MaskablePPO(
            policy=LayerNormMaskablePolicy,
            env=vec_env,
            learning_rate=lr,
            n_steps=n_steps,
            batch_size=batch_size,
            n_epochs=n_epochs,
            gamma=float(ppo.get("gamma", 0.997)),
            gae_lambda=float(ppo.get("gae_lambda", 0.95)),
            clip_range=float(ppo.get("clip_range", 0.2)),
            target_kl=ppo.get("target_kl", 0.05),
            normalize_advantage=bool(ppo.get("normalize_advantage", True)),
            ent_coef=float(ppo.get("ent_coef", 0.005)),
            vf_coef=float(ppo.get("vf_coef", 0.5)),
            max_grad_norm=float(ppo.get("max_grad_norm", 0.5)),
            policy_kwargs=policy_kwargs,
            tensorboard_log=None,
            verbose=0,
            seed=args.seed,
            device=device,
        )
        warm_start_info = initialize_v11_from_v10(args.v10_checkpoint, model, device="cpu")
        print(
            f"[V11 warm start] copied {warm_start_info['parameters']:,} parameters from "
            f"V10 step {warm_start_info['source_num_timesteps']:,}; V11 counter/optimizer reset"
        )

    print(
        f"[V11] device={device} envs={args.n_envs} rollout={n_steps}×{args.n_envs} "
        f"batch={batch_size} epochs={n_epochs} target={total_timesteps:,}; "
        f"CPU budget={cpu_budget}, env-worker/BLAS/Numba thread caps=1"
    )
    callback = V11TrainingCallback(
        pool=pool,
        save_dir=str(save_dir),
        backup_dir=str(backup_dir) if backup_dir else None,
        config=ppo_cfg,
        source_v10=source_v10,
        metric_interval=int(logging_cfg.get("metrics_interval_steps", 100_000)),
        checkpoint_interval=int(logging_cfg.get("checkpoint_interval_steps", 250_000)),
        evaluation_interval=int(logging_cfg.get("evaluation_interval_steps", 1_000_000)),
        evaluation_episodes=int(logging_cfg.get("evaluation_episodes_per_scenario", 5)),
        split_kill_horizon=int(logging_cfg.get("split_kill_horizon_steps", 30)),
        pool_update_interval=int(self_play_cfg.get("update_interval_steps", 250_000)),
        min_pool_step=int(self_play_cfg.get("min_pool_step", 200_000)),
        drive_sync_seconds=float(logging_cfg.get("drive_sync_interval_seconds", 300.0)),
    )
    start = int(model.num_timesteps)
    callback.last_checkpoint = start
    callback.last_pool_update = start
    callback.last_metric_step = start
    callback.next_metric = ((start // callback.metric_interval) + 1) * callback.metric_interval
    callback.next_evaluation = ((start // callback.evaluation_interval) + 1) * callback.evaluation_interval
    callback.prepare_resume(start)
    if start >= total_timesteps:
        print(f"[V11] checkpoint already reached target ({start:,}/{total_timesteps:,})")
        callback.model = model
        if callback.resume_evaluation_milestone:
            milestone = callback.resume_evaluation_milestone
            callback.save_and_sync()
            try:
                if not callback._run_scenario_evaluation(start, milestone):
                    raise RuntimeError(f"Could not complete evaluation for milestone {milestone:,}.")
            finally:
                callback.save_and_sync()
                vec_env.close()
            return
        callback.save_and_sync()
        vec_env.close()
        return

    if device.startswith("cuda") and torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    try:
        model.learn(
            # SB3 interprets total_timesteps as additional steps when
            # reset_num_timesteps=False, so pass only the remaining budget.
            total_timesteps=total_timesteps - start,
            callback=callback,
            reset_num_timesteps=False,
            progress_bar=False,
        )
    except KeyboardInterrupt:
        print("[V11] stop requested; saving the current model and Drive state")
    finally:
        if device.startswith("cuda") and torch.cuda.is_available():
            torch.cuda.synchronize()
        elapsed = max(1e-6, time.perf_counter() - started)
        trained_steps = int(model.num_timesteps) - start
        try:
            callback.save_and_sync()
        finally:
            vec_env.close()

    print(f"[V11] saved at {int(model.num_timesteps):,}; this run added {trained_steps:,} steps")
    if args.profile_run:
        peak_vram_mb = torch.cuda.max_memory_allocated() / (1024.0 * 1024.0) if device.startswith("cuda") else 0.0
        print(f"PROFILE_RESULT steps_per_second={trained_steps / elapsed:.3f} max_vram_mb={peak_vram_mb:.1f}")


if __name__ == "__main__":
    main()
