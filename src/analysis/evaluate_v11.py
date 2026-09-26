"""Evaluate and compare V11 checkpoints on the same fixed environment seeds."""

from __future__ import annotations

import argparse
import gc
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import yaml

# Evaluation does not need event logging. Avoid loading TensorBoard/TensorFlow.
sys.modules["torch.utils.tensorboard"] = None

from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.utils import get_action_masks
from stable_baselines3.common.vec_env import DummyVecEnv, VecMonitor, VecNormalize

from src.env.gym_wrapper import AgarEnv
from src.training.policy_arch import custom_policy_objects


def _stored_step(path: Path) -> int:
    try:
        with zipfile.ZipFile(path) as archive:
            data = archive.read("data").decode("utf-8", errors="replace")
        match = re.search(r'"num_timesteps"\s*:\s*(\d+)', data)
        return int(match.group(1)) if match else -1
    except (OSError, KeyError, zipfile.BadZipFile):
        return -1


def _discover_checkpoints(folder: Path, limit: int = 0) -> list[tuple[int, Path]]:
    if not folder.is_dir():
        raise FileNotFoundError(f"V11 checkpoint folder does not exist: {folder}")
    manifest = folder / "v11_manifest.json"
    if not manifest.is_file() or json.loads(manifest.read_text(encoding="utf-8")).get("version") != "v11":
        raise ValueError(f"Expected a V11 manifest in {folder}")
    by_step: dict[int, Path] = {}
    for path in [*folder.glob("ppo_step_*.zip"), folder / "ppo_latest.zip"]:
        if not path.is_file() or path.stat().st_size < 1024:
            continue
        step = _stored_step(path)
        if step < 0:
            continue
        previous = by_step.get(step)
        # Prefer the named immutable checkpoint over a rolling latest alias.
        if previous is None or (previous.name == "ppo_latest.zip" and path.name != "ppo_latest.zip"):
            by_step[step] = path
    checkpoints = sorted(((step, path) for step, path in by_step.items()), key=lambda row: row[0])
    if limit > 0 and len(checkpoints) > limit:
        indices = np.linspace(0, len(checkpoints) - 1, limit, dtype=np.int64)
        checkpoints = [checkpoints[int(i)] for i in sorted(set(indices))]
    if not checkpoints:
        raise FileNotFoundError(f"No readable V11 model checkpoints found in {folder}")
    return checkpoints


def _make_env(config: dict[str, Any], seed: int):
    def create():
        return AgarEnv(config=config, seed=seed)
    return create


def _evaluate_one(model, env, episodes: int, first_seed: int) -> list[dict[str, Any]]:
    rows = []
    for offset in range(episodes):
        seed = first_seed + offset
        env.seed(seed)
        obs = env.reset()
        mass_history = []
        peak_mass = 0.0
        cumulative_reward = 0.0
        length = 0
        died = False
        last_info: dict[str, Any] = {}
        while True:
            action_masks = get_action_masks(env)
            actions, _ = model.predict(obs, deterministic=True, action_masks=action_masks)
            obs, rewards, dones, infos = env.step(actions)
            info = infos[0]
            last_info = info
            length += 1
            cumulative_reward += float(rewards[0])
            mass_history.append(float(info.get("player_mass", 0.0)))
            peak_mass = max(peak_mass, float(info.get("peak_mass", 0.0)))
            if dones[0]:
                died = bool(info.get("died", False))
                break
        rows.append({
            "seed": seed,
            "final_mass": float(last_info.get("player_mass", 0.0)),
            "peak_mass": peak_mass,
            "survived_to_time_limit": not died,
            "died": died,
            "episode_steps": length,
            "simulated_seconds": (
                length
                * float(last_info.get("action_repeat", 3))
                * float(last_info.get("tick_duration_seconds", 0.04))
            ),
            "episode_reward": cumulative_reward,
            "mass_trace_mean": float(np.mean(mass_history)) if mass_history else 0.0,
            "pellets_eaten": int(last_info.get("episode_pellets", 0)),
            "cells_eaten": int(last_info.get("episode_kills", 0)),
        })
    return rows


