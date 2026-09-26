"""Measure one complete AgarEnv step, including observations and all bot actions."""

from __future__ import annotations

import argparse
import json
import time

from src.env.gym_wrapper import AgarEnv


def profile_env(steps: int = 2_000, warmup_steps: int = 200, seed: int = 42) -> dict:
    if steps < 1 or warmup_steps < 0:
        raise ValueError("steps must be positive and warmup_steps nonnegative")
    env = AgarEnv(seed=seed)
    env.action_space.seed(seed)
    obs, _ = env.reset(seed=seed)
    started = None
    total_reward = 0.0
    completed = 0
    peak_mass = float(env.initial_player_mass)
    for index in range(warmup_steps + steps):
        action = env.action_space.sample()
        if index == warmup_steps:
            started = time.perf_counter()
        obs, reward, terminated, truncated, info = env.step(action)
        if index >= warmup_steps:
            completed += 1
            total_reward += float(reward)
            peak_mass = max(peak_mass, float(info.get("peak_mass", 0.0)))
        if terminated or truncated:
            obs, _ = env.reset()
    elapsed = max(1e-9, time.perf_counter() - (started or time.perf_counter()))
    result = {
        "steps": completed,
        "warmup_steps": warmup_steps,
        "elapsed_seconds": elapsed,
        "environment_steps_per_second": completed / elapsed,
        "physics_ticks_per_second": completed * env.action_repeat / elapsed,
        "action_repeat": env.action_repeat,
        "simulated_seconds": completed * env.action_repeat * env.engine.tick_duration_seconds,
        "mean_reward": total_reward / max(1, completed),
        "peak_mass": peak_mass,
        "num_bots": env.num_bots,
        "num_pellets": env.engine.num_pellets,
    }
    env.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=2_000)
    parser.add_argument("--warmup-steps", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = profile_env(args.steps, args.warmup_steps, args.seed)
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(
            f"AgarEnv: {result['environment_steps_per_second']:.1f} decisions/s "
            f"({result['physics_ticks_per_second']:.1f} physics ticks/s), "
            f"{result['num_bots']} bots, {result['num_pellets']} pellets"
        )
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
