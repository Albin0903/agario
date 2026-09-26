"""Gymnasium Environment Wrapper for Agar.io Vectorized Simulation.

SOTA V3 Architecture:
- Multi-Action Support: MultiDiscrete([24, 3]) or continuous Box(3).
- V11 mass objective: signed mass delta + new-peak bonus + bounded death penalty.
- Zero artificial wall/danger/jerk micro-penalties (prevents policy paralysis).
- Fully vectorized Farama Gymnasium compliance.
"""

from __future__ import annotations
import math
from typing import Optional, Tuple, Dict, Any, Callable, List
import numpy as np
import gymnasium as gym
from gymnasium import spaces

from src.env.agar_engine import AgarEngine
from src.env.entities import mass_to_radius
from src.env.physics_fast import (
    find_nearest_pellets_numba,
    compute_heuristic_threat_prey,
    compute_bot_action_fast,
    extract_entities_observation_numba,
)


class HeuristicBot:
    """Tactical rule-based bot opponent with hunting, split attacks, and virus avoidance."""

    def __init__(self, player_id: int, rng: Optional[np.random.Generator] = None):
        self.player_id = player_id
        self.rng = rng if rng is not None else np.random.default_rng()
        self.split_cooldown = 0
        self._action_buf = np.zeros(3, dtype=np.float32)

    def get_action(self, engine: AgarEngine) -> np.ndarray:
        if self.split_cooldown > 0:
            self.split_cooldown -= 1

        p_cells = engine.get_player_cells(self.player_id)
        if not p_cells:
            self._action_buf[0] = 0.0
            self._action_buf[1] = 0.0
            self._action_buf[2] = -1.0
            return self._action_buf

        cx, cy, cr = engine.get_player_centroid(self.player_id)
        my_mass = engine.get_player_mass(self.player_id)
        rng_split = float(self.rng.random())
        rng_ang = float(self.rng.uniform(0.0, 2.0 * math.pi))

        dx, dy, trig, new_cooldown = compute_bot_action_fast(
            cx,
            cy,
            cr,
            my_mass,
            len(p_cells),
            self.split_cooldown,
            engine.cells_xy,
            engine.cells_mass,
            engine.cells_pid,
            self.player_id,
            engine.viruses_xy,
            engine.pellets_xy,
            rng_split,
            rng_ang,
        )
        self.split_cooldown = new_cooldown
        self._action_buf[0] = dx
        self._action_buf[1] = dy
        self._action_buf[2] = trig
        return self._action_buf


