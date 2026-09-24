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
        """Sample an opponent using Prioritized Fictitious Self-Play (PFSP):
        - 20%: Heuristic baseline (guarantees grounding against hand-crafted bots)
        - 40%: Latest checkpoint (freshest clone, forces active competitive adaptation)
        - 40%: Historical pool (guards against strategy cycling and catastrophic forgetting)
        """
        if not self.pool:
            return None

        roll = random.random()
        if roll < self.heuristic_ratio:
            return None  # 20% Heuristic bot

        if roll < (self.heuristic_ratio + 0.40):
            # 40% Latest checkpoint
            return self.pool[-1]

        # 40% Historical sample across earlier pool generations
        return random.choice(self.pool)

    def get_action(self, opponent: Optional[OpponentEntry], obs: np.ndarray) -> np.ndarray:
        """Query action from opponent model, or fallback to random/zeros."""
        if opponent is None or opponent.policy is None:
            ang = random.uniform(0, 2 * np.pi)
            return np.array([np.cos(ang), np.sin(ang), -1.0], dtype=np.float32)

        try:
            with torch.no_grad():
                action, _ = opponent.policy.predict(obs, deterministic=False)
                return action
        except Exception:
            ang = random.uniform(0, 2 * np.pi)
            return np.array([np.cos(ang), np.sin(ang), -1.0], dtype=np.float32)

    def sync_from_disk(self) -> int:
        """Scan history_dir on disk and load newly saved checkpoints in numerical order."""
        if not os.path.exists(self.history_dir):
            return 0
        loaded = 0
        existing_paths = set(entry.path for entry in self.pool)

        import re
        def step_key(filename: str) -> int:
            m = re.search(r'step_(\d+)', filename)
            return int(m.group(1)) if m else 0

        files = [f for f in os.listdir(self.history_dir) if f.endswith(".zip")]
        files.sort(key=step_key)

        for f in files:
            full_path = os.path.join(self.history_dir, f)
            if full_path not in existing_paths:
                try:
                    self.add_checkpoint(full_path, tag=f.replace(".zip", ""))
                    existing_paths.add(full_path)
                    loaded += 1
                except Exception:
                    pass
        return loaded