def evaluate_checkpoints(
    checkpoint_dir: str,
    env_config_path: str = "config/env_config.yaml",
    episodes: int = 5,
    seed: int = 10_000,
    limit_checkpoints: int = 0,
    output_csv: str = "v11_evaluation.csv",
    output_json: str = "v11_evaluation.json",
    resume_results: bool = True,
) -> list[dict[str, Any]]:
    folder = Path(checkpoint_dir)
    checkpoints = _discover_checkpoints(folder, limit_checkpoints)
    with open(env_config_path, "r", encoding="utf-8") as handle:
        env_config = yaml.safe_load(handle) or {}
    norm_path = folder / "vec_normalize.pkl"
    if not norm_path.is_file():
        raise FileNotFoundError(f"V11 VecNormalize statistics not found: {norm_path}")

    vec_env = DummyVecEnv([_make_env(env_config, seed)])
    vec_env = VecMonitor(vec_env)
    vec_env = VecNormalize.load(str(norm_path), vec_env)
    vec_env.training = False
    vec_env.norm_reward = False

    results: list[dict[str, Any]] = []
    results_path = Path(output_json)
    if resume_results and results_path.is_file():
        try:
            prior = json.loads(results_path.read_text(encoding="utf-8"))
            if isinstance(prior, list):
                valid_steps = {step for step, _ in checkpoints}
                results = [row for row in prior if int(row.get("checkpoint_step", -1)) in valid_steps]
        except (OSError, ValueError, TypeError):
            results = []
    completed = {
        (int(row["checkpoint_step"]), int(row["seed"]))
        for row in results
        if "checkpoint_step" in row and "seed" in row
    }
    for step, path in checkpoints:
        pending_seeds = [
            seed + offset
            for offset in range(episodes)
            if (step, seed + offset) not in completed
        ]
        if not pending_seeds:
            print(f"[V11 eval {step:>10,}] already complete; skipping")
            continue
        model = MaskablePPO.load(
            str(path), env=vec_env, device="cpu", tensorboard_log=None,
            custom_objects=custom_policy_objects(),
        )
        if not isinstance(model, MaskablePPO):
            raise TypeError(f"V11 checkpoint is not MaskablePPO: {path}")
        for eval_seed in pending_seeds:
            episode = _evaluate_one(model, vec_env, 1, eval_seed)[0]
            episode.update({"checkpoint_step": step, "checkpoint": path.name})
            results.append(episode)
            results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
            try:
                import pandas as pd
                pd.DataFrame(results).to_csv(output_csv, index=False)
            except ImportError:
                pass
            completed.add((step, eval_seed))
        this_checkpoint = [row for row in results if int(row["checkpoint_step"]) == step]
        mean_peak = float(np.mean([row["peak_mass"] for row in this_checkpoint]))
        mean_final = float(np.mean([row["final_mass"] for row in this_checkpoint]))
        survive = float(np.mean([row["survived_to_time_limit"] for row in this_checkpoint]))
        print(f"[V11 eval {step:>10,}] peak={mean_peak:7.1f} final={mean_final:7.1f} survival={survive:.0%}")
        del model
        gc.collect()

    vec_env.close()
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-dir", required=True)
    parser.add_argument("--env-config", default="config/env_config.yaml")
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument("--seed", type=int, default=10_000)
    parser.add_argument("--limit-checkpoints", type=int, default=0, help="0 evaluates every V11 checkpoint")
    parser.add_argument("--output-csv", default="v11_evaluation.csv")
    parser.add_argument("--output-json", default="v11_evaluation.json")
    parser.add_argument("--fresh", action="store_true", help="Ignore previous partial evaluation results")
    args = parser.parse_args()
    evaluate_checkpoints(
        args.checkpoint_dir,
        args.env_config,
        args.episodes,
        args.seed,
        args.limit_checkpoints,
        args.output_csv,
        args.output_json,
        not args.fresh,
    )


if __name__ == "__main__":
    main()
