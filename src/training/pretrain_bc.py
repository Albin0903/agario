"""Behavioral Cloning (BC) Warm-Start for AGAR-RL Policy.

Gathers expert demonstration trajectories from HeuristicBot and pre-trains
the Stable-Baselines3 PPO policy network via supervised cross-entropy.
This gives the agent a solid foundation (foraging, evasion, tactical splits)
before PPO reinforcement learning and self-play begin.
"""

from __future__ import annotations
import os
import sys
import math
import argparse
from typing import Dict, Any, Optional, Tuple
import numpy as np
import yaml
import torch
import torch.nn.functional as F
from torch.utils.data import TensorDataset, DataLoader

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from sb3_contrib import MaskablePPO
from src.env.gym_wrapper import AgarEnv, HeuristicBot
from src.training.policy_arch import LayerNormMaskablePolicy, build_policy_kwargs, wrap_action_masker


def load_yaml(path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def collect_demonstrations(
    num_samples: int = 25000,
    env_config: Optional[Dict[str, Any]] = None,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Gather expert (observation, angle_target, trigger_target) tuples from HeuristicBot."""
    print(f"[BC Pretrain] Collecting {num_samples:,} expert transitions from HeuristicBot...")
    env = AgarEnv(config=env_config, seed=seed)
    bot = HeuristicBot(player_id=env.learning_player_id, rng=np.random.default_rng(seed))

    obs_list = []
    angle_list = []
    trig_list = []

    obs, info = env.reset(seed=seed)
    samples_collected = 0

    while samples_collected < num_samples:
        raw_act = bot.get_action(env.engine)
        dx, dy = float(raw_act[0]), float(raw_act[1])
        theta = math.atan2(dy, dx) % (2.0 * math.pi)
        angle_idx = int(round(theta / (2.0 * math.pi / env.num_angles))) % env.num_angles
        trig = float(raw_act[2])
        trig_idx = 1 if trig > 0.6 else (2 if trig > 0.2 else 0)

        obs_list.append(obs.copy())
        angle_list.append(angle_idx)
        trig_list.append(trig_idx)
        samples_collected += 1

        discrete_act = np.array([angle_idx, trig_idx], dtype=np.int64)
        obs, reward, terminated, truncated, info = env.step(discrete_act)

        if terminated or truncated:
            obs, info = env.reset()

        if samples_collected % 5000 == 0:
            print(f"  [Collection] {samples_collected:,}/{num_samples:,} samples | Current Mass: {info.get('player_mass', 20):.0f}")

    return (
        np.array(obs_list, dtype=np.float32),
        np.array(angle_list, dtype=np.int64),
        np.array(trig_list, dtype=np.int64),
    )


def pretrain_policy(
    output_path: str = "checkpoints/ppo/ppo_bc_pretrained.zip",
    num_samples: int = 25000,
    epochs: int = 6,
    batch_size: int = 512,
    lr: float = 1e-3,
    config_path: str = "config/ppo_config.yaml",
    env_config_path: str = "config/env_config.yaml",
    device: str = "auto",
    seed: int = 42,
) -> str:
    """Pre-train PPO policy via behavioral cloning on expert demonstrations."""
    ppo_cfg = load_yaml(config_path)
    env_cfg = load_yaml(env_config_path)

    dev = "cuda" if (device == "auto" and torch.cuda.is_available()) else ("cpu" if device == "auto" else device)
    print("=" * 65)
    print("  AGAR-RL: Behavioral Cloning Warm-Start")
    print(f"  Device: {dev} | Samples: {num_samples:,} | Epochs: {epochs}")
    print("=" * 65)

    obs_np, angles_np, trigs_np = collect_demonstrations(
        num_samples=num_samples,
        env_config=env_cfg,
        seed=seed,
    )

    dataset = TensorDataset(
        torch.from_numpy(obs_np),
        torch.from_numpy(angles_np),
        torch.from_numpy(trigs_np),
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    # Instantiate SB3 PPO model matching training configuration
    dummy_env = wrap_action_masker(AgarEnv(config=env_cfg, seed=seed))
    policy_kwargs = build_policy_kwargs(ppo_cfg)

    model = MaskablePPO(
        policy=LayerNormMaskablePolicy,
        env=dummy_env,
        policy_kwargs=policy_kwargs,
        device=dev,
    )
    policy = model.policy
    policy.to(dev)
    policy.train()

    optimizer = torch.optim.Adam(policy.parameters(), lr=lr, weight_decay=1e-5)

    print(f"\n[BC Training] Optimizing policy across {len(loader)} mini-batches per epoch...")
    for epoch in range(1, epochs + 1):
        total_loss = 0.0
        correct_angles = 0
        correct_trigs = 0
        total_items = 0

        for b_obs, b_angles, b_trigs in loader:
            b_obs = b_obs.to(dev)
            b_angles = b_angles.to(dev)
            b_trigs = b_trigs.to(dev)

            dist = policy.get_distribution(b_obs)
            logits_angle = dist.distribution[0].logits
            logits_trig = dist.distribution[1].logits

            loss_angle = F.cross_entropy(logits_angle, b_angles)
            loss_trig = F.cross_entropy(logits_trig, b_trigs)
            loss = loss_angle + 0.5 * loss_trig

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item() * len(b_obs)
            pred_angles = logits_angle.argmax(dim=-1)
            pred_trigs = logits_trig.argmax(dim=-1)
            correct_angles += (pred_angles == b_angles).sum().item()
            correct_trigs += (pred_trigs == b_trigs).sum().item()
            total_items += len(b_obs)

        avg_loss = total_loss / total_items
        acc_angle = (correct_angles / total_items) * 100.0
        acc_trig = (correct_trigs / total_items) * 100.0
        print(f"  Epoch {epoch:2d}/{epochs} | Loss: {avg_loss:.4f} | Angle Acc: {acc_angle:5.1f}% | Trig Acc: {acc_trig:5.1f}%")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    model.save(output_path)
    print(f"\n[SUCCESS] [BC Pretrain] Warm-started policy saved successfully to: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Pretrain AGAR-RL Policy via Behavioral Cloning")
    parser.add_argument("--samples", type=int, default=25000, help="Number of expert samples")
    parser.add_argument("--epochs", type=int, default=6, help="Training epochs")
    parser.add_argument("--output", type=str, default="checkpoints/ppo/ppo_bc_pretrained.zip", help="Output path")
    parser.add_argument("--device", type=str, default="auto", help="Device ('cpu', 'cuda', 'auto')")
    parser.add_argument("--seed", type=int, default=42, help="Seed")
    args = parser.parse_args()

    pretrain_policy(
        output_path=args.output,
        num_samples=args.samples,
        epochs=args.epochs,
        device=args.device,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
