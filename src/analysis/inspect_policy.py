"""Diagnostic and Policy Inspection Tool for AGAR-RL Agents.

Analyzes policy weights, logits, decision entropy, and runs tactical probe scenarios:
1. Foraging Response: Vector alignment towards food.
2. Predator Evasion: Reaction to threatening large cells.
3. Prey Hunting & Split Trigger: Response when prey is in strike zone vs open space.
4. Multi-Cell & Remerge Diagnostics: Behavior when split into subcells.
5. Rollout Telemetry: Distribution of actions across a live episode.

Usage:
    python src/analysis/inspect_policy.py --model checkpoints/ppo/ppo_latest.zip
    python src/analysis/inspect_policy.py --model /content/drive/MyDrive/agario_rl_backup_v5/ppo_latest.zip
"""

from __future__ import annotations
import os
import sys
import math
import argparse
from typing import Dict, Any, List, Tuple
import numpy as np
import yaml
import torch

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from stable_baselines3 import PPO
from src.env.gym_wrapper import AgarEnv, mass_to_radius


def load_yaml(path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def get_policy_action_probs(model: PPO, obs: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Query actor head to extract probability distributions for angles (24) and triggers (3)."""
    with torch.no_grad():
        obs_tensor = torch.as_tensor(obs, device=model.device).float().unsqueeze(0)
        dist = model.policy.get_distribution(obs_tensor)

        # MultiCategorical distribution has multiple categorical sub-distributions
        if hasattr(dist, "distribution"):
            sub_dists = dist.distribution
            angle_probs = sub_dists[0].probs.cpu().numpy()[0]
            trig_probs = sub_dists[1].probs.cpu().numpy()[0]
        else:
            # Fallback for continuous or other heads
            angle_probs = np.ones(24) / 24.0
            trig_probs = np.array([1.0, 0.0, 0.0])
    return angle_probs, trig_probs


def probe_synthetic_scenarios(model: PPO, env: AgarEnv):
    """Evaluate policy logits on targeted synthetic game states."""
    print("\n" + "=" * 70)
    print("🔬 [PROBE 1] SYNTHETIC TACTICAL BEHAVIOR TESTS")
    print("=" * 70)

    # 1. Neutral State: No prey, no predator, just food ahead at 0 degrees
    obs_food = np.zeros(84, dtype=np.float32)
    obs_food[0] = np.tanh(50.0 / 500.0)  # Self mass = 50
    # Closest pellet at (dx=50, dy=0) -> angle 0 rad
    obs_food[4] = 1.0  # u_x
    obs_food[5] = 0.0  # u_y

    a_probs, t_probs = get_policy_action_probs(model, obs_food)
    best_ang_idx = int(np.argmax(a_probs))
    best_ang_deg = best_ang_idx * 15.0
    print(f"🍏 Scenario A: Food Foraging (Pellet directly at 0°)")
    print(f"   - Preferred Angle: {best_ang_deg:.1f}° (Prob: {a_probs[best_ang_idx]*100:.1f}%)")
    print(f"   - Split Probability: {t_probs[1]*100:.2f}% | Eject: {t_probs[2]*100:.2f}% | Idle: {t_probs[0]*100:.2f}%")

    # 2. Predator Danger: Giant cell at 0 degrees, distance 150 (Lethal Split Threat)
    obs_pred = np.zeros(84, dtype=np.float32)
    obs_pred[0] = np.tanh(50.0 / 500.0)  # Self mass = 50
    # Predator 1: dx=150, dy=0, mass=350 (7x bigger, lethal split threat)
    obs_pred[44] = 150.0 / 600.0  # dx / R
    obs_pred[45] = 0.0            # dy / R
    obs_pred[46] = float(np.tanh(math.log(350.0 / 50.0)))  # threat level ~0.96
    obs_pred[47] = 0.0

    a_probs, t_probs = get_policy_action_probs(model, obs_pred)
    best_ang_idx = int(np.argmax(a_probs))
    best_ang_deg = best_ang_idx * 15.0
    print(f"\n🚨 Scenario B1: Lethal Predator Threat (Huge predator at 0°, 150m ahead, 7.0x mass)")
    print(f"   - Preferred Angle: {best_ang_deg:.1f}° (Ideal evasion: ~180°)")
    print(f"   - Evasion Alignment: {'✅ Fleeing correctly' if 135 <= best_ang_deg <= 225 else '⚠️ Ineffective evasion'}")
    print(f"   - Split Probability: {t_probs[1]*100:.2f}% (Panic split?) | Idle: {t_probs[0]*100:.2f}%")

    # 2b. Harmless Rival: Cell at 0 degrees, distance 150, mass 60 (1.2x bigger, cannot split-kill)
    obs_rival = np.zeros(84, dtype=np.float32)
    obs_rival[0] = np.tanh(50.0 / 500.0)
    obs_rival[44] = 150.0 / 600.0
    obs_rival[45] = 0.0
    obs_rival[46] = float(np.tanh(math.log(60.0 / 50.0)))  # harmless rival ~0.18
    obs_rival[47] = 0.0

    a_probs_r, t_probs_r = get_policy_action_probs(model, obs_rival)
    best_ang_idx_r = int(np.argmax(a_probs_r))
    best_ang_deg_r = best_ang_idx_r * 15.0
    print(f"\n🛡️ Scenario B2: Harmless Rival (Enemy 1.2x mass at 0°, cannot split-kill)")
    print(f"   - Preferred Angle: {best_ang_deg_r:.1f}°")
    print(f"   - Split Probability: {t_probs_r[1]*100:.2f}% ({'✅ Calm (No panic split)' if t_probs_r[1] < 0.10 else '⚠️ Unnecessary panic split'}) | Idle: {t_probs_r[0]*100:.2f}%")

    # 3. Prey Opportunity: Smaller bot right in front at 0 degrees, distance 120 (Strike Zone!)
    # Self mass = 120, Prey mass = 50 -> split half = 60 > 1.15 * 50 = 57.5 (Viable split strike!)
    obs_prey = np.zeros(84, dtype=np.float32)
    obs_prey[0] = np.tanh(120.0 / 500.0)  # Self mass = 120
    obs_prey[24] = 120.0 / 600.0  # dx / R
    obs_prey[25] = 0.0            # dy / R
    obs_prey[26] = float(np.tanh(math.log(50.0 / 120.0)))  # edible prey ~ -0.71
    obs_prey[27] = 0.0

    a_probs, t_probs = get_policy_action_probs(model, obs_prey)
    best_ang_idx = int(np.argmax(a_probs))
    best_ang_deg = best_ang_idx * 15.0
    print(f"\n🎯 Scenario C: Prey Opportunity (Small prey at 0°, distance 120 in strike zone, split viable)")
    print(f"   - Preferred Angle: {best_ang_deg:.1f}° (Target is 0°)")
    print(f"   - SPLIT ATTACK PROBABILITY: {t_probs[1]*100:.2f}% (Needs to be > 30% for aggressive hunting)")
    print(f"   - Move/Idle Probability:    {t_probs[0]*100:.2f}%")
    if t_probs[1] < 0.05:
        print("   ⚠️ DIAGNOSIS: Policy suffers from 'Pacifist/Vegetarian syndrome'. It refuses to split on prey!")
    else:
        print("   ✅ Hunting split instinct detected!")

    # 4. Multi-cell / Fragmented state
    obs_split = np.zeros(84, dtype=np.float32)
    obs_split[0] = np.tanh(100.0 / 500.0)
    obs_split[3] = 4.0 / 16.0  # 4 subcells active!
    obs_split[83] = 100.0 / 300.0  # remerge cooldown remaining

    a_probs, t_probs = get_policy_action_probs(model, obs_split)
    print(f"\n🧩 Scenario D: Multi-Cell State (4 subcells currently split)")
    print(f"   - Additional Split Probability: {t_probs[1]*100:.2f}%")
    print(f"   - Idle / Move Probability:     {t_probs[0]*100:.2f}%")
    if t_probs[1] > 0.15:
        print("   ⚠️ DIAGNOSIS: Policy tends to over-split even when already fragmented!")


def probe_live_simulation(model: PPO, env: AgarEnv, num_steps: int = 1500):
    """Run an evaluation episode and log combat and movement telemetry."""
    print("\n" + "=" * 70)
    print(f"🎮 [PROBE 2] LIVE MATCH TELEMETRY ({num_steps} STEPS)")
    print("=" * 70)

    obs, info = env.reset(seed=123)
    splits_count = 0
    splits_on_prey = 0
    splits_on_empty = 0
    cells_eaten_total = 0
    pellets_eaten_total = 0
    peak_mass = 20.0
    subcell_counts = []
    angle_counts = np.zeros(24, dtype=int)
    trigger_counts = np.zeros(3, dtype=int)

    for step in range(num_steps):
        action, _ = model.predict(obs, deterministic=False)
        angle_idx = int(action[0])
        trig_idx = int(action[1])

        angle_counts[angle_idx] += 1
        trigger_counts[trig_idx] += 1

        # Check if split was triggered and what was in front
        if trig_idx == 1:
            splits_count += 1
            # Check prey observation slice: dx, dy of prey 1
            prey_dx = obs[24]
            prey_dy = obs[25]
            prey_dist = math.hypot(prey_dx, prey_dy)
            if prey_dist > 0.001 and prey_dist < 0.4:
                splits_on_prey += 1
            else:
                splits_on_empty += 1

        obs, reward, terminated, truncated, info = env.step(action)
        cells_eaten_total += info.get("cells_eaten", 0)
        pellets_eaten_total += info.get("pellets_eaten", 0)
        curr_mass = float(info.get("player_mass", 20.0))
        if curr_mass > peak_mass:
            peak_mass = curr_mass

        subcells = info.get("num_subcells", 1)
        subcell_counts.append(subcells)

        if terminated or truncated:
            obs, info = env.reset()

    total_trig = max(1, int(np.sum(trigger_counts)))
    print(f"📊 Match Statistics over {num_steps} steps:")
    print(f"   - Peak Mass Reached:       {peak_mass:.1f}")
    print(f"   - Pellets Eaten:           {pellets_eaten_total}")
    print(f"   - Opponent Cells Consumed: {cells_eaten_total} (Kills)")
    print(f"   - Total Splits Fired:      {splits_count}")
    print(f"     • Splits aimed at prey:  {splits_on_prey} ({(splits_on_prey/max(1, splits_count))*100:.1f}%)")
    print(f"     • Splits in empty space: {splits_on_empty} ({(splits_on_empty/max(1, splits_count))*100:.1f}%)")
    print(f"   - Average Subcells Count:  {np.mean(subcell_counts):.2f} (Max: {np.max(subcell_counts)})")
    print(f"   - Action Distribution:")
    print(f"     • Move/Idle: {trigger_counts[0]/total_trig*100:.1f}%")
    print(f"     • Split:     {trigger_counts[1]/total_trig*100:.1f}%")
    print(f"     • Eject:     {trigger_counts[2]/total_trig*100:.1f}%")

    # Shannon Entropy of Angle Policy
    p_ang = angle_counts / max(1, np.sum(angle_counts))
    p_ang_nz = p_ang[p_ang > 0]
    entropy = -np.sum(p_ang_nz * np.log2(p_ang_nz))
    max_entropy = math.log2(24)
    print(f"   - Angle Exploration Entropy: {entropy:.2f} / {max_entropy:.2f} bits ({(entropy/max_entropy)*100:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="AGAR-RL Policy Inspector & Diagnostic Tool")
    parser.add_argument("--model", type=str, default=None, help="Path to PPO model .zip")
    parser.add_argument("--env-config", type=str, default="config/env_config.yaml", help="Path to env config")
    parser.add_argument("--steps", type=int, default=1500, help="Live simulation steps")
    args = parser.parse_args()

    # Auto-detect checkpoint if not provided
    model_path = args.model
    if not model_path or not os.path.exists(model_path):
        candidates = [
            "/content/drive/MyDrive/agario_rl_backup_v5/ppo_latest.zip",
            "checkpoints/ppo/ppo_latest.zip",
            "checkpoints/ppo/ppo_final.zip",
            "checkpoints/ppo/ppo_bc_pretrained.zip",
        ]
        import glob
        candidates.extend(glob.glob("/content/drive/MyDrive/agario_rl_backup_v5/*.zip"))
        candidates.extend(glob.glob("checkpoints/self_play_pool/*.zip"))
        model_path = next((c for c in candidates if os.path.exists(c)), None)

    if not model_path or not os.path.exists(model_path):
        print("❌ Error: No valid checkpoint found. Please specify --model <path>")
        sys.exit(1)

    print("=" * 70)
    print("🔎 AGAR-RL POLICY INSPECTOR & DIAGNOSTIC TOOL")
    print(f"   Model Target: {model_path} ({os.path.getsize(model_path)/(1024*1024):.2f} MB)")
    print("=" * 70)

    env_cfg = load_yaml(args.env_config)
    env = AgarEnv(config=env_cfg, seed=42)

    model = PPO.load(model_path, device="cpu")

    probe_synthetic_scenarios(model, env)
    probe_live_simulation(model, env, num_steps=args.steps)

    print("\n" + "=" * 70)
    print("💡 DIAGNOSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
