"""Windowed behavior/throughput telemetry and scheduled V11 evaluation."""

from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any, Optional

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import VecNormalize

from src.training.hardware import effective_cpu_count
from src.training.telemetry import SplitKillAttributor


class V11TrainingCallback(BaseCallback):
    def __init__(
        self,
        pool,
        save_dir: str,
        backup_dir: Optional[str],
        config: dict[str, Any],
        source_v10: Optional[str],
        metric_interval: int = 100_000,
        checkpoint_interval: int = 250_000,
        evaluation_interval: int = 1_000_000,
        evaluation_episodes: int = 5,
        split_kill_horizon: int = 30,
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
        self.evaluation_interval = max(1, int(evaluation_interval))
        self.evaluation_episodes = max(1, int(evaluation_episodes))
        self.split_kill_horizon = max(1, int(split_kill_horizon))
        self.pool_update_interval = max(1, int(pool_update_interval))
        self.min_pool_step = max(0, int(min_pool_step))
        self.drive_sync_seconds = max(1.0, float(drive_sync_seconds))
        self.next_metric = self.metric_interval
        self.next_evaluation = self.evaluation_interval
        self.last_checkpoint = 0
        self.last_pool_update = 0
        self.last_sync_at = time.monotonic()
        self.last_metric_at = time.monotonic()
        self.last_metric_step = 0
        self.metrics_path = self.save_dir / "metrics.jsonl"
        self.scenario_path = self.save_dir / "scenario_evaluations.jsonl"
        self.recent_returns = deque(maxlen=512)
        self.recent_episode_lengths = deque(maxlen=512)
        self.recent_peak_mass = deque(maxlen=4096)
        self.current_life_steps: list[int] = []
        self.split_trackers: list[SplitKillAttributor] = []
        self._reset_window()
        self.longest_episode_steps = 0
        self.longest_survived_episode_steps = 0
        self.longest_alive_streak_steps = 0
        self.seconds_per_decision = 0.0
        self.completed_episodes = 0
        self.completed_evaluation_milestones: set[int] = set()
        self.resume_evaluation_milestone = 0
        self._restore_lifetime_metrics()
        self._restore_evaluation_progress()
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def _reset_window(self) -> None:
        self.window: dict[str, float] = {
            "samples": 0, "mass_sum": 0.0, "peak_sum": 0.0, "peak_max": 0.0,
            "kills": 0, "pellets": 0, "split_actions": 0, "split_cells": 0,
            "eject_actions": 0, "ejected_cells": 0, "deaths": 0,
            "reward_mass": 0.0, "reward_peak": 0.0, "reward_death": 0.0,
            "new_peak_steps": 0, "mass_loss_steps": 0,
            "split_with_kill_30": 0, "split_without_kill_30": 0,
        }
        self.window_episode_lengths: list[int] = []
        self.window_survived: list[bool] = []
        self.window_returns: list[float] = []
        self.window_masses: list[float] = []
        self.window_peaks: list[float] = []

    def _restore_lifetime_metrics(self) -> None:
        if not self.metrics_path.is_file():
            return
        try:
            with self.metrics_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    row = json.loads(line)
                    self.longest_episode_steps = max(self.longest_episode_steps, int(row.get("longest_episode_steps", 0)))
                    self.longest_survived_episode_steps = max(
                        self.longest_survived_episode_steps,
                        int(row.get("longest_survived_episode_steps", 0)),
                    )
                    self.longest_alive_streak_steps = max(
                        self.longest_alive_streak_steps,
                        int(row.get("longest_alive_streak_steps", 0)),
                    )
                    self.seconds_per_decision = float(row.get("simulated_seconds_per_decision", self.seconds_per_decision))
                    self.completed_episodes = max(self.completed_episodes, int(row.get("completed_episodes_total", 0)))
        except (OSError, ValueError, TypeError):
            return

    def _restore_evaluation_progress(self) -> None:
        counts: dict[int, set[tuple[str, int]]] = {}
        if not self.scenario_path.is_file():
            return
        try:
            with self.scenario_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                        milestone = int(row.get("evaluation_milestone", 0))
                        if milestone > 0:
                            counts.setdefault(milestone, set()).add((str(row["scenario"]), int(row["seed"])))
                    except (ValueError, KeyError, TypeError):
                        continue
        except (OSError, ValueError, KeyError, TypeError):
            return
        expected = 3 * self.evaluation_episodes
        self.completed_evaluation_milestones = {
            milestone for milestone, rows in counts.items() if len(rows) >= expected
        }

    def prepare_resume(self, start_step: int) -> None:
        milestone = (int(start_step) // self.evaluation_interval) * self.evaluation_interval
        if milestone >= self.evaluation_interval and milestone not in self.completed_evaluation_milestones:
            self.resume_evaluation_milestone = milestone

    def _on_step(self) -> bool:
        infos = self.locals.get("infos", ())
        if not self.current_life_steps:
            self.current_life_steps = [0] * len(infos)
            self.split_trackers = [SplitKillAttributor(self.split_kill_horizon) for _ in infos]

        for env_index, info in enumerate(infos):
            if "player_mass" in info:
                mass = float(info["player_mass"])
                peak = float(info.get("peak_mass", mass))
                self.seconds_per_decision = (
                    float(info.get("action_repeat", 1))
                    * float(info.get("tick_duration_seconds", 0.0))
                )
                self.window["samples"] += 1
                self.window["mass_sum"] += mass
                self.window["peak_sum"] += peak
                self.window["peak_max"] = max(self.window["peak_max"], peak)
                self.window_masses.append(mass)
                self.window_peaks.append(peak)
                self.recent_peak_mass.append(peak)
                self.window["kills"] += int(info.get("cells_eaten", 0))
                self.window["pellets"] += int(info.get("pellets_eaten", 0))
                self.window["split_actions"] += int(bool(info.get("split_requested", False)))
                self.window["split_cells"] += int(info.get("splits", 0))
                self.window["eject_actions"] += int(bool(info.get("eject_requested", False)))
                self.window["ejected_cells"] += int(info.get("ejects", 0))
                self.window["deaths"] += int(bool(info.get("died", False)))
                self.window["reward_mass"] += float(info.get("reward_mass", 0.0))
                self.window["reward_peak"] += float(info.get("reward_peak", 0.0))
                self.window["reward_death"] += float(info.get("reward_death", 0.0))
                self.window["new_peak_steps"] += int(float(info.get("reward_peak", 0.0)) > 0.0)
                self.window["mass_loss_steps"] += int(float(info.get("reward_mass", 0.0)) < 0.0)

                self.current_life_steps[env_index] += 1
                life = self.current_life_steps[env_index]
                self.longest_alive_streak_steps = max(self.longest_alive_streak_steps, life)
                useful, wasteful = self.split_trackers[env_index].observe(
                    bool(info.get("split_requested", False)),
                    int(info.get("cells_eaten", 0)),
                    done=bool(info.get("died", False) or "episode" in info),
                )
                self.window["split_with_kill_30"] += useful
                self.window["split_without_kill_30"] += wasteful

                episode = info.get("episode")
                if episode:
                    episode_length = int(episode.get("l", life))
                    died = bool(info.get("died", False))
                    self.completed_episodes += 1
                    self.longest_episode_steps = max(self.longest_episode_steps, episode_length)
                    if not died:
                        self.longest_survived_episode_steps = max(
                            self.longest_survived_episode_steps, episode_length
                        )
                    self.recent_episode_lengths.append(episode_length)
                    self.recent_returns.append(float(episode.get("r", 0.0)))
                    self.window_episode_lengths.append(episode_length)
                    self.window_survived.append(not died)
                    self.window_returns.append(float(episode.get("r", 0.0)))
                    self.current_life_steps[env_index] = 0

        while self.num_timesteps >= self.next_metric:
            self._log_metrics()
            self.next_metric += self.metric_interval

        if self.num_timesteps - self.last_checkpoint >= self.checkpoint_interval:
            self.save_and_sync()
        elif self.backup_dir and time.monotonic() - self.last_sync_at >= self.drive_sync_seconds:
            self.save_and_sync()

        while self.num_timesteps >= self.next_evaluation:
            step = int(self.num_timesteps)
            if step != self.last_checkpoint:
                self.save_and_sync()
            if not self._run_scenario_evaluation(step, self.next_evaluation):
                raise RuntimeError(
                    f"Fixed-seed evaluation failed at milestone {self.next_evaluation:,}; "
                    "training was stopped after saving so the evaluation can be retried on resume."
                )
            self.next_evaluation += self.evaluation_interval
        return True

    def _on_training_start(self) -> None:
        if self.resume_evaluation_milestone:
            step = int(self.model.num_timesteps)
            milestone = self.resume_evaluation_milestone
            print(f"[V11 eval] resuming incomplete fixed-seed evaluation for milestone {milestone:,}")
            self.save_and_sync()
            if not self._run_scenario_evaluation(step, milestone):
                raise RuntimeError(
                    f"Could not complete resumed scenario evaluation for milestone {milestone:,}."
                )
            self.resume_evaluation_milestone = 0

    @staticmethod
    def _gpu_snapshot() -> dict[str, float | None]:
        try:
            import torch
            if not torch.cuda.is_available():
                return {"gpu_utilization_percent": None, "gpu_memory_used_mb": None,
                        "gpu_memory_allocated_mb": 0.0, "gpu_memory_peak_allocated_mb": 0.0}
            values: dict[str, float | None] = {
                "gpu_memory_allocated_mb": torch.cuda.memory_allocated() / (1024 ** 2),
                "gpu_memory_peak_allocated_mb": torch.cuda.max_memory_allocated() / (1024 ** 2),
                "gpu_utilization_percent": None,
                "gpu_memory_used_mb": None,
            }
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=1.5, check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                utilization, memory = result.stdout.strip().splitlines()[0].split(",")
                values["gpu_utilization_percent"] = float(utilization.strip())
                values["gpu_memory_used_mb"] = float(memory.strip())
            return values
        except Exception:
            return {"gpu_utilization_percent": None, "gpu_memory_used_mb": None,
                    "gpu_memory_allocated_mb": None, "gpu_memory_peak_allocated_mb": None}

    def _log_metrics(self) -> None:
        now = time.monotonic()
        step_delta = int(self.num_timesteps) - self.last_metric_step
        elapsed = max(1e-6, now - self.last_metric_at)
        n = max(1, int(self.window["samples"]))
        completed = len(self.window_episode_lengths)
        split_resolved = self.window["split_with_kill_30"] + self.window["split_without_kill_30"]
        try:
            cpu_load_per_core = os.getloadavg()[0] / effective_cpu_count()
        except (AttributeError, OSError):
            cpu_load_per_core = None
        info: dict[str, Any] = {
            "version": "v11",
            "timesteps": int(self.num_timesteps),
            "window_steps": step_delta,
            "window_seconds": elapsed,
            "fps_window": step_delta / elapsed,
            "fps_sb3_global": float(self.logger.name_to_value.get("time/fps", 0.0)),
            "mass_mean": self.window["mass_sum"] / n,
            "mass_p50": float(np.percentile(self.window_masses, 50)) if self.window_masses else None,
            "mass_p90": float(np.percentile(self.window_masses, 90)) if self.window_masses else None,
            "peak_mass_mean": self.window["peak_sum"] / n,
            "peak_mass_max": self.window["peak_max"],
            "peak_mass_p50": float(np.percentile(self.window_peaks, 50)) if self.window_peaks else None,
            "peak_mass_p90": float(np.percentile(self.window_peaks, 90)) if self.window_peaks else None,
            "kills": int(self.window["kills"]),
            "kills_per_100k": self.window["kills"] * 100_000 / max(1, step_delta),
            "pellets": int(self.window["pellets"]),
            "pellets_per_100k": self.window["pellets"] * 100_000 / max(1, step_delta),
            "split_actions": int(self.window["split_actions"]),
            "split_cells": int(self.window["split_cells"]),
            "split_actions_with_kill_30": int(self.window["split_with_kill_30"]),
            "split_actions_without_kill_30": int(self.window["split_without_kill_30"]),
            "split_kill_rate_30": self.window["split_with_kill_30"] / max(1, split_resolved),
            "split_kill_horizon_steps": self.split_kill_horizon,
            "eject_actions": int(self.window["eject_actions"]),
            "ejected_cells": int(self.window["ejected_cells"]),
            "deaths": int(self.window["deaths"]),
            "death_rate_per_100k": self.window["deaths"] * 100_000 / max(1, step_delta),
            "new_peak_steps": int(self.window["new_peak_steps"]),
            "mass_loss_steps": int(self.window["mass_loss_steps"]),
            "split_outcomes_resolved": int(split_resolved),
            "completed_episodes": completed,
            "episode_steps_mean": float(np.mean(self.window_episode_lengths)) if completed else None,
            "episode_steps_p90": float(np.percentile(self.window_episode_lengths, 90)) if completed else None,
            "survival_rate": float(np.mean(self.window_survived)) if completed else None,
            "episode_return_mean": float(np.mean(self.window_returns)) if completed else None,
            "reward_mass_sum": self.window["reward_mass"],
            "reward_peak_sum": self.window["reward_peak"],
            "reward_death_sum": self.window["reward_death"],
            "longest_episode_steps": self.longest_episode_steps,
            "longest_episode_seconds": self.longest_episode_steps * self.seconds_per_decision,
            "longest_survived_episode_steps": self.longest_survived_episode_steps,
            "longest_survived_episode_seconds": self.longest_survived_episode_steps * self.seconds_per_decision,
            "longest_alive_streak_steps": self.longest_alive_streak_steps,
            "longest_alive_streak_seconds": self.longest_alive_streak_steps * self.seconds_per_decision,
            "simulated_seconds_per_decision": self.seconds_per_decision,
            "completed_episodes_total": self.completed_episodes,
            "pool_size": len(self.pool),
            "cpu_load_per_core": cpu_load_per_core,
            "recorded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **self._gpu_snapshot(),
        }
        with self.metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(info, sort_keys=True) + "\n")
        print(
            f"[V11 {self.num_timesteps:>10,}] mass={info['mass_mean']:6.1f} "
            f"peak={info['peak_mass_max']:7.1f} kills={info['kills']:4d} "
            f"split={info['split_actions']:4d} useful={info['split_actions_with_kill_30']:3d}/"
            f"{info['split_actions_without_kill_30']:3d} "
            f"lifeMax={self.longest_survived_episode_steps:4d} "
            f"survival={info['survival_rate'] if completed else float('nan'):.0%} "
            f"fps={info['fps_window']:6.1f} pool={len(self.pool)}"
        )
        self._reset_window()
        self.last_metric_at = now
        self.last_metric_step = int(self.num_timesteps)

    def _run_scenario_evaluation(self, step: int, milestone: int) -> bool:
        checkpoint = self.save_dir / f"ppo_step_{step}.zip"
        command = [
            sys.executable, "-u", "-m", "src.analysis.evaluate_scenarios_v11",
            "--checkpoint", str(checkpoint), "--checkpoint-step", str(step),
            "--vec-normalize", str(self.save_dir / f"vec_normalize_step_{step}.pkl"),
            "--env-config", "config/env_config.yaml",
            "--episodes-per-scenario", str(self.evaluation_episodes),
            "--split-kill-horizon", str(self.split_kill_horizon),
            "--evaluation-milestone", str(milestone),
            "--output-jsonl", str(self.scenario_path),
        ]
        print(f"[V11 eval] fixed-seed scenario suite at step {step:,} ({self.evaluation_episodes} seeds/scenario)")
        try:
            process = subprocess.Popen(command)
            try:
                return_code = process.wait()
            except KeyboardInterrupt:
                process.send_signal(signal.SIGINT)
                process.wait()
                raise
            finally:
                # Save completed episode rows even when an evaluation is
                # interrupted, so the next Colab session can skip them.
                if self.backup_dir and self.scenario_path.exists():
                    self._atomic_copy(self.scenario_path, self.backup_dir / self.scenario_path.name)
            if return_code:
                print(f"[V11 eval] failed (exit={return_code}); subprocess output is above.")
                return False
            self.completed_evaluation_milestones.add(milestone)
            if self.backup_dir and self.metrics_path.exists():
                self._atomic_copy(self.metrics_path, self.backup_dir / self.metrics_path.name)
            return True
        except OSError as exc:
            print(f"[V11 eval] could not launch fixed-seed suite: {exc}")
            return False

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
            score = float(np.mean(self.recent_peak_mass)) if self.recent_peak_mass else 0.0
            self.pool.add_checkpoint(str(step_path), score=score, tag=f"step_{step}")
            self.last_pool_update = step

        normalizer = self.model.get_vec_normalize_env()
        norm_path = self.save_dir / f"vec_normalize_step_{step}.pkl"
        norm_alias = self.save_dir / "vec_normalize.pkl"
        if isinstance(normalizer, VecNormalize):
            norm_tmp = self.save_dir / f"vec_normalize_step_{step}.tmp.pkl"
            normalizer.save(str(norm_tmp))
            os.replace(norm_tmp, norm_path)
            self._atomic_copy(norm_path, norm_alias)

        manifest = {
            "version": "v11", "timesteps": step, "checkpoint": "ppo_latest.zip",
            "step_checkpoint": step_name,
            "vec_normalize": norm_alias.name if norm_alias.exists() else None,
            "vec_normalize_checkpoint": norm_path.name if norm_path.exists() else None,
            "pool_state": "pool_state.json", "source_v10_checkpoint": self.source_v10,
            "n_envs": int(self.model.n_envs), "n_steps": int(self.model.n_steps),
            "batch_size": int(self.model.batch_size), "n_epochs": int(self.model.n_epochs),
            "device": str(self.model.device),
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
                self._atomic_copy(step_path, self.backup_dir / step_path.name)
                if norm_path.exists():
                    self._atomic_copy(norm_path, self.backup_dir / norm_path.name)
                    self._atomic_copy(norm_alias, self.backup_dir / norm_alias.name)
                if self.metrics_path.exists():
                    self._atomic_copy(self.metrics_path, self.backup_dir / self.metrics_path.name)
                if self.scenario_path.exists():
                    self._atomic_copy(self.scenario_path, self.backup_dir / self.scenario_path.name)
                if self.pool.state_path and os.path.exists(self.pool.state_path):
                    self._atomic_copy(Path(self.pool.state_path), self.backup_dir / "pool_state.json")
                # Publish mutable aliases and the manifest last. The manifest
                # points at immutable, same-step model and normalizer files.
                self._atomic_copy(latest, self.backup_dir / latest.name)
                self._atomic_copy(manifest_path, self.backup_dir / manifest_path.name)
                self.last_sync_at = time.monotonic()
                print(f"[V11 Drive] synced step {step:,}")
            except OSError as exc:
                print(f"[V11 Drive] sync failed at step {step:,}; local save is intact: {exc}")
        self.last_checkpoint = step

    def _on_training_end(self) -> None:
        return None
