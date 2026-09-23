"""Farama Gymnasium compliant environment for Agar.io with 84-dim observation vector."""

from __future__ import annotations
import math
from typing import Dict, List, Tuple, Optional, Any, Callable
import numpy as np
import gymnasium as gym
from gymnasium import spaces

from src.env.agar_engine import AgarEngine
from src.env.entities import Cell, mass_to_radius, mass_to_speed


class HeuristicBot:
    """Heuristic rule-based Agar.io bot for baseline opponents and self-play warmup."""

    def __init__(self, player_id: int, rng: Optional[np.random.Generator] = None):
        self.player_id = player_id
        self.rng = rng or np.random.default_rng()

    def get_action(self, engine: AgarEngine) -> np.ndarray:
        """Compute an action [tx, ty, trigger] based on nearby threats and targets."""
        p_cells = engine.get_player_cells(self.player_id)
        if not p_cells:
            # Random exploration if dead or respawning
            return np.array([self.rng.uniform(-1, 1), self.rng.uniform(-1, 1), -1.0], dtype=np.float32)

        cx, cy, cr = engine.get_player_centroid(self.player_id)
        my_mass = engine.get_player_mass(self.player_id)
        view_r = 500.0 + 2.0 * cr

        # Check threats (cells larger than 1.1x)
        threat_vec = np.zeros(2, dtype=np.float32)
        prey_vec = np.zeros(2, dtype=np.float32)
        closest_prey_dist = 1e9
        closest_prey_mass = 0.0

        for other_cell in engine.cells:
            if other_cell.player_id == self.player_id:
                continue
            dx = other_cell.x - cx
            dy = other_cell.y - cy
            dist = math.hypot(dx, dy)
            if dist > view_r or dist < 1e-4:
                continue

            if other_cell.mass >= 1.1 * my_mass:
                # Flee threat with inverse-distance weighting
                weight = 1.0 / max(30.0, dist)
                threat_vec[0] -= (dx / dist) * weight
                threat_vec[1] -= (dy / dist) * weight
            elif other_cell.mass <= 0.9 * my_mass:
                # Target prey
                if dist < closest_prey_dist:
                    closest_prey_dist = dist
                    closest_prey_mass = other_cell.mass
                    prey_vec[0] = dx / dist
                    prey_vec[1] = dy / dist

        # Avoid viruses if mass > 130
        virus_avoid_vec = np.zeros(2, dtype=np.float32)
        if my_mass > 130.0:
            for vx, vy in engine.viruses_xy:
                v_dx = vx - cx
                v_dy = vy - cy
                v_dist = math.hypot(v_dx, v_dy)
                if v_dist < (cr + 50.0) and v_dist > 1e-4:
                    virus_avoid_vec[0] -= (v_dx / v_dist) * (1.0 / max(10.0, v_dist))
                    virus_avoid_vec[1] -= (v_dy / v_dist) * (1.0 / max(10.0, v_dist))

        # Check if threat is dominant
        threat_norm = np.linalg.norm(threat_vec)
        virus_norm = np.linalg.norm(virus_avoid_vec)

        if threat_norm > 1e-4:
            move_dir = threat_vec / threat_norm
            return np.array([move_dir[0], move_dir[1], -1.0], dtype=np.float32)

        if virus_norm > 1e-4:
            move_dir = virus_avoid_vec / virus_norm
            return np.array([move_dir[0], move_dir[1], -1.0], dtype=np.float32)

        # Hunt prey or split if safe and advantageous
        if closest_prey_dist < 250.0 and my_mass >= 2.0 * closest_prey_mass and my_mass >= 40.0:
            if len(p_cells) < 8 and self.rng.random() < 0.2:
                # Split attack!
                return np.array([prey_vec[0], prey_vec[1], 0.8], dtype=np.float32)
            return np.array([prey_vec[0], prey_vec[1], -1.0], dtype=np.float32)

        # Check for nearby ejected mass (tempting bait / food)
        if engine.ejected:
            closest_feed_dist = float("inf")
            feed_dir = np.zeros(2, dtype=np.float32)
            for em in engine.ejected:
                em_dx = em.x - cx
                em_dy = em.y - cy
                em_dist = math.hypot(em_dx, em_dy)
                if em_dist < min(view_r, 450.0) and em_dist < closest_feed_dist:
                    closest_feed_dist = em_dist
                    feed_dir[0] = em_dx / max(1e-4, em_dist)
                    feed_dir[1] = em_dy / max(1e-4, em_dist)

            if closest_feed_dist < min(view_r, 400.0):
                # Move toward feed (baiting / feeding works!)
                return np.array([feed_dir[0], feed_dir[1], -1.0], dtype=np.float32)

        # Otherwise forage closest pellet
        cand = engine.spatial_grid.query_circle(cx, cy, min(view_r, 300.0))
        if cand:
            c_xy = engine.pellets_xy[cand]
            dists = np.hypot(c_xy[:, 0] - cx, c_xy[:, 1] - cy)
            closest_idx = np.argmin(dists)
            p_dx = c_xy[closest_idx, 0] - cx
            p_dy = c_xy[closest_idx, 1] - cy
            p_dist = max(1e-4, dists[closest_idx])
            return np.array([p_dx / p_dist, p_dy / p_dist, -1.0], dtype=np.float32)

        # Random wander with smooth momentum
        ang = self.rng.uniform(0, 2 * np.pi)
        return np.array([math.cos(ang), math.sin(ang), -1.0], dtype=np.float32)


