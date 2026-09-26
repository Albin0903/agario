"""Concise metrics, atomic checkpoints, and Drive sync for V11 runs."""

from __future__ import annotations

import json
import os
import shutil
import time
from collections import deque
from pathlib import Path
from typing import Any, Optional

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import VecNormalize


class V11TrainingCallback(BaseCallback):
    def __init__(
        self,
        pool,
        save_dir: str,
        backup_dir: Optional[str],
        config: dict[str, Any],
        source_v10: Optional[str],
        metric_interval: int = 25_000,
        checkpoint_interval: int = 250_000,
        pool_update_interval: int = 250_000,
        min_pool_step: int = 200_000,
        drive_sync_seconds: float = 300.0,
    ):
        super().__init__(verbose=0)
        self.pool = pool
        self.save_dir = Path(save_dir)
        self.backup_dir = Path(backup_dir) if backup_dir else None
        self.config = config
        self.source_v10 = source_v10
        self.metric_interval = max(1, int(metric_interval))
        self.checkpoint_interval = max(1, int(checkpoint_interval))
        self.pool_update_interval = max(1, int(pool_update_interval))
        self.min_pool_step = max(0, int(min_pool_step))
        self.drive_sync_seconds = max(1.0, float(drive_sync_seconds))
        self.next_metric = self.metric_interval
        self.last_checkpoint = 0
        self.last_pool_update = 0
        self.last_sync_at = time.monotonic()
        self.mass = deque(maxlen=4096)
        self.peak = deque(maxlen=4096)
        self.episode_returns = deque(maxlen=256)
        self.metrics_path = self.save_dir / "metrics.jsonl"
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def _on_step(self) -> bool:
        for info in self.locals.get("infos", ()):
            if "player_mass" in info:
                self.mass.append(float(info["player_mass"]))
                self.peak.append(float(info.get("peak_mass", info["player_mass"])))
            episode = info.get("episode")
            if episode:
                self.episode_returns.append(float(episode.get("r", 0.0)))

        while self.num_timesteps >= self.next_metric:
            self._log_metrics()
            self.next_metric += self.metric_interval

        if self.num_timesteps - self.last_checkpoint >= self.checkpoint_interval:
            self.save_and_sync()
        elif self.backup_dir and time.monotonic() - self.last_sync_at >= self.drive_sync_seconds:
            self.save_and_sync()
        return True

    def _log_metrics(self) -> None:
        info = {
            "version": "v11",
            "timesteps": int(self.num_timesteps),
            "mass_mean": float(np.mean(self.mass)) if self.mass else None,
            "peak_mass_mean": float(np.mean(self.peak)) if self.peak else None,
            "episode_return_mean": float(np.mean(self.episode_returns)) if self.episode_returns else None,
            "fps": float(self.logger.name_to_value.get("time/fps", 0.0)),
            "pool_size": len(self.pool),
            "recorded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with self.metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(info, sort_keys=True) + "\n")
        print(
            f"[V11 {self.num_timesteps:>10,}] "
            f"mass={info['mass_mean'] if info['mass_mean'] is not None else 0.0:6.1f} "
            f"peak={info['peak_mass_mean'] if info['peak_mass_mean'] is not None else 0.0:6.1f} "
            f"fps={info['fps']:6.1f} pool={len(self.pool)}"
        )

    @staticmethod
    def _atomic_copy(source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        shutil.copy2(source, temporary)
        os.replace(temporary, target)

    def save_and_sync(self) -> None:
        step = int(self.model.num_timesteps)
        step_name = f"ppo_step_{step}.zip"
        latest = self.save_dir / "ppo_latest.zip"
        latest_tmp = self.save_dir / "ppo_latest.tmp.zip"
        self.model.save(str(latest_tmp))
        os.replace(latest_tmp, latest)

        step_path = self.save_dir / step_name
        self._atomic_copy(latest, step_path)

        if step >= self.min_pool_step and step - self.last_pool_update >= self.pool_update_interval:
            score = float(np.mean(self.peak)) if self.peak else 0.0
            self.pool.add_checkpoint(str(step_path), score=score, tag=f"step_{step}")
            self.last_pool_update = step

        normalizer = self.model.get_vec_normalize_env()
        norm_path = self.save_dir / "vec_normalize.pkl"
        if isinstance(normalizer, VecNormalize):
            norm_tmp = self.save_dir / "vec_normalize.tmp.pkl"
            normalizer.save(str(norm_tmp))
            os.replace(norm_tmp, norm_path)

        manifest = {
            "version": "v11",
            "timesteps": step,
            "checkpoint": "ppo_latest.zip",
            "step_checkpoint": step_name,
            "vec_normalize": norm_path.name if norm_path.exists() else None,
            "pool_state": "pool_state.json",
            "source_v10_checkpoint": self.source_v10,
            "n_envs": int(self.model.n_envs),
            "n_steps": int(self.model.n_steps),
            "batch_size": int(self.model.batch_size),
            "n_epochs": int(self.model.n_epochs),
        }
        manifest_path = self.save_dir / "v11_manifest.json"
        manifest_tmp = self.save_dir / "v11_manifest.tmp.json"
        with manifest_tmp.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(manifest_tmp, manifest_path)

        if self.backup_dir:
            try:
                self._atomic_copy(latest, self.backup_dir / latest.name)
                self._atomic_copy(step_path, self.backup_dir / step_path.name)
                if norm_path.exists():
                    self._atomic_copy(norm_path, self.backup_dir / norm_path.name)
                if self.metrics_path.exists():
                    self._atomic_copy(self.metrics_path, self.backup_dir / self.metrics_path.name)
                if self.pool.state_path and os.path.exists(self.pool.state_path):
                    self._atomic_copy(Path(self.pool.state_path), self.backup_dir / "pool_state.json")
                # Publish the manifest last; it commits the files above.
                self._atomic_copy(manifest_path, self.backup_dir / manifest_path.name)
                self.last_sync_at = time.monotonic()
                print(f"[V11 Drive] synced step {step:,}")
            except OSError as exc:
                print(f"[V11 Drive] sync failed at step {step:,}; local save is intact: {exc}")
        self.last_checkpoint = step

    def _on_training_end(self) -> None:
        # The trainer's finally block performs one final atomic save for normal
        # completion, KeyboardInterrupt, and callback exceptions alike.
        return None
