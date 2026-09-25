"""Self-play opponent pool managing past checkpoints and heuristic baselines."""

from __future__ import annotations
import os
import random
import json
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import torch
from src.training.policy_arch import load_trained_model, predict_action


@dataclass
class OpponentEntry:
    """Entry storing a frozen adversary policy in the self-play pool."""
    tag: str
    path: str
    generation: int
    score: float = 0.0
    win_rate: float = 0.5
    policy: Optional[torch.nn.Module] = None


class SelfPlayPool:
    """Historical pool of adversary models for continuous self-play training."""

    def __init__(
        self,
        max_size: int = 10,
        history_dir: str = "checkpoints/self_play_pool",
        heuristic_ratio: float = 0.3,
        current_ratio: float = 0.2,
        pfsp_power: float = 1.5,
        seed: int = 42,
        device: str = "cpu",
    ):
        self.max_size = max_size
        self.history_dir = history_dir
        self.heuristic_ratio = heuristic_ratio
        self.current_ratio = current_ratio
        self.pfsp_power = float(np.clip(pfsp_power, 1.0, 2.0))
        self.rng = random.Random(seed)
        self.device = torch.device(device)
        self.pool: List[OpponentEntry] = []
        self._generation_counter = 0

        os.makedirs(self.history_dir, exist_ok=True)

    def __len__(self) -> int:
        return len(self.pool)

    def add_checkpoint(
        self,
        checkpoint_path: str,
        score: float = 0.0,
        tag: Optional[str] = None,
        win_rate: float = 0.5,
    ) -> OpponentEntry:
        """Add a newly saved model checkpoint to the opponent pool."""
        self._generation_counter += 1
        name = tag or f"gen_{self._generation_counter:04d}"

        # Load policy on specified device with no grad
        try:
            model = load_trained_model(checkpoint_path, device=self.device, allow_legacy=False)
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
            win_rate=float(np.clip(win_rate, 0.0, 1.0)),
            policy=policy,
        )

        # Evict oldest or lowest scoring entry if capacity reached
        if len(self.pool) >= self.max_size:
            # Sort by score ascending, remove worst
            self.pool.sort(key=lambda x: x.score)
            evicted = self.pool.pop(0)
            print(f"[SelfPlayPool] Evicted opponent {evicted.tag} (score: {evicted.score:.2f})")

        self.pool.append(entry)
        self._save_state()
        print(f"[SelfPlayPool] Registered opponent {entry.tag} (pool size: {len(self.pool)}/{self.max_size})")
        return entry

    def sample_opponent(self) -> Optional[OpponentEntry]:
        """Sample 30% heuristic, 20% current clone, or 50% PFSP history."""
        if not self.pool:
            return None

        roll = self.rng.random()
        if roll < self.heuristic_ratio:
            return None

        if roll < (self.heuristic_ratio + self.current_ratio):
            return self.pool[-1]

        weights = np.asarray(
            [
                max(1e-6, 1.0 - float(np.clip(entry.win_rate, 0.0, 1.0))) ** self.pfsp_power
                for entry in self.pool
            ],
            dtype=np.float64,
        )
        weights /= weights.sum()
        return self.rng.choices(self.pool, weights=weights.tolist(), k=1)[0]

    def update_win_rate(self, tag: str, won: bool, alpha: float = 0.1) -> None:
        """Update an opponent's active-agent win-rate estimate for PFSP."""
        for entry in self.pool:
            if entry.tag == tag:
                target = 1.0 if won else 0.0
                entry.win_rate = (1.0 - alpha) * entry.win_rate + alpha * target
                self._save_state()
                return

    @property
    def state_path(self) -> str:
        return os.path.join(self.history_dir, "pool_state.json")

    def _save_state(self) -> None:
        state = [
            {
                "tag": entry.tag,
                "path": entry.path,
                "generation": entry.generation,
                "score": entry.score,
                "win_rate": entry.win_rate,
            }
            for entry in self.pool
        ]
        temporary = f"{self.state_path}.tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        os.replace(temporary, self.state_path)

    def _load_state(self) -> Dict[str, Dict[str, Any]]:
        try:
            with open(self.state_path, "r", encoding="utf-8") as handle:
                entries = json.load(handle)
            return {str(item["path"]): item for item in entries}
        except (FileNotFoundError, OSError, ValueError, KeyError, TypeError):
            return {}

    def get_action(
        self,
        opponent: Optional[OpponentEntry],
        obs: np.ndarray,
        action_masks: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Query action from opponent model, or fallback to random/zeros."""
        if opponent is None or opponent.policy is None:
            ang = self.rng.uniform(0, 2 * np.pi)
            return np.array([np.cos(ang), np.sin(ang), -1.0], dtype=np.float32)

        try:
            with torch.no_grad():
                return predict_action(opponent.policy, obs, action_masks=action_masks, deterministic=False)
        except Exception:
            ang = self.rng.uniform(0, 2 * np.pi)
            return np.array([np.cos(ang), np.sin(ang), -1.0], dtype=np.float32)

    def sync_from_disk(self) -> int:
        """Scan history_dir on disk and load newly saved checkpoints in numerical order."""
        if not os.path.exists(self.history_dir):
            return 0
        try:
            mtime = os.path.getmtime(self.history_dir)
            if hasattr(self, "_last_disk_mtime") and self._last_disk_mtime == mtime:
                return 0
            self._last_disk_mtime = mtime
        except OSError:
            pass

        loaded = 0
        existing_paths = set(entry.path for entry in self.pool)
        metadata = self._load_state()

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
                    saved = metadata.get(full_path, {})
                    self.add_checkpoint(
                        full_path,
                        score=float(saved.get("score", 0.0)),
                        tag=saved.get("tag", f.replace(".zip", "")),
                        win_rate=float(saved.get("win_rate", 0.5)),
                    )
                    existing_paths.add(full_path)
                    loaded += 1
                except Exception:
                    pass
        return loaded


