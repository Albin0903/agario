"""Repeatable headless engine throughput and phase profiler."""

from __future__ import annotations

import argparse
import json
import math
import time

import numpy as np

from src.env.agar_engine import AgarEngine


def profile_engine(
    steps: int = 2_000,
    warmup_steps: int = 250,
    players: int = 20,
    cells_per_player: int = 2,
    pellets: int = 2_000,
    viruses: int = 8,
    seed: int = 42,
) -> dict:
    if steps < 1 or warmup_steps < 0 or players < 1:
        raise ValueError("steps and players must be positive; warmup_steps cannot be negative")
    if cells_per_player not in (1, 2, 4, 8, 16):
        raise ValueError("cells_per_player must be a power of two from 1 through the 16-cell cap")

    engine = AgarEngine(
        width=1400.0,
        height=1400.0,
        num_pellets=pellets,
        num_viruses=viruses,
        seed=seed,
        remerge_cooldown_ticks=max(600, steps + warmup_steps + 1),
    )
    engine.profile_enabled = True
    target_mass = 80.0 * cells_per_player
    for player_id in range(players):
        engine.spawn_player(player_id, initial_mass=target_mass)
        while len(engine.get_player_cells(player_id)) < cells_per_player:
            engine._execute_split(player_id, (1.0, 0.0))

    phase_seconds: dict[str, float] = {}
    wall_engine_seconds = 0.0
    player_ids = list(range(players))
    for index in range(warmup_steps + steps):
        actions = {
            pid: np.asarray(
                [math.cos(index * 0.01 + pid), math.sin(index * 0.01 + pid), -1.0],
                dtype=np.float32,
            )
            for pid in player_ids
        }
        started = time.perf_counter()
        engine.step(actions)
        elapsed = time.perf_counter() - started
        if index >= warmup_steps:
            wall_engine_seconds += elapsed
            for name, phase_time in engine.last_profile.items():
                phase_seconds[name] = phase_seconds.get(name, 0.0) + phase_time

    profiled_phase_seconds = sum(phase_seconds.values())
    return {
        "steps": steps,
        "players": players,
        "cells_per_player_initial": cells_per_player,
        "pellets": pellets,
        "viruses": viruses,
        "warmup_steps": warmup_steps,
        "measured_engine_seconds": wall_engine_seconds,
        "phase_coverage_percent": 100.0 * profiled_phase_seconds / wall_engine_seconds if wall_engine_seconds else 0.0,
        "measured_engine_steps_per_second": steps / wall_engine_seconds if wall_engine_seconds else 0.0,
        "phase_seconds": phase_seconds,
        "phase_percent": {
            name: 100.0 * elapsed / wall_engine_seconds
            for name, elapsed in sorted(phase_seconds.items(), key=lambda pair: pair[1], reverse=True)
            if wall_engine_seconds
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=2_000)
    parser.add_argument("--warmup-steps", type=int, default=250)
    parser.add_argument("--players", type=int, default=20)
    parser.add_argument("--cells-per-player", type=int, default=2)
    parser.add_argument("--pellets", type=int, default=2_000)
    parser.add_argument("--viruses", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", action="store_true", help="Print only machine-readable JSON")
    args = parser.parse_args()
    result = profile_engine(
        steps=args.steps,
        warmup_steps=args.warmup_steps,
        players=args.players,
        cells_per_player=args.cells_per_player,
        pellets=args.pellets,
        viruses=args.viruses,
        seed=args.seed,
    )
    if args.json:
        print(json.dumps(result, sort_keys=True))
        return
    print(f"Engine: {result['measured_engine_steps_per_second']:.1f} ticks/s; "
          f"profile coverage {result['phase_coverage_percent']:.1f}%")
    for name, percent in result["phase_percent"].items():
        print(f"{name:24s}: {percent:6.2f}%")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
