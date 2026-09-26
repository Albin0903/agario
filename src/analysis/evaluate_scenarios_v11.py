"""Evaluate one V11 checkpoint on fixed baseline and stress-test scenarios."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml

# Evaluation writes JSONL and does not need SB3's optional TensorBoard writer.
sys.modules["torch.utils.tensorboard"] = None

from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.utils import get_action_masks
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from src.env.gym_wrapper import AgarEnv
from src.training.policy_arch import custom_policy_objects
from src.training.telemetry import SplitKillAttributor


def _scenario_configs(base: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scenarios = {"standard": copy.deepcopy(base)}
    sparse = copy.deepcopy(base)
    food = sparse.setdefault("entities", {})
    food["num_pellets"] = max(1, int(food.get("num_pellets", 2000) * 0.5))
    scenarios["sparse_food_50pct"] = sparse

    pressure = copy.deepcopy(base)
    sim = pressure.setdefault("simulation", {})
    baseline_bots = int(sim.get("num_bots", 20))
    sim["num_bots"] = max(baseline_bots + 1, int(np.ceil(baseline_bots * 1.5)))
    scenarios["high_pressure_150pct_bots"] = pressure
    return scenarios


def _evaluate_episode(
    model, config: dict[str, Any], seed: int, split_kill_horizon: int, vec_normalize_path: str,
) -> dict[str, Any]:
    vec_env = DummyVecEnv([lambda: AgarEnv(config=config, seed=seed)])
    vec_env.seed(seed)
    env = VecNormalize.load(vec_normalize_path, vec_env)
    env.training = False
    env.norm_reward = False
    obs = env.reset()
    tracker = SplitKillAttributor(horizon=split_kill_horizon)
    steps = kills = pellets = split_actions = split_cells = ejects = 0
    resolved_with_kill = resolved_without_kill = 0
    peak = float(config.get("physics", {}).get("initial_player_mass", 20.0))
    reward_sum = reward_mass_sum = reward_peak_sum = 0.0
    info: dict[str, Any] = {}
    died = False
    started = time.perf_counter()
    while True:
        action_masks = get_action_masks(env)
        action, _ = model.predict(obs, deterministic=True, action_masks=action_masks)
        obs, reward, dones, infos = env.step(action)
        info = infos[0]
        steps += 1
        reward_sum += float(reward)
        reward_mass_sum += float(info.get("reward_mass", 0.0))
        reward_peak_sum += float(info.get("reward_peak", 0.0))
        peak = max(peak, float(info.get("peak_mass", 0.0)))
        step_kills = int(info.get("cells_eaten", 0))
        kills += step_kills
        pellets += int(info.get("pellets_eaten", 0))
        split_actions += int(bool(info.get("split_requested", False)))
        split_cells += int(info.get("splits", 0))
        ejects += int(info.get("ejects", 0))
        useful, wasteful = tracker.observe(
            bool(info.get("split_requested", False)), step_kills,
            done=bool(dones[0]),
        )
        resolved_with_kill += useful
        resolved_without_kill += wasteful
        if dones[0]:
            died = bool(info.get("died", False))
            break

    action_repeat = int(info.get("action_repeat", 3))
    tick_duration = float(info.get("tick_duration_seconds", 0.04))
    simulated_seconds = steps * action_repeat * tick_duration
    result = {
        "seed": int(seed),
        "died": died,
        "survived_to_time_limit": not died,
        "episode_steps": steps,
        "simulated_seconds": simulated_seconds,
        "final_mass": float(info.get("player_mass", 0.0)),
        "peak_mass": peak,
        "kills": kills,
        "pellets": pellets,
        "split_actions": split_actions,
        "split_cells": split_cells,
        "split_actions_with_kill_30": resolved_with_kill,
        "split_actions_without_kill_30": resolved_without_kill,
        "split_kill_rate_30": resolved_with_kill / max(1, resolved_with_kill + resolved_without_kill),
        "ejects": ejects,
        "reward_sum": reward_sum,
        "reward_mass_sum": reward_mass_sum,
        "reward_peak_sum": reward_peak_sum,
        "elapsed_seconds": time.perf_counter() - started,
    }
    env.close()
    return result


def evaluate_scenarios(
    checkpoint: str,
    env_config_path: str,
    checkpoint_step: int,
    vec_normalize_path: str,
    episodes_per_scenario: int = 3,
    seed_base: int = 90_000,
    split_kill_horizon: int = 30,
    evaluation_milestone: int = 0,
    output_jsonl: str = "checkpoints/v11/scenario_evaluations.jsonl",
) -> list[dict[str, Any]]:
    if episodes_per_scenario < 1:
        raise ValueError("episodes_per_scenario must be positive")
    with open(env_config_path, "r", encoding="utf-8") as handle:
        base_config = yaml.safe_load(handle) or {}
    model = MaskablePPO.load(
        checkpoint, device="cpu", tensorboard_log=None,
        custom_objects=custom_policy_objects(),
    )
    output = Path(output_jsonl)
    output.parent.mkdir(parents=True, exist_ok=True)
    completed: set[tuple[int, str, int]] = set()
    if output.is_file():
        with output.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    old = json.loads(line)
                    completed.add((int(old["checkpoint_step"]), str(old["scenario"]), int(old["seed"])))
                except (ValueError, KeyError, TypeError):
                    continue
    all_rows: list[dict[str, Any]] = []
    for scenario, config in _scenario_configs(base_config).items():
        rows = []
        for index in range(episodes_per_scenario):
            seed = seed_base + index
            key = (int(checkpoint_step), scenario, seed)
            if key in completed:
                continue
            row = _evaluate_episode(model, config, seed, split_kill_horizon, vec_normalize_path)
            row["split_kill_horizon_steps"] = int(split_kill_horizon)
            row.update({
                "version": "v11",
                "checkpoint_step": int(checkpoint_step),
                "evaluation_milestone": int(evaluation_milestone),
                "checkpoint": str(checkpoint),
                "scenario": scenario,
            })
            rows.append(row)
            all_rows.append(row)
            # Persist per episode so a stop during evaluation only repeats the
            # unfinished scenarios/seeds on the next trainer start.
            with output.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
        scenario_rows = []
        with output.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    saved_row = json.loads(line)
                except ValueError:
                    continue
                if (int(saved_row.get("checkpoint_step", -1)) == int(checkpoint_step)
                        and saved_row.get("scenario") == scenario):
                    scenario_rows.append(saved_row)
        if not scenario_rows:
            print(f"[V11 scenario {checkpoint_step:,} {scenario}] no completed episodes yet")
            continue
        peak_mean = float(np.mean([row["peak_mass"] for row in scenario_rows]))
        survival = float(np.mean([row["survived_to_time_limit"] for row in scenario_rows]))
        split_rate = float(np.mean([row["split_kill_rate_30"] for row in scenario_rows]))
        print(
            f"[V11 scenario {checkpoint_step:,} {scenario}] "
            f"peak={peak_mean:.1f} survival={survival:.0%} split_kill_30={split_rate:.0%}"
        )

    return all_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--checkpoint-step", type=int, required=True)
    parser.add_argument("--vec-normalize", required=True)
    parser.add_argument("--env-config", default="config/env_config.yaml")
    parser.add_argument("--episodes-per-scenario", type=int, default=5)
    parser.add_argument("--seed-base", type=int, default=90_000)
    parser.add_argument("--split-kill-horizon", type=int, default=30)
    parser.add_argument("--evaluation-milestone", type=int, default=0)
    parser.add_argument("--output-jsonl", default="checkpoints/v11/scenario_evaluations.jsonl")
    args = parser.parse_args()
    evaluate_scenarios(
        args.checkpoint, args.env_config, args.checkpoint_step,
        args.vec_normalize,
        args.episodes_per_scenario, args.seed_base, args.split_kill_horizon,
        args.evaluation_milestone, args.output_jsonl,
    )


if __name__ == "__main__":
    main()
