"""Self-play opponent pool managing past checkpoints and heuristic baselines."""

from __future__ import annotations
import os
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import torch
from stable_baselines3 import PPO


@dataclass
class OpponentEntry:
    """Entry storing a frozen adversary policy in the self-play pool."""
    tag: str
    path: str
    generation: int
    score: float = 0.0
    policy: Optional[torch.nn.Module] = None


class SelfPlayPool:
    """Historical pool of adversary models for continuous self-play training."""

    def __init__(
        self,
        max_size: int = 10,
        history_dir: str = "checkpoints/self_play_pool",
        heuristic_ratio: float = 0.3,
        device: str = "cpu",
    ):
        self.max_size = max_size
        self.history_dir = history_dir
        self.heuristic_ratio = heuristic_ratio
        self.device = torch.device(device)
        self.pool: List[OpponentEntry] = []
        self._generation_counter = 0

        os.makedirs(self.history_dir, exist_ok=True)

    def __len__(self) -> int:
        return len(self.pool)

    def add_checkpoint(self, checkpoint_path: str, score: float = 0.0, tag: Optional[str] = None) -> OpponentEntry:
        """Add a newly saved model checkpoint to the opponent pool."""
        self._generation_counter += 1
        name = tag or f"gen_{self._generation_counter:04d}"

        # Load policy on specified device with no grad
        try:
            model = PPO.load(checkpoint_path, device=self.device)
            policy = model.policy
            policy.eval()
            for p in policy.parameters():
                p.requires_grad = False
        except Exception as e:
            print(f"[SelfPlayPool] Warning: Could not pre-cache policy weights ({e}), storing path only.")
            policy = None

        entry = OpponentEntry(
            tag=name,
            path=checkpoint_path,
            generation=self._generation_counter,
            score=score,
            policy=policy,
        )

        # Evict oldest or lowest scoring entry if capacity reached
        if len(self.pool) >= self.max_size:
            # Sort by score ascending, remove worst
            self.pool.sort(key=lambda x: x.score)
            evicted = self.pool.pop(0)
            print(f"[SelfPlayPool] Evicted opponent {evicted.tag} (score: {evicted.score:.2f})")

        self.pool.append(entry)
        print(f"[SelfPlayPool] Registered opponent {entry.tag} (pool size: {len(self.pool)}/{self.max_size})")
        return entry

    def sample_opponent(self) -> Optional[OpponentEntry]:
        """Sample an opponent from the pool, or return None for heuristic bot."""
        if not self.pool:
            return None

        # Chance to select heuristic baseline
        if random.random() < self.heuristic_ratio:
            return None

        return random.choice(self.pool)

    def get_action(self, opponent: Optional[OpponentEntry], obs: np.ndarray) -> np.ndarray:
        """Query action from opponent model, or fallback to random/zeros."""
        if opponent is None or opponent.policy is None:
            return np.array([0.0, 0.0, -1.0], dtype=np.float32)

        with torch.no_grad():
            obs_tensor = torch.as_tensor(obs, dtype=torch.float32, device=self.device).unsqueeze(0)
            # Query policy distribution action mean
            features = opponent.policy.extract_features(obs_tensor)
            if hasattr(opponent.policy, "mlp_extractor"):
                latent_pi, _ = opponent.policy.mlp_extractor(features)
                action_mean = opponent.policy.action_net(latent_pi)
            else:
                action_mean, _, _ = opponent.policy(obs_tensor)

            action = action_mean.squeeze(0).cpu().numpy()
            return np.clip(action, -1.0, 1.0)

