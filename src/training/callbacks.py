"""Callbacks for PPO training, checkpoint saving, metric tracking, and self-play updates."""

from __future__ import annotations
import os
import json
import shutil
import subprocess
import time
from collections import deque
from typing import Dict, Any, Optional
import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

from src.training.self_play_pool import SelfPlayPool


class SelfPlayCallback(BaseCallback):
    """Callback managing periodic checkpointing, self-play pool expansion, and metric logging."""

    def __init__(
        self,
        pool: SelfPlayPool,
        update_interval_steps: int = 500_000,
        save_dir: str = "checkpoints/ppo",
        log_interval_steps: int = 10_000,
        min_pool_step: int = 200_000,
        backup_dir: Optional[str] = None,
        ent_coef_start: float = 0.005,
        ent_coef_end: float = 0.001,
        verbose: int = 1,
    ):
        super().__init__(verbose)
        self.pool = pool
        self.update_interval_steps = update_interval_steps
        self.save_dir = save_dir
        self.log_interval_steps = log_interval_steps
        self.min_pool_step = min_pool_step
        self.backup_dir = backup_dir
        self.ent_coef_start = float(ent_coef_start)
        self.ent_coef_end = float(ent_coef_end)
        self.started_at = time.perf_counter()

        self.last_pool_update = 0
        self.last_log_step = 0

        # Rolling statistics buffers (window = 100)
        self.rolling_rewards = deque(maxlen=100)
        self.rolling_masses = deque(maxlen=100)
        self.rolling_peaks = deque(maxlen=100)
        self.rolling_cells_eaten = deque(maxlen=100)
        self.rolling_pellets_eaten = deque(maxlen=100)
        self.rolling_splits = deque(maxlen=100)
        self.rolling_lengths = deque(maxlen=100)

        os.makedirs(self.save_dir, exist_ok=True)
        self.pool.sync_from_disk()

    def _init_callback(self) -> None:
        super()._init_callback()
        self.last_pool_update = self.num_timesteps
        self.last_log_step = self.num_timesteps

    def _on_step(self) -> bool:
        progress = float(np.clip(getattr(self.model, "_current_progress_remaining", 1.0), 0.0, 1.0))
        setattr(
            self.model,
            "ent_coef",
            self.ent_coef_end + (self.ent_coef_start - self.ent_coef_end) * progress,
        )

        # Extract environment step information
        infos = self.locals.get("infos", [])
        dones = self.locals.get("dones", [])
        rewards = self.locals.get("rewards", [])

        for i, info in enumerate(infos):
            if isinstance(info, dict):
                mass = info.get("player_mass", None)
                if mass is not None:
                    self.rolling_masses.append(float(mass))
                peak = info.get("peak_mass", None)
                if peak is not None:
                    self.rolling_peaks.append(float(peak))
                self.rolling_splits.append(info.get("splits", 0))

            if i < len(dones) and dones[i]:
                # Use VecMonitor's episode info for accurate total episode reward
                episode_info = info.get("episode", None) if isinstance(info, dict) else None
                if episode_info is not None:
                    self.rolling_rewards.append(float(episode_info["r"]))
                    self.rolling_lengths.append(int(episode_info["l"]))
                elif i < len(rewards):
                    self.rolling_rewards.append(float(rewards[i]))

                if isinstance(info, dict):
                    self.rolling_pellets_eaten.append(info.get("episode_pellets", 0))
                    self.rolling_cells_eaten.append(info.get("episode_kills", 0))

        # Log rolling statistics
        if (self.num_timesteps - self.last_log_step) >= self.log_interval_steps:
            self.last_log_step = self.num_timesteps
            self.pool.sync_from_disk()
            avg_mass = float(np.mean(self.rolling_masses)) if self.rolling_masses else 0.0
            avg_peak = float(np.mean(self.rolling_peaks)) if self.rolling_peaks else avg_mass
            avg_rew = float(np.mean(self.rolling_rewards)) if self.rolling_rewards else 0.0
            avg_eaten = float(np.mean(self.rolling_cells_eaten)) if self.rolling_cells_eaten else 0.0
            avg_pellets = float(np.mean(self.rolling_pellets_eaten)) if self.rolling_pellets_eaten else 0.0

            if self.logger is not None:
                self.logger.record("agar/avg_mass", avg_mass)
                self.logger.record("agar/peak_mass", avg_peak)
                self.logger.record("agar/avg_reward", avg_rew)
                self.logger.record("agar/cells_eaten", avg_eaten)
                self.logger.record("agar/pellets_eaten", avg_pellets)
                self.logger.record("agar/self_play_pool_size", len(self.pool))
                self.logger.record(
                    "agar/steps_per_second",
                    self.num_timesteps / max(1e-6, time.perf_counter() - self.started_at),
                )
                try:
                    import torch
                    if torch.cuda.is_available():
                        self.logger.record("agar/gpu_memory_allocated_gb", torch.cuda.memory_allocated() / 2**30)
                        self.logger.record("agar/gpu_memory_reserved_gb", torch.cuda.memory_reserved() / 2**30)
                except ImportError:
                    pass
                if hasattr(self.model, "lr_schedule"):
                    progress = getattr(self.model, "_current_progress_remaining", 1.0)
                    self.logger.record("agar/learning_rate", float(self.model.lr_schedule(progress)))
                for key in (
                    "train/approx_kl",
                    "train/clip_fraction",
                    "train/entropy_loss",
                    "train/policy_gradient_loss",
                    "train/value_loss",
                    "train/explained_variance",
                ):
                    if key in self.logger.name_to_value:
                        self.logger.record(f"agar/{key[6:]}", self.logger.name_to_value[key])

            if self.verbose > 0:
                print(
                    f"[Step {self.num_timesteps:8d}] "
                    f"Mass: {avg_mass:5.1f} (Peak: {avg_peak:5.1f}) | "
                    f"Ep Rew: {avg_rew:7.2f} | "
                    f"Pellets/Ep: {avg_pellets:4.0f} | "
                    f"Kills/Ep: {avg_eaten:4.2f} | "
                    f"Pool: {len(self.pool)}"
                )

        # Trigger self-play checkpointing and pool update
        if (self.num_timesteps - self.last_pool_update) >= self.update_interval_steps:
            self.last_pool_update = self.num_timesteps
            checkpoint_filename = f"ppo_step_{self.num_timesteps}.zip"
            checkpoint_path = os.path.join(self.pool.history_dir, checkpoint_filename)

            self.model.save(checkpoint_path)
            # Also maintain latest in save_dir
            latest_path = os.path.join(self.save_dir, "ppo_latest.zip")
            self.model.save(latest_path)

            # Save VecNormalize stats if active
            vec_norm = getattr(self.model, "get_vec_normalize_env", lambda: None)()
            vn_path = os.path.join(self.save_dir, "vec_normalize.pkl")
            if vec_norm is not None:
                vec_norm.save(vn_path)

            manifest_path = os.path.join(self.save_dir, "v10_manifest.json")
            manifest = {
                "version": "v10",
                "timesteps": int(self.num_timesteps),
                "checkpoint": checkpoint_filename,
                "vec_normalize": "vec_normalize.pkl" if vec_norm is not None else None,
                "pool_state": "pool_state.json",
                "seed": getattr(self.model, "seed", None),
                "git_revision": self._git_revision(),
            }
            temporary_manifest = f"{manifest_path}.tmp"
            with open(temporary_manifest, "w", encoding="utf-8") as handle:
                json.dump(manifest, handle, indent=2)
            os.replace(temporary_manifest, manifest_path)

            if self.backup_dir:
                try:
                    os.makedirs(self.backup_dir, exist_ok=True)
                    self._mirror_file(checkpoint_path, os.path.join(self.backup_dir, checkpoint_filename))
                    self._mirror_file(latest_path, os.path.join(self.backup_dir, "ppo_latest.zip"))
                    if vec_norm is not None and os.path.exists(vn_path):
                        self._mirror_file(vn_path, os.path.join(self.backup_dir, "vec_normalize.pkl"))
                    self._mirror_file(manifest_path, os.path.join(self.backup_dir, "v10_manifest.json"))
                    if os.path.exists(self.pool.state_path):
                        self._mirror_file(self.pool.state_path, os.path.join(self.backup_dir, "pool_state.json"))
                    if self.verbose > 0:
                        print(f"📁 [Drive Backup] Checkpoint mirrored to {self.backup_dir}")
                except Exception as e:
                    print(f"⚠️ [Drive Backup] Warning: Could not mirror checkpoint: {e}")

            if self.verbose > 0:
                print(f"[SelfPlayCallback] Checkpoint saved: {checkpoint_path}")

            if self.num_timesteps >= self.min_pool_step:
                score = float(np.mean(self.rolling_masses)) if self.rolling_masses else 0.0
                self.pool.add_checkpoint(checkpoint_path, score=score, tag=f"step_{self.num_timesteps}")
                if self.backup_dir and os.path.exists(self.pool.state_path):
                    try:
                        self._mirror_file(self.pool.state_path, os.path.join(self.backup_dir, "pool_state.json"))
                    except OSError as exc:
                        print(f"⚠️ [Drive Backup] Warning: Could not mirror pool state: {exc}")
            else:
                if self.verbose > 0:
                    print(f"[SelfPlayCallback] Skipping pool entry (warm-up phase until step {self.min_pool_step:,})")

        return True

    @staticmethod
    def _git_revision() -> Optional[str]:
        try:
            return subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
            ).strip()
        except (OSError, subprocess.SubprocessError):
            return None

    @staticmethod
    def _mirror_file(source: str, destination: str) -> None:
        temporary = f"{destination}.tmp"
        shutil.copy2(source, temporary)
        if os.path.getsize(temporary) != os.path.getsize(source):
            os.remove(temporary)
            raise IOError(f"Incomplete backup copy: {source}")
        os.replace(temporary, destination)

