"""Gymnasium Environment Wrapper for Agar.io Vectorized Simulation.

SOTA V3 Architecture:
- Multi-Action Support: MultiDiscrete([24, 3]) or continuous Box(3).
- Pure SOTA Minimalist Reward (AgarCL / AgarIA standard):
    R_t = Delta_Mass / M_0 + 10.0 * Kills - min(5.0, M_death / M_0) * Death
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
    find_single_nearest_pellet_numba,
    compute_heuristic_threat_prey,
)


class HeuristicBot:
    """Tactical rule-based bot opponent with hunting, split attacks, and virus avoidance."""

    def __init__(self, player_id: int, rng: Optional[np.random.Generator] = None):
        self.player_id = player_id
        self.rng = rng if rng is not None else np.random.default_rng()
        self.split_cooldown = 0

    def get_action(self, engine: AgarEngine) -> np.ndarray:
        if self.split_cooldown > 0:
            self.split_cooldown -= 1

        p_cells = engine.get_player_cells(self.player_id)
        if not p_cells:
            return np.array([0.0, 0.0, -1.0], dtype=np.float32)

        cx, cy, cr = engine.get_player_centroid(self.player_id)
        my_mass = engine.get_player_mass(self.player_id)
        view_r = 500.0 + 2.0 * cr

        threat_x, threat_y, prey_dx, prey_dy, closest_prey_dist, closest_prey_mass = compute_heuristic_threat_prey(
            cx, cy, cr, my_mass, engine.cells_xy, engine.cells_mass, engine.cells_pid, self.player_id, view_r
        )

        # Avoid viruses if mass > 130
        virus_avoid_x = 0.0
        virus_avoid_y = 0.0
        if my_mass > 130.0 and len(engine.viruses_xy) > 0:
            for v in range(len(engine.viruses_xy)):
                vx = engine.viruses_xy[v, 0]
                vy = engine.viruses_xy[v, 1]
                v_dx = vx - cx
                if abs(v_dx) < (cr + 50.0):
                    v_dy = vy - cy
                    if abs(v_dy) < (cr + 50.0):
                        v_dist = math.hypot(v_dx, v_dy)
                        if 1e-4 < v_dist < (cr + 50.0):
                            w = 1.0 / max(10.0, v_dist)
                            virus_avoid_x -= (v_dx / v_dist) * w
                            virus_avoid_y -= (v_dy / v_dist) * w

        threat_norm = math.hypot(threat_x, threat_y)
        virus_norm = math.hypot(virus_avoid_x, virus_avoid_y)

        # 1. Primary instinct: Flee from predators
        if threat_norm > 1e-4:
            return np.array([threat_x / threat_norm, threat_y / threat_norm, -1.0], dtype=np.float32)

        # 2. Avoid popping on viruses
        if virus_norm > 1e-4:
            return np.array([virus_avoid_x / virus_norm, virus_avoid_y / virus_norm, -1.0], dtype=np.float32)

        # 3. Disciplined tactical split: ONLY when completely safe and highly advantageous
        can_split = (
            self.split_cooldown == 0
            and threat_norm < 1e-4
            and len(p_cells) <= 2
            and my_mass >= 60.0
            and 120.0 < closest_prey_dist < 240.0
            and my_mass >= 2.5 * closest_prey_mass
            and self.rng.random() < 0.08
        )
        if can_split:
            self.split_cooldown = 150  # 5-second cooldown at 30Hz
            return np.array([prey_dx, prey_dy, 0.8], dtype=np.float32)

        # 4. Normal prey pursuit without splitting
        if closest_prey_dist < 320.0 and my_mass >= 1.2 * closest_prey_mass:
            return np.array([prey_dx, prey_dy, -1.0], dtype=np.float32)

        # 5. Forage nearest pellet
        found, p_dx, p_dy = find_single_nearest_pellet_numba(cx, cy, engine.pellets_xy, max_dist=min(view_r, 350.0))
        if found:
            return np.array([p_dx, p_dy, -1.0], dtype=np.float32)

        ang = float(self.rng.uniform(0.0, 2.0 * math.pi))
        return np.array([math.cos(ang), math.sin(ang), -1.0], dtype=np.float32)


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
        self.kill_reward_multiplier = float(rewards_cfg.get("kill_reward_multiplier", 1.5))
        self.eat_cell_reward = float(rewards_cfg.get("kill_reward", 0.0))
        self.death_penalty_max = float(rewards_cfg.get("death_penalty_max", 10.0))
        self.forage_reward_scale = float(rewards_cfg.get("forage_reward_scale", 0.02))
        self.hunt_reward_scale = float(rewards_cfg.get("hunt_reward_scale", 0.05))
        self.split_strike_bonus = float(rewards_cfg.get("split_strike_bonus", 0.0))
        self.split_waste_penalty = float(rewards_cfg.get("split_waste_penalty", 0.0))
        self.split_invalid_penalty = float(rewards_cfg.get("split_invalid_penalty", 0.05))

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
            virus_split_threshold=float(cfg.get("entities", {}).get("virus_split_threshold", 140.0)),
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
            mass_decay_rate=float(cfg.get("physics", {}).get("mass_decay_rate", 0.00008)),
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

    def reset(
        self,
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
        for bot_id in range(1, self.num_bots + 1):
            self.engine.spawn_player(bot_id, initial_mass=self.initial_player_mass)
            self.heuristic_bots[bot_id] = HeuristicBot(bot_id, rng=np.random.default_rng(seed))

        self.prev_mass = self.initial_player_mass
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

        pre_prey_dist = self._last_prey_dist
        pre_prey_dx = self._last_prey_dx
        pre_prey_dy = self._last_prey_dy
        pre_prey_mass = self._last_prey_mass
        pre_learning_cells = self.engine.get_player_cells(self.learning_player_id)
        pre_max_subcell_mass = max((c.mass for c in pre_learning_cells), default=self.prev_mass)

        # Query bot macro-actions ONCE per step for all active bots (3x speedup)
        actions_dict: Dict[int, np.ndarray] = {self.learning_player_id: engine_action}
        for bot_id in range(1, self.num_bots + 1):
            if not self.engine.get_player_cells(bot_id):
                self.engine.spawn_player(bot_id, initial_mass=self.initial_player_mass)
            if self.opponent_policy_fn is not None:
                bot_act = self.opponent_policy_fn(bot_id, self.engine)
            else:
                bot_act = self.heuristic_bots[bot_id].get_action(self.engine)
            actions_dict[bot_id] = self.parse_action(bot_act)

        # Prepare sub-tick actions (reset split trigger on ticks 1+ to prevent multi-split within same macro-step)
        subtick_actions: Dict[int, np.ndarray] = {}
        for pid, act in actions_dict.items():
            subtick_actions[pid] = np.array([act[0], act[1], -1.0], dtype=np.float32)

        # Execute physics sub-ticks for action persistence / macro-action
        for tick_idx in range(self.action_repeat):
            step_actions = actions_dict if tick_idx == 0 else subtick_actions
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

        # SOTA Minimalist Reward (AgarCL / AgarIA / GoBigger standard):
        # 1. Normalized mass gain (strictly positive on eating pellets or cells)
        delta_mass = current_mass - self.prev_mass
        r_growth = (delta_mass / self.initial_player_mass) * self.mass_scale

        # 2. Combat payoff strictly proportional to victim mass (GoBigger standard)
        # Prevents valuing a 10-mass bot equally to a 200-mass bot!
        r_kill = (total_mass_eaten / self.initial_player_mass) * self.kill_reward_multiplier
        if self.eat_cell_reward > 0.0:
            r_kill += self.eat_cell_reward * float(total_cells_eaten)

        # 3. Moderate death penalty (AgarIA standard, never paralyzing)
        r_death = -min(self.death_penalty_max, self.prev_mass / self.initial_player_mass) if died else 0.0

        # 4. Action Invalidity Feedback for Split (Physical Feedback)
        # If the agent attempts a split when it's physically impossible (mass < 36 or at 16 cells),
        # apply light friction penalty to discourage wasted commands.
        r_split = 0.0
        if engine_action[2] > 0.6:
            if total_splits == 0 and (pre_max_subcell_mass < self.min_split_mass or len(pre_learning_cells) >= self.max_subcells):
                r_split = -self.split_invalid_penalty
            elif self.split_strike_bonus > 0.0 and 40.0 < pre_prey_dist < 320.0 and pre_prey_mass > 0:
                if (pre_max_subcell_mass / 2.0) > 1.15 * pre_prey_mass:
                    act_angle = math.atan2(float(engine_action[1]), float(engine_action[0]))
                    prey_angle = math.atan2(pre_prey_dy, pre_prey_dx)
                    angle_diff = abs((act_angle - prey_angle + math.pi) % (2.0 * math.pi) - math.pi)
                    if angle_diff < (math.pi / 4.0):  # within +/- 45 deg
                        r_split = self.split_strike_bonus

        # Build next observation (also updates self._last_pellet_dist and self._last_prey_dist)
        obs = self._build_observation()
        curr_pellet_dist = self._last_pellet_dist
        curr_prey_dist = self._last_prey_dist

        # 4. Dense Potential-Based Reward Shaping (PBRS) for Food Foraging (damped for large cells)
        # Suppressed during split ticks to eliminate centroid displacement artifacts
        r_forage = 0.0
        if not died and total_splits == 0 and self.prev_pellet_dist > 0 and curr_pellet_dist > 0:
            forage_mod = 1.0 if current_mass < 60.0 else max(0.2, 60.0 / current_mass)
            if total_pellets_eaten > 0:
                r_forage = self.forage_reward_scale * forage_mod
            else:
                dist_delta = self.prev_pellet_dist - curr_pellet_dist
                max_close = max(1.0, float(self.action_repeat) * self.v_max)
                progress = np.clip(dist_delta / max_close, -1.0, 1.0)
                r_forage = float(progress * self.forage_reward_scale * forage_mod)

        # 5. Directional Pursuit Reward (Heading Alignment): rewards pointing towards edible prey
        # Uses pre-step prey vector to evaluate exact decision direction
        r_hunt = 0.0
        if not died and pre_prey_dist > 0:
            act_norm = math.hypot(float(engine_action[0]), float(engine_action[1]))
            if act_norm > 1e-4:
                cos_align = (float(engine_action[0]) * pre_prey_dx + float(engine_action[1]) * pre_prey_dy) / (act_norm * pre_prey_dist)
                if cos_align > 0.0:
                    proximity = min(1.0, 350.0 / max(40.0, pre_prey_dist))
                    r_hunt = float(cos_align * self.hunt_reward_scale * proximity)

        self.prev_pellet_dist = curr_pellet_dist
        self.prev_prey_dist = curr_prey_dist
        self.prev_mass = current_mass

        reward = float(r_growth + r_kill + r_death + r_forage + r_hunt + r_split)

        terminated = bool(died)
        truncated = bool(self.current_step >= self.max_steps)

        info = {
            "player_mass": current_mass,
            "cells_eaten": total_cells_eaten,
            "pellets_eaten": total_pellets_eaten,
            "episode_pellets": self.episode_pellets_total,
            "episode_kills": self.total_cells_eaten,
            "died": died,
            "splits": total_splits,
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
        pellet_feats, nearest_dist = find_nearest_pellets_numba(cx, cy, self.engine.pellets_xy, view_r, k=10)
        obs[4:24] = pellet_feats
        self._last_pellet_dist = nearest_dist

        # Separate preys and predators based on authentic Agar.io subcell-level capabilities
        preys: List[Tuple[float, float, float, float, float, float]] = []
        predators: List[Tuple[float, float, float, float, float]] = []

        for other_cell in self.engine.cells:
            if other_cell.player_id == pid:
                continue
            dx = other_cell.x - cx
            dy = other_cell.y - cy
            dist = math.hypot(dx, dy)
            if dist > view_r:
                continue

            v_rel = math.hypot(other_cell.vx - avg_vx, other_cell.vy - avg_vy)

            # Authentic Prey condition: our largest cell can eat it! (other_cell.mass * 1.1 <= max_subcell_mass)
            # If our largest cell can eat it, it is prey (our main cell can split-kill or chase it down)
            if other_cell.mass * 1.1 <= max_subcell_mass:
                log_ratio = math.log(max(1.0, other_cell.mass) / max(1.0, max_subcell_mass))
                log_ratio_norm = float(np.tanh(log_ratio))
                preys.append((dist, dx, dy, log_ratio_norm, v_rel, other_cell.mass))
            elif other_cell.mass >= 1.1 * min_subcell_mass:
                # Authentic Predator condition: our largest cell CANNOT eat it, AND it threatens at least one subcell!
                log_ratio = math.log(max(1.0, other_cell.mass) / max(1.0, max_subcell_mass))
                log_ratio_norm = float(np.tanh(log_ratio))
                predators.append((dist, dx, dy, log_ratio_norm, v_rel))

        # 3. 5 Prey Cells (20 floats) -> offset 24 to 44
        preys.sort(key=lambda item: item[0])
        if pid == self.learning_player_id:
            if preys:
                self._last_prey_dist = preys[0][0]
                self._last_prey_dx = preys[0][1]
                self._last_prey_dy = preys[0][2]
                self._last_prey_mass = preys[0][5]
            else:
                self._last_prey_dist = -1.0
                self._last_prey_dx = 0.0
                self._last_prey_dy = 0.0
                self._last_prey_mass = 0.0

        for i, (dist, dx, dy, lr_norm, v_rel, *_) in enumerate(preys[:5]):
            base = 24 + i * 4
            obs[base] = float(np.clip(dx / view_r, -1.0, 1.0))
            obs[base + 1] = float(np.clip(dy / view_r, -1.0, 1.0))
            obs[base + 2] = lr_norm
            obs[base + 3] = float(np.clip(v_rel / self.v_max, -1.0, 1.0))

        # 4. 5 Predator Cells (20 floats) -> offset 44 to 64
        predators.sort(key=lambda item: item[0])
        for i, (_, dx, dy, lr_norm, v_rel) in enumerate(predators[:5]):
            base = 44 + i * 4
            obs[base] = float(np.clip(dx / view_r, -1.0, 1.0))
            obs[base + 1] = float(np.clip(dy / view_r, -1.0, 1.0))
            obs[base + 2] = lr_norm
            obs[base + 3] = float(np.clip(v_rel / self.v_max, -1.0, 1.0))

        # 5. 4 nearest Viruses (12 floats) -> offset 64 to 76
        v_dx = self.engine.viruses_xy[:, 0] - cx
        v_dy = self.engine.viruses_xy[:, 1] - cy
        v_dists = np.hypot(v_dx, v_dy)
        v_sorted = np.argsort(v_dists)[:4]

        can_explode_on_virus = (max_subcell_mass > self.engine.virus_split_threshold) and (len(my_cells) < self.engine.max_subcells)
        threat_sign = -1.0 if can_explode_on_virus else 1.0

        for i, v_idx in enumerate(v_sorted):
            base = 64 + i * 3
            if v_dists[v_idx] <= view_r:
                obs[base] = float(np.clip(v_dx[v_idx] / view_r, -1.0, 1.0))
                obs[base + 1] = float(np.clip(v_dy[v_idx] / view_r, -1.0, 1.0))
                obs[base + 2] = threat_sign

        # 6. Distances to 4 arena walls (4 floats) -> offset 76 to 80
        obs[76] = float(np.clip((self.height - cy) / view_r, 0.0, 1.0))
        obs[77] = float(np.clip(cy / view_r, 0.0, 1.0))
        obs[78] = float(np.clip(cx / view_r, 0.0, 1.0))
        obs[79] = float(np.clip((self.width - cx) / view_r, 0.0, 1.0))

        # 7. Global position & properties (4 floats) -> offset 80 to 84
        min_remerge = min((c.remerge_cooldown for c in my_cells), default=0)
        obs[80] = float(np.clip((cx / self.width) * 2.0 - 1.0, -1.0, 1.0))
        obs[81] = float(np.clip((cy / self.height) * 2.0 - 1.0, -1.0, 1.0))
        obs[82] = float(np.clip(cr / view_r, 0.0, 1.0))
        obs[83] = float(np.clip(min_remerge / 300.0, 0.0, 1.0))

        return np.clip(obs, -1.0, 1.0)
