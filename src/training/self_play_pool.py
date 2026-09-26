"""Self-play opponent pool managing past checkpoints and heuristic baselines."""

from __future__ import annotations
import os
import random
import json
import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
import numpy as np


@dataclass
class OpponentEntry:
    """Entry storing a frozen adversary policy in the self-play pool."""
    tag: str
    path: str
    generation: int
    score: float = 0.0
    win_rate: float = 0.5
    # Keep the pool import lightweight in rollout workers. The concrete policy
    # type is supplied lazily by _load_policy after a checkpoint is sampled.
    policy: Optional[Any] = None


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
        verbose: int = 0,
        checkpoint_dirs: Optional[List[str]] = None,
        preload_models: bool = True,
        max_cached_models: int = 4,
    ):
        self.max_size = max_size
        self.history_dir = history_dir
        self.heuristic_ratio = heuristic_ratio
        self.current_ratio = current_ratio
        self.pfsp_power = float(np.clip(pfsp_power, 1.0, 2.0))
        self.rng = random.Random(seed)
        self.device = str(device)
        self.checkpoint_dirs = list(checkpoint_dirs or [])
        self.preload_models = bool(preload_models)
        self.max_cached_models = max(1, int(max_cached_models))
        self._policy_cache: OrderedDict[str, Any] = OrderedDict()
        self.verbose = int(verbose)
        self.pool: List[OpponentEntry] = []
        self._generation_counter = 0
        # Remember files that have been considered even after their policy is
        # evicted from the bounded in-memory league.
        self._known_checkpoint_paths: set[str] = set()

        os.makedirs(self.history_dir, exist_ok=True)

    def __len__(self) -> int:
        return len(self.pool)

    def add_checkpoint(
        self,
        checkpoint_path: str,
        score: float = 0.0,
        tag: Optional[str] = None,
        win_rate: float = 0.5,
        persist_state: bool = True,
    ) -> OpponentEntry:
        """Add a newly saved model checkpoint to the opponent pool."""
        self._generation_counter += 1
        name = tag or f"gen_{self._generation_counter:04d}"

        policy = self._load_policy(checkpoint_path) if self.preload_models else None

        entry = OpponentEntry(
            tag=name,
            path=checkpoint_path,
            generation=self._generation_counter,
            score=score,
            win_rate=float(np.clip(win_rate, 0.0, 1.0)),
            policy=policy,
        )
        self._known_checkpoint_paths.add(os.path.abspath(checkpoint_path))

        # Keep score-based diversity when meaningful evaluation scores exist;
        # otherwise evict the oldest generation (all-zero scores are common).
        if len(self.pool) >= self.max_size:
            if any(abs(entry.score) > 1e-9 for entry in self.pool):
                evict_idx = min(range(len(self.pool)), key=lambda idx: self.pool[idx].score)
            else:
                evict_idx = min(range(len(self.pool)), key=lambda idx: self.pool[idx].generation)
            evicted = self.pool.pop(evict_idx)
            self._policy_cache.pop(os.path.abspath(evicted.path), None)
            if self.verbose > 1:
                print(f"[SelfPlayPool] Evicted opponent {evicted.tag} (score: {evicted.score:.2f})")

        self.pool.append(entry)
        if policy is not None:
            self._cache_policy(entry, policy)
        if persist_state:
            self._save_state()
        if self.verbose > 1:
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

    def _load_policy(self, checkpoint_path: str):
        try:
            import torch
            from src.training.policy_arch import load_trained_model

            torch.set_num_threads(1)
            try:
                torch.set_num_interop_threads(1)
            except RuntimeError:
                pass
            model = load_trained_model(checkpoint_path, device=self.device)
            policy = model.policy
            policy.eval()
            for parameter in policy.parameters():
                parameter.requires_grad = False
            return policy
        except Exception as exc:
            if self.verbose:
                print(f"[SelfPlayPool] Could not load {checkpoint_path}: {exc}")
            return None

    def _cache_policy(self, entry: OpponentEntry, policy: Any) -> None:
        key = os.path.abspath(entry.path)
        entry.policy = policy
        self._policy_cache[key] = policy
        self._policy_cache.move_to_end(key)
        while len(self._policy_cache) > self.max_cached_models:
            evicted_path, _ = self._policy_cache.popitem(last=False)
            for candidate in self.pool:
                if os.path.abspath(candidate.path) == evicted_path:
                    candidate.policy = None
                    break

    def get_action(
        self,
        opponent: Optional[OpponentEntry],
        obs: np.ndarray,
        action_masks: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Query action from opponent model, or fallback to random/zeros."""
        if opponent is None:
            ang = self.rng.uniform(0, 2 * np.pi)
            return np.array([np.cos(ang), np.sin(ang), -1.0], dtype=np.float32)

        try:
            import torch
            from src.training.policy_arch import predict_action

            if opponent.policy is None:
                policy = self._load_policy(opponent.path)
                if policy is None:
                    raise RuntimeError(f"Could not load opponent {opponent.path}")
                self._cache_policy(opponent, policy)
            else:
                key = os.path.abspath(opponent.path)
                if key in self._policy_cache:
                    self._policy_cache.move_to_end(key, last=True)
                else:
                    self._cache_policy(opponent, opponent.policy)
            with torch.no_grad():
                return predict_action(opponent.policy, obs, action_masks=action_masks, deterministic=False)
        except Exception:
            ang = self.rng.uniform(0, 2 * np.pi)
            return np.array([np.cos(ang), np.sin(ang), -1.0], dtype=np.float32)

    def sync_from_disk(self, persist_state: bool = True) -> int:
        """Discover newly saved immutable checkpoints without loading weights eagerly."""
        search_dirs = [self.history_dir, *self.checkpoint_dirs]
        if not any(os.path.isdir(folder) for folder in search_dirs):
            return 0
        metadata = self._load_state()
        metadata_by_basename = {os.path.basename(path): item for path, item in metadata.items()}

        def step_key(filename: str) -> int:
            m = re.search(r'step_(\d+)', filename)
            return int(m.group(1)) if m else 0

        candidates: dict[str, str] = {}
        for folder_index, folder in enumerate(search_dirs):
            if not os.path.isdir(folder):
                continue
            for filename in os.listdir(folder):
                if not filename.endswith(".zip") or filename.startswith("._"):
                    continue
                if folder_index > 0 and not filename.startswith("ppo_step_"):
                    continue
                full_path = os.path.abspath(os.path.join(folder, filename))
                if os.path.getsize(full_path) > 1000:
                    candidates.setdefault(full_path, filename)
        ordered_paths = sorted(candidates, key=lambda path: step_key(candidates[path]))
        new_paths = [path for path in ordered_paths if path not in self._known_checkpoint_paths]
        if not new_paths:
            return 0

        # At startup, only materialize the entries that can fit in the league.
        # Keep saved league members first, then fill remaining slots with the
        # newest checkpoints. Mark older files as seen so later syncs do not
        # repeatedly deserialize and evict the same historical models.
        preferred = [
            path for path in new_paths
            if path in metadata or os.path.basename(path) in metadata_by_basename
        ]
        preferred_set = set(preferred)
        newest = [path for path in reversed(new_paths) if path not in preferred_set]
        selected = (preferred + newest)[: self.max_size]
        self._known_checkpoint_paths.update(new_paths)

        loaded = 0
        for full_path in selected:
            try:
                saved = metadata.get(full_path, metadata_by_basename.get(os.path.basename(full_path), {}))
                self.add_checkpoint(
                    full_path,
                    score=float(saved.get("score", 0.0)),
                    tag=saved.get("tag", os.path.basename(full_path).replace(".zip", "")),
                    win_rate=float(saved.get("win_rate", 0.5)),
                    persist_state=persist_state,
                )
                loaded += 1
            except Exception:
                pass
        return loaded