class AgarEnv(gym.Env):
    """SOTA Gymnasium Environment for Agar.io Multi-Agent Reinforcement Learning.

    Observation Space: Box(84,) normalized in [-1, 1].
    Action Space:
      - MultiDiscrete([24, 3]): 24 movement angles + [0: Move, 1: Split, 2: Eject]
      - Or continuous Box(3,): [target_x, target_y, trigger]
    """

    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 30}

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        opponent_policy_fn: Optional[Callable[[int, AgarEngine], np.ndarray]] = None,
        seed: Optional[int] = None,
    ):
        super().__init__()
        cfg = config or {}
        arena_cfg = cfg.get("arena", {})
        self.width = float(arena_cfg.get("width", 1400.0))
        self.height = float(arena_cfg.get("height", 1400.0))

        sim_cfg = cfg.get("simulation", {})
        self.num_bots = int(sim_cfg.get("num_bots", 20))
        self.max_steps = int(sim_cfg.get("max_steps", 3500))

        # Action space configuration
        action_cfg = cfg.get("action", {})
        self.action_type = action_cfg.get("action_type", "multidiscrete")
        self.num_angles = int(action_cfg.get("num_angles", 24))

        if self.action_type == "multidiscrete":
            self.action_space = spaces.MultiDiscrete([self.num_angles, 3])
        else:
            self.action_space = spaces.Box(
                low=np.array([-1.0, -1.0, -1.0], dtype=np.float32),
                high=np.array([1.0, 1.0, 1.0], dtype=np.float32),
                shape=(3,),
                dtype=np.float32,
            )

        # SOTA Minimalist Reward formulation (AgarCL / AgarIA / GoBigger standard)
        rewards_cfg = cfg.get("rewards", {})
        self.mass_scale = float(rewards_cfg.get("mass_scale", 1.0))
        self.death_penalty_max = float(rewards_cfg.get("death_penalty_max", 10.0))
        self.peak_mass_scale = float(rewards_cfg.get("peak_mass_scale", 1.0))

        self.action_repeat = int(sim_cfg.get("action_repeat", 3))
        self.initial_player_mass = float(cfg.get("physics", {}).get("initial_player_mass", 20.0))
        self.v_base = float(cfg.get("physics", {}).get("v_base", 3.5))
        self.v_max = 2.0
        self.min_split_mass = float(cfg.get("physics", {}).get("min_split_mass", 36.0))
        self.max_subcells = int(cfg.get("physics", {}).get("max_subcells", 16))

        self.engine = AgarEngine(
            width=self.width,
            height=self.height,
            num_pellets=int(cfg.get("entities", {}).get("num_pellets", 2000)),
            pellet_mass=float(cfg.get("entities", {}).get("pellet_mass", 1.0)),
            num_viruses=int(cfg.get("entities", {}).get("num_viruses", 8)),
            virus_mass=float(cfg.get("entities", {}).get("virus_mass", 100.0)),
            virus_radius=float(cfg.get("entities", {}).get("virus_radius", 24.0)),
            virus_split_threshold=float(cfg.get("entities", {}).get("virus_split_threshold", 130.0)),
            eat_ratio=float(cfg.get("physics", {}).get("eat_ratio", 1.1)),
            v_base=self.v_base,
            v_min=float(cfg.get("physics", {}).get("v_min", 0.8)),
            radius_scale=float(cfg.get("physics", {}).get("radius_scale", 3.0)),
            max_subcells=int(cfg.get("physics", {}).get("max_subcells", 16)),
            max_cell_mass=float(cfg.get("physics", {}).get("max_cell_mass", 2250.0)),
            min_split_mass=float(cfg.get("physics", {}).get("min_split_mass", 36.0)),
            remerge_cooldown_ticks=int(cfg.get("physics", {}).get("remerge_cooldown_ticks", 600)),
            remerge_cooldown_mass_factor=float(cfg.get("physics", {}).get("remerge_cooldown_mass_factor", 0.5)),
            split_boost_speed=float(cfg.get("physics", {}).get("split_boost_speed", 26.0)),
            split_boost_decay=float(cfg.get("physics", {}).get("split_boost_decay", 0.90)),
            eject_loss_mass=float(cfg.get("physics", {}).get("eject_loss_mass", 16.0)),
            eject_spawn_mass=float(cfg.get("physics", {}).get("eject_spawn_mass", 12.0)),
            mass_decay_rate=float(cfg.get("physics", {}).get("mass_decay_rate", 0.002)),
            tick_duration_seconds=float(sim_cfg.get("tick_duration_seconds", 1.0 / 25.0)),
            spatial_cell_size=float(sim_cfg.get("spatial_grid_cell_size", 100.0)),
            seed=seed,
        )

        self.learning_player_id = 0
        self.opponent_policy_fn = opponent_policy_fn

        # Observation space: 84 floats bounded in [-1.0, 1.0]
        self.observation_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(84,),
            dtype=np.float32,
        )

        self.current_step = 0
        self.prev_mass = self.initial_player_mass
        self.peak_mass = self.initial_player_mass
        self.prev_pellet_dist = -1.0
        self._last_pellet_dist = -1.0
        self.prev_prey_dist = -1.0
        self._last_prey_dist = -1.0
        self._last_prey_dx = 0.0
        self._last_prey_dy = 0.0
        self._last_prey_mass = 0.0
        self.heuristic_bots: Dict[int, HeuristicBot] = {}
        self.total_cells_eaten = 0
        self.episode_pellets_total = 0
        self._actions_dict: Dict[int, np.ndarray] = {}
        self._subtick_actions: Dict[int, np.ndarray] = {
            pid: np.array([0.0, 0.0, -1.0], dtype=np.float32) for pid in range(self.num_bots + 1)
        }

    def action_masks(self, player_id: Optional[int] = None) -> np.ndarray:
        """Flattened MultiDiscrete mask: [num_angles bits | 3 trigger bits].

        Split (trigger index 1) is False when no cell has mass >= min_split_mass
        or the player already has max_subcells. Angles and eject stay legal.
        """
        n_angles = self.num_angles
        mask = np.ones(n_angles + 3, dtype=np.bool_)
        if self.action_type != "multidiscrete":
            return mask
        pid = self.learning_player_id if player_id is None else player_id
        cells = self.engine.get_player_cells(pid)
        can_split = bool(cells) and len(cells) < self.max_subcells and any(
            cell.mass >= self.min_split_mass for cell in cells
        )
        mask[n_angles + 1] = can_split
        return mask

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Reset environment to initial state."""
        super().reset(seed=seed)
        self.current_step = 0
        self.engine.reset(seed=seed)

        # Spawn learning player (id = 0)
        self.engine.spawn_player(self.learning_player_id, initial_mass=self.initial_player_mass)

        # Spawn bot opponents (ids 1 .. num_bots)
        self.heuristic_bots.clear()
        self._actions_dict.clear()
        for bot_id in range(1, self.num_bots + 1):
            self.engine.spawn_player(bot_id, initial_mass=self.initial_player_mass)
            self.heuristic_bots[bot_id] = HeuristicBot(bot_id, rng=np.random.default_rng(seed))
            if bot_id not in self._subtick_actions:
                self._subtick_actions[bot_id] = np.array([0.0, 0.0, -1.0], dtype=np.float32)

        self.prev_mass = self.initial_player_mass
        self.peak_mass = self.initial_player_mass
        self.total_cells_eaten = 0
        self.episode_pellets_total = 0

        obs = self._build_observation()
        self.prev_pellet_dist = self._last_pellet_dist
        self.prev_prey_dist = self._last_prey_dist
        info = {
            "player_mass": self.initial_player_mass,
            "step": self.current_step,
            "num_subcells": 1,
        }
        return obs, info

    def parse_action(self, action: Any) -> np.ndarray:
        """Universal Action Converter: converts MultiDiscrete([24, 3]) or Box(3) into engine [dx, dy, trig]."""
        if isinstance(action, (np.ndarray, list, tuple)):
            if len(action) == 2 and isinstance(action[0], (int, np.integer)):
                angle_idx = int(action[0]) % self.num_angles
                trig_idx = int(action[1])
                theta = angle_idx * (2.0 * math.pi / self.num_angles)
                raw_dx = math.cos(theta)
                raw_dy = math.sin(theta)
                # trig: 0 -> -1.0 (idle/move), 1 -> 0.8 (split), 2 -> 0.4 (eject)
                trig = 0.8 if trig_idx == 1 else (0.4 if trig_idx == 2 else -1.0)
                return np.array([raw_dx, raw_dy, trig], dtype=np.float32)
            raw_arr = np.asarray(action, dtype=np.float32)
            if len(raw_arr) == 2:
                return np.array([raw_arr[0], raw_arr[1], -1.0], dtype=np.float32)
            return np.clip(raw_arr, -1.0, 1.0)
        return np.array([0.0, 0.0, -1.0], dtype=np.float32)

    def step(self, action: Any) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """Advance environment by one timestep with learning agent action (applying action_repeat)."""
        self.current_step += 1
        engine_action = self.parse_action(action)

        total_cells_eaten = 0
        total_pellets_eaten = 0
        total_mass_eaten = 0.0
        total_splits = 0
        died = False

        pre_learning_cells = self.engine.get_player_cells(self.learning_player_id)
        pre_max_subcell_mass = max((c.mass for c in pre_learning_cells), default=self.prev_mass)

        # Query bot macro-actions ONCE per step for all active bots (3x speedup)
        self._actions_dict[self.learning_player_id] = engine_action
        learn_sub = self._subtick_actions[self.learning_player_id]
        learn_sub[0] = engine_action[0]
        learn_sub[1] = engine_action[1]
        learn_sub[2] = -1.0

        for bot_id in range(1, self.num_bots + 1):
            if not self.engine.get_player_cells(bot_id):
                self.engine.spawn_player(bot_id, initial_mass=self.initial_player_mass)
            if self.opponent_policy_fn is not None:
                bot_act = self.opponent_policy_fn(bot_id, self.engine)
                parsed = self.parse_action(bot_act)
            else:
                parsed = self.heuristic_bots[bot_id].get_action(self.engine)
            self._actions_dict[bot_id] = parsed
            bot_sub = self._subtick_actions[bot_id]
            bot_sub[0] = parsed[0]
            bot_sub[1] = parsed[1]
            bot_sub[2] = -1.0

        # Execute physics sub-ticks for action persistence / macro-action
        for tick_idx in range(self.action_repeat):
            step_actions = self._actions_dict if tick_idx == 0 else self._subtick_actions
            events = self.engine.step(step_actions)
            player_events = events.get(self.learning_player_id, {})
            total_cells_eaten += player_events.get("cells_eaten", 0)
            total_pellets_eaten += player_events.get("pellets_eaten", 0)
            total_mass_eaten += player_events.get("mass_eaten", 0.0)
            total_splits += player_events.get("splits", 0)

            learning_cells = self.engine.get_player_cells(self.learning_player_id)
            if player_events.get("died", False) or (len(learning_cells) == 0):
                died = True
                break

        current_mass = self.engine.get_player_mass(self.learning_player_id)
        self.total_cells_eaten += total_cells_eaten
        self.episode_pellets_total += total_pellets_eaten

        # Growth objective: signed mass progress plus peak progression.
        delta_mass = current_mass - self.prev_mass
        previous_peak = self.peak_mass
        self.peak_mass = max(self.peak_mass, current_mass)
        new_peak_delta = self.peak_mass - previous_peak
        r_growth = (delta_mass / self.initial_player_mass) * self.mass_scale
        r_peak = (new_peak_delta / self.initial_player_mass) * self.peak_mass_scale
        r_death = -min(self.death_penalty_max, self.peak_mass / self.initial_player_mass) if died else 0.0

        # Build next observation (also updates self._last_pellet_dist and self._last_prey_dist)
        obs = self._build_observation()
        curr_pellet_dist = self._last_pellet_dist

        self.prev_pellet_dist = curr_pellet_dist
        self.prev_mass = current_mass

        reward = float(r_growth + r_peak + r_death)

        terminated = bool(died)
        truncated = bool(self.current_step >= self.max_steps)

        info = {
            "player_mass": current_mass,
            "peak_mass": self.peak_mass,
            "action_repeat": self.action_repeat,
            "tick_duration_seconds": self.engine.tick_duration_seconds,
            "cells_eaten": total_cells_eaten,
            "pellets_eaten": total_pellets_eaten,
            "episode_pellets": self.episode_pellets_total,
            "episode_kills": self.total_cells_eaten,
            "died": died,
            "splits": total_splits,
            "reward_mass": r_growth,
            "reward_mass_growth": r_growth,
            "reward_peak": r_peak,
            "reward_death": r_death,
            "step": self.current_step,
            "num_subcells": len(self.engine.get_player_cells(self.learning_player_id)),
        }

        return obs, reward, terminated, truncated, info

    def _build_observation(self, player_id: Optional[int] = None) -> np.ndarray:
        """Construct the 84-dimensional egocentric normalized observation vector.

        Structure:
          1. Self state (4 floats): [tanh(m/500), vx/vmax, vy/vmax, min(1.0, k/16)]
          2. 10 nearest Pellets (20 floats): [u_x, u_y] for nearest + [dx/R, dy/R] for others
          3. 5 Prey Cells (20 floats): [dx/R, dy/R, tanh(dm/100), v_rel/vmax]
          4. 5 Predator Cells (20 floats): [dx/R, dy/R, tanh(dm/100), v_rel/vmax]
          5. 4 nearest Viruses (12 floats): [dx/R, dy/R, threat_sign]
          6. 4 Arena boundary distances (4 floats): [d_top/R, d_bottom/R, d_left/R, d_right/R]
          7. Global position & properties (4 floats): [norm_x, norm_y, radius/R, min_remerge/300]
        """
        pid = self.learning_player_id if player_id is None else player_id
        obs = np.zeros(84, dtype=np.float32)

        my_cells = self.engine.get_player_cells(pid)
        if not my_cells:
            return obs

        cx, cy, cr = self.engine.get_player_centroid(pid)
        my_mass = self.engine.get_player_mass(pid)
        max_subcell_mass = max(c.mass for c in my_cells)
        min_subcell_mass = min(c.mass for c in my_cells)
        view_r = 500.0 + 2.0 * cr

        avg_vx = sum(c.vx for c in my_cells) / len(my_cells)
        avg_vy = sum(c.vy for c in my_cells) / len(my_cells)

        # 1. Self state (4 floats)
        obs[0] = float(np.tanh(my_mass / 500.0))
        obs[1] = float(np.clip(avg_vx / self.v_max, -1.0, 1.0))
        obs[2] = float(np.clip(avg_vy / self.v_max, -1.0, 1.0))
        obs[3] = float(np.clip(len(my_cells) / 16.0, 0.0, 1.0))

        # 2. 10 nearest Pellets (20 floats) -> offset 4 to 24 (compiled Numba JIT)
        pellet_feats, nearest_dist = find_nearest_pellets_numba(
            cx, cy, self.engine.pellets_xy, view_r, k=10
        )
        obs[4:24] = pellet_feats
        self._last_pellet_dist = nearest_dist

        # 3. Preys, Predators, Viruses, Walls, Global (24 to 84) via compiled Numba JIT
        self.engine._refresh_player_cache()
        n_all = len(self.engine.cells)
        cells_vx = np.empty(n_all, dtype=np.float32)
        cells_vy = np.empty(n_all, dtype=np.float32)
        for i, c in enumerate(self.engine.cells):
            cells_vx[i] = c.vx
            cells_vy[i] = c.vy

        can_explode = (max_subcell_mass > self.engine.virus_split_threshold) and (len(my_cells) < self.engine.max_subcells)
        min_cd = min((c.remerge_cooldown for c in my_cells), default=0)

        p_dist, p_dx, p_dy, p_mass = extract_entities_observation_numba(
            obs, cx, cy, avg_vx, avg_vy, view_r, self.v_max,
            max_subcell_mass, min_subcell_mass, pid,
            self.engine.cells_xy, self.engine.cells_mass, self.engine.cells_pid,
            cells_vx, cells_vy, self.engine.viruses_xy, can_explode,
            self.engine.width, self.engine.height, cr, float(min_cd),
        )

        if pid == self.learning_player_id:
            self._last_prey_dist = p_dist
            self._last_prey_dx = p_dx
            self._last_prey_dy = p_dy
            self._last_prey_mass = p_mass

        return obs