class AgarEnv(gym.Env):
    """Gymnasium Environment for Agar.io reinforcement learning agents.

    Observation Space: Box(84,) normalized in [-1, 1].
    Action Space: Box(3,) continuous:
      - act[0]: target X direction [-1, 1]
      - act[1]: target Y direction [-1, 1]
      - act[2]: trigger: < -0.33 (idle), [-0.33, 0.33] (eject), > 0.33 (split)
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
        self.width = float(arena_cfg.get("width", 2000.0))
        self.height = float(arena_cfg.get("height", 2000.0))

        sim_cfg = cfg.get("simulation", {})
        self.num_bots = int(sim_cfg.get("num_bots", 10))
        self.max_steps = int(sim_cfg.get("max_steps", 1000))

        rewards_cfg = cfg.get("rewards", {})
        self.mass_scale = float(rewards_cfg.get("mass_scale", 1.0))
        self.pellet_reward = float(rewards_cfg.get("pellet_reward", 0.05))
        self.eat_cell_reward = float(rewards_cfg.get("eat_cell_reward", 5.0))
        self.death_penalty = float(rewards_cfg.get("death_penalty", -10.0))
        self.inefficient_split_penalty = float(rewards_cfg.get("inefficient_split_penalty", 0.0))
        self.split_eval_window = int(rewards_cfg.get("split_eval_window", 30))
        self.survival_reward = float(rewards_cfg.get("survival_reward", 0.001))
        self.proximity_pellet_reward = float(rewards_cfg.get("proximity_pellet_reward", 0.0))

        self.initial_player_mass = float(cfg.get("physics", {}).get("initial_player_mass", 20.0))
        self.v_base = float(cfg.get("physics", {}).get("v_base", 2.0))
        self.v_max = 2.0  # Normalization denominator

        self.engine = AgarEngine(
            width=self.width,
            height=self.height,
            num_pellets=int(cfg.get("entities", {}).get("num_pellets", 1800)),
            pellet_mass=float(cfg.get("entities", {}).get("pellet_mass", 1.0)),
            num_viruses=int(cfg.get("entities", {}).get("num_viruses", 10)),
            virus_mass=float(cfg.get("entities", {}).get("virus_mass", 100.0)),
            virus_radius=float(cfg.get("entities", {}).get("virus_radius", 30.0)),
            virus_split_threshold=float(cfg.get("entities", {}).get("virus_split_threshold", 130.0)),
            eat_ratio=float(cfg.get("physics", {}).get("eat_ratio", 1.1)),
            v_base=self.v_base,
            v_min=float(cfg.get("physics", {}).get("v_min", 0.5)),
            radius_scale=float(cfg.get("physics", {}).get("radius_scale", 3.0)),
            max_subcells=int(cfg.get("physics", {}).get("max_subcells", 16)),
            remerge_cooldown_ticks=int(cfg.get("physics", {}).get("remerge_cooldown_ticks", 600)),
            remerge_cooldown_mass_factor=float(cfg.get("physics", {}).get("remerge_cooldown_mass_factor", 0.5)),
            split_boost_speed=float(cfg.get("physics", {}).get("split_boost_speed", 24.0)),
            split_boost_decay=float(cfg.get("physics", {}).get("split_boost_decay", 0.90)),
            eject_loss_mass=float(cfg.get("physics", {}).get("eject_loss_mass", 16.0)),
            eject_spawn_mass=float(cfg.get("physics", {}).get("eject_spawn_mass", 12.0)),
            mass_decay_rate=float(cfg.get("physics", {}).get("mass_decay_rate", 0.0004)),
            spatial_cell_size=float(sim_cfg.get("spatial_grid_cell_size", 100.0)),
            seed=seed,
        )

        self.learning_player_id = 0
        self.opponent_policy_fn = opponent_policy_fn

        # Action space: continuous [target_x, target_y, trigger]
        self.action_space = spaces.Box(
            low=np.array([-1.0, -1.0, -1.0], dtype=np.float32),
            high=np.array([1.0, 1.0, 1.0], dtype=np.float32),
            shape=(3,),
            dtype=np.float32,
        )

        # Observation space: 84 floats bounded in [-1.0, 1.0]
        self.observation_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(84,),
            dtype=np.float32,
        )

        self.current_step = 0
        self.prev_mass = self.initial_player_mass
        self.heuristic_bots: Dict[int, HeuristicBot] = {}

        # Tracking for inefficient split penalty: list of (step_at_split, cells_eaten_at_split)
        self.active_splits: List[Tuple[int, int]] = []
        self.total_cells_eaten = 0

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
        self.active_splits.clear()
        self.total_cells_eaten = 0
        self.prev_nearest_pellet_dist = 0.0  # Will be computed on first step

        obs = self._build_observation()
        info = {
            "player_mass": self.initial_player_mass,
            "step": self.current_step,
            "num_subcells": 1,
        }
        return obs, info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """Advance environment by one timestep with learning agent action."""
        self.current_step += 1

        # Clip action to action space
        action = np.clip(action, self.action_space.low, self.action_space.high)

        # Prepare actions dictionary for all active players
        actions_dict: Dict[int, np.ndarray] = {self.learning_player_id: action}

        # Query actions for bots
        for bot_id in range(1, self.num_bots + 1):
            if not self.engine.get_player_cells(bot_id):
                # Respawn dead bot
                self.engine.spawn_player(bot_id, initial_mass=self.initial_player_mass)

            if self.opponent_policy_fn is not None:
                bot_act = self.opponent_policy_fn(bot_id, self.engine)
            else:
                bot_act = self.heuristic_bots[bot_id].get_action(self.engine)
            actions_dict[bot_id] = bot_act

        # Execute simulation step
        events = self.engine.step(actions_dict)

        # Check learning player status
        learning_cells = self.engine.get_player_cells(self.learning_player_id)
        current_mass = self.engine.get_player_mass(self.learning_player_id)
        player_events = events.get(self.learning_player_id, {})

        cells_eaten = player_events.get("cells_eaten", 0)
        self.total_cells_eaten += cells_eaten
        died = player_events.get("died", False) or (len(learning_cells) == 0)
        splits_performed = player_events.get("splits", 0)

        # Record split for inefficient split penalty tracking
        for _ in range(splits_performed):
            self.active_splits.append((self.current_step, self.total_cells_eaten))

        # Check expired split tracking
        inefficient_splits = 0
        retained_splits = []
        for split_time, eaten_at_split in self.active_splits:
            if (self.current_step - split_time) >= self.split_eval_window:
                if (self.total_cells_eaten - eaten_at_split) == 0:
                    inefficient_splits += 1
            else:
                retained_splits.append((split_time, eaten_at_split))
        self.active_splits = retained_splits

        # Compute Reward (Section 2.4)
        # R_mass = (sqrt(m_t) - sqrt(m_{t-1})) / sqrt(m_{init})
        r_mass = (math.sqrt(max(1.0, current_mass)) - math.sqrt(max(1.0, self.prev_mass))) / math.sqrt(
            self.initial_player_mass
        )
        pellets_eaten = player_events.get("pellets_eaten", 0)
        r_pellet = float(pellets_eaten) * self.pellet_reward
        r_hunt = float(cells_eaten) * self.eat_cell_reward
        r_death = self.death_penalty if died else 0.0
        r_split_penalty = float(inefficient_splits) * abs(self.inefficient_split_penalty)
        r_survival = self.survival_reward

        # Proximity-to-pellet reward: dense signal for approaching food
        r_proximity = 0.0
        if self.proximity_pellet_reward > 0 and not died and len(learning_cells) > 0:
            cx, cy, _ = self.engine.get_player_centroid(self.learning_player_id)
            cand = self.engine.spatial_grid.query_circle(cx, cy, 300.0)
            if cand:
                p_xy = self.engine.pellets_xy[cand]
                dists = np.hypot(p_xy[:, 0] - cx, p_xy[:, 1] - cy)
                nearest_dist = float(np.min(dists))
            else:
                nearest_dist = 300.0

            if self.prev_nearest_pellet_dist > 0:
                # Reward for closing distance (positive when getting closer)
                delta = self.prev_nearest_pellet_dist - nearest_dist
                r_proximity = float(np.clip(delta / 50.0, -0.5, 0.5)) * self.proximity_pellet_reward
            self.prev_nearest_pellet_dist = nearest_dist

        reward = float(r_mass * self.mass_scale + r_pellet + r_hunt + r_death - r_split_penalty + r_survival + r_proximity)

        self.prev_mass = current_mass

        terminated = bool(died)
        truncated = bool(self.current_step >= self.max_steps)

        obs = self._build_observation()
        info = {
            "player_mass": current_mass,
            "cells_eaten": cells_eaten,
            "pellets_eaten": player_events.get("pellets_eaten", 0),
            "died": died,
            "splits": splits_performed,
            "step": self.current_step,
            "num_subcells": len(learning_cells),
        }

        return obs, reward, terminated, truncated, info

    def _build_observation(self, player_id: Optional[int] = None) -> np.ndarray:
        """Construct the 84-dimensional egocentric normalized observation vector.

        Structure:
          1. Self state (4 floats): [tanh(m/500), vx/vmax, vy/vmax, k/16]
          2. 10 nearest Pellets (20 floats): [dx/R, dy/R]
          3. 5 Prey Cells (20 floats): [dx/R, dy/R, tanh(dm/100), v_rel/vmax]
          4. 5 Predator Cells (20 floats): [dx/R, dy/R, tanh(dm/100), v_rel/vmax]
          5. 4 nearest Viruses (12 floats): [dx/R, dy/R, imminent_collision_bool]
          6. 4 Arena boundary distances (4 floats): [d_top/R, d_bottom/R, d_left/R, d_right/R]
        """
        pid = self.learning_player_id if player_id is None else player_id
        obs = np.zeros(84, dtype=np.float32)

        my_cells = self.engine.get_player_cells(pid)
        if not my_cells:
            # Dead or empty: return padded zeros
            return obs

        cx, cy, cr = self.engine.get_player_centroid(pid)
        my_mass = self.engine.get_player_mass(pid)
        view_r = 500.0 + 2.0 * cr

        # Average velocity
        avg_vx = sum(c.vx for c in my_cells) / len(my_cells)
        avg_vy = sum(c.vy for c in my_cells) / len(my_cells)

        # 1. Self state (4 floats)
        obs[0] = float(np.tanh(my_mass / 500.0))
        obs[1] = float(np.clip(avg_vx / self.v_max, -1.0, 1.0))
        obs[2] = float(np.clip(avg_vy / self.v_max, -1.0, 1.0))
        obs[3] = float(np.clip(len(my_cells) / 16.0, 0.0, 1.0))

        # 2. 10 nearest Pellets (10 * 2 = 20 floats) -> offset 4 to 24
        cand_pellets = self.engine.spatial_grid.query_circle(cx, cy, view_r)
        if cand_pellets:
            p_xy = self.engine.pellets_xy[cand_pellets]
            p_dx = p_xy[:, 0] - cx
            p_dy = p_xy[:, 1] - cy
            p_dists = np.hypot(p_dx, p_dy)
            within_view = p_dists <= view_r
            if np.any(within_view):
                valid_idx = np.where(within_view)[0]
                sorted_idx = valid_idx[np.argsort(p_dists[valid_idx])][:10]
                for i, idx in enumerate(sorted_idx):
                    base = 4 + i * 2
                    obs[base] = float(np.clip(p_dx[idx] / view_r, -1.0, 1.0))
                    obs[base + 1] = float(np.clip(p_dy[idx] / view_r, -1.0, 1.0))

        # Separate preys and predators among other cells
        preys: List[Tuple[float, float, float, float, float]] = []  # (dist, dx, dy, dm, v_rel)
        predators: List[Tuple[float, float, float, float, float]] = []

        for other_cell in self.engine.cells:
            if other_cell.player_id == pid:
                continue
            dx = other_cell.x - cx
            dy = other_cell.y - cy
            dist = math.hypot(dx, dy)
            if dist > view_r:
                continue

            dm = other_cell.mass - my_mass
            v_rel = math.hypot(other_cell.vx - avg_vx, other_cell.vy - avg_vy)

            if other_cell.mass <= 0.9 * my_mass:
                preys.append((dist, dx, dy, dm, v_rel))
            elif other_cell.mass >= 1.1 * my_mass:
                predators.append((dist, dx, dy, dm, v_rel))

        # 3. 5 Prey Cells (5 * 4 = 20 floats) -> offset 24 to 44
        preys.sort(key=lambda item: item[0])
        for i, (_, dx, dy, dm, v_rel) in enumerate(preys[:5]):
            base = 24 + i * 4
            obs[base] = float(np.clip(dx / view_r, -1.0, 1.0))
            obs[base + 1] = float(np.clip(dy / view_r, -1.0, 1.0))
            obs[base + 2] = float(np.tanh(dm / 100.0))
            obs[base + 3] = float(np.clip(v_rel / self.v_max, -1.0, 1.0))

        # 4. 5 Predator Cells (5 * 4 = 20 floats) -> offset 44 to 64
        predators.sort(key=lambda item: item[0])
        for i, (_, dx, dy, dm, v_rel) in enumerate(predators[:5]):
            base = 44 + i * 4
            obs[base] = float(np.clip(dx / view_r, -1.0, 1.0))
            obs[base + 1] = float(np.clip(dy / view_r, -1.0, 1.0))
            obs[base + 2] = float(np.tanh(dm / 100.0))
            obs[base + 3] = float(np.clip(v_rel / self.v_max, -1.0, 1.0))

        # 5. 4 nearest Viruses (4 * 3 = 12 floats) -> offset 64 to 76
        v_dx = self.engine.viruses_xy[:, 0] - cx
        v_dy = self.engine.viruses_xy[:, 1] - cy
        v_dists = np.hypot(v_dx, v_dy)
        v_sorted = np.argsort(v_dists)[:4]

        for i, v_idx in enumerate(v_sorted):
            base = 64 + i * 3
            if v_dists[v_idx] <= view_r:
                obs[base] = float(np.clip(v_dx[v_idx] / view_r, -1.0, 1.0))
                obs[base + 1] = float(np.clip(v_dy[v_idx] / view_r, -1.0, 1.0))
                # Collision imminent: mass > 130 and dist < (cr + 50)
                imminent = 1.0 if (my_mass > 130.0 and v_dists[v_idx] < (cr + 50.0)) else 0.0
                obs[base + 2] = imminent

        # 6. Distances to 4 arena walls (4 floats) -> offset 76 to 80
        # Walls: top (y=height), bottom (y=0), left (x=0), right (x=width)
        d_top = self.height - cy
        d_bottom = cy
        d_left = cx
        d_right = self.width - cx

        obs[76] = float(np.clip(d_top / view_r, 0.0, 1.0))
        obs[77] = float(np.clip(d_bottom / view_r, 0.0, 1.0))
        obs[78] = float(np.clip(d_left / view_r, 0.0, 1.0))
        obs[79] = float(np.clip(d_right / view_r, 0.0, 1.0))

        # 7. Global position & cell properties (4 floats) -> offset 80 to 84
        # Completes D = 84 feature representation
        min_remerge = min((c.remerge_cooldown for c in my_cells), default=0)
        obs[80] = float(np.clip((cx / self.width) * 2.0 - 1.0, -1.0, 1.0))
        obs[81] = float(np.clip((cy / self.height) * 2.0 - 1.0, -1.0, 1.0))
        obs[82] = float(np.clip(cr / view_r, 0.0, 1.0))
        obs[83] = float(np.clip(min_remerge / 300.0, 0.0, 1.0))

        # Final clip safety for exact [-1.0, 1.0] interval
        return np.clip(obs, -1.0, 1.0)
