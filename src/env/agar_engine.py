"""Headless high-performance 2D vectorized simulation engine for Agar.io."""

from __future__ import annotations
import math
import time
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from src.env.entities import mass_to_radius, mass_to_speed, Pellet, Virus, Cell, EjectedMass
from src.env.physics_fast import (
    check_pellet_collisions_numba,
    check_pellet_collisions_fast,
    find_virus_cell_collisions_numba,
    find_cell_eat_events_numba,
    spawn_pellet_coords_fast,
)


class SpatialHashGrid:
    """Uniform 2D spatial hash grid for accelerating point entity queries (pellets)."""

    def __init__(self, width: float, height: float, cell_size: float = 100.0):
        self.width = width
        self.height = height
        self.cell_size = cell_size
        self.inv_cell = 1.0 / cell_size
        self.cols = int(math.ceil(width / cell_size))
        self.rows = int(math.ceil(height / cell_size))
        self.total_cells = self.cols * self.rows
        self.buckets: List[set] = [set() for _ in range(self.total_cells)]
        self.pellet_buckets: np.ndarray = np.zeros(0, dtype=np.int32)

    def clear(self) -> None:
        for b in self.buckets:
            b.clear()

    def build(self, pellets_xy: np.ndarray) -> None:
        """Populate the grid with pellet positions (N, 2)."""
        self.clear()
        n = len(pellets_xy)
        if len(self.pellet_buckets) != n:
            self.pellet_buckets = np.zeros(n, dtype=np.int32)

        cols = np.clip((pellets_xy[:, 0] * self.inv_cell).astype(np.int32), 0, self.cols - 1)
        rows = np.clip((pellets_xy[:, 1] * self.inv_cell).astype(np.int32), 0, self.rows - 1)
        indices = rows * self.cols + cols
        self.pellet_buckets[:] = indices
        for i, idx in enumerate(indices):
            self.buckets[idx].add(i)

    def update_pellet(self, idx: int, new_x: float, new_y: float) -> None:
        """Incrementally update single pellet position bucket."""
        c = int(new_x * self.inv_cell)
        r = int(new_y * self.inv_cell)
        if c < 0: c = 0
        elif c >= self.cols: c = self.cols - 1
        if r < 0: r = 0
        elif r >= self.rows: r = self.rows - 1
        new_bucket = r * self.cols + c
        old_bucket = int(self.pellet_buckets[idx])
        if new_bucket != old_bucket:
            self.buckets[old_bucket].discard(idx)
            self.buckets[new_bucket].add(idx)
            self.pellet_buckets[idx] = new_bucket

    def query_circle(self, x: float, y: float, radius: float) -> List[int]:
        """Query all pellet indices located in grid buckets overlapping a circle."""
        min_c = int((x - radius) * self.inv_cell)
        max_c = int((x + radius) * self.inv_cell)
        min_r = int((y - radius) * self.inv_cell)
        max_r = int((y + radius) * self.inv_cell)

        if min_c < 0: min_c = 0
        elif min_c >= self.cols: min_c = self.cols - 1
        if max_c < 0: max_c = 0
        elif max_c >= self.cols: max_c = self.cols - 1

        if min_r < 0: min_r = 0
        elif min_r >= self.rows: min_r = self.rows - 1
        if max_r < 0: max_r = 0
        elif max_r >= self.rows: max_r = self.rows - 1

        candidates: List[int] = []
        for r in range(min_r, max_r + 1):
            base = r * self.cols
            for c in range(min_c, max_c + 1):
                candidates.extend(self.buckets[base + c])
        return candidates


class AgarEngine:
    """Vectorized, headless 2D Agar physics simulation engine."""

    def __init__(
        self,
        width: float = 2000.0,
        height: float = 2000.0,
        num_pellets: int = 1800,
        pellet_mass: float = 1.0,
        num_viruses: int = 10,
        virus_mass: float = 100.0,
        virus_radius: float = 30.0,
        virus_split_threshold: float = 130.0,
        eat_ratio: float = 1.1,
        v_base: float = 2.0,
        v_min: float = 0.5,
        radius_scale: float = 3.0,
        max_subcells: int = 16,
        max_cell_mass: float = 2250.0,
        min_split_mass: float = 36.0,
        remerge_cooldown_ticks: int = 600,
        remerge_cooldown_mass_factor: float = 0.5,
        split_boost_speed: float = 24.0,
        split_boost_decay: float = 0.90,
        eject_loss_mass: float = 16.0,
        eject_spawn_mass: float = 12.0,
        mass_decay_rate: float = 0.0,
        spatial_cell_size: float = 100.0,
        seed: Optional[int] = None,
    ):
        self.width = float(width)
        self.height = float(height)
        self.num_pellets = num_pellets
        self.pellet_mass = pellet_mass
        self.num_viruses = num_viruses
        self.virus_mass = virus_mass
        self.virus_radius = virus_radius
        self.virus_split_threshold = virus_split_threshold
        self.eat_ratio = eat_ratio
        self.v_base = v_base
        self.v_min = v_min
        self.radius_scale = radius_scale
        self.max_subcells = max_subcells
        self.max_cell_mass = float(max_cell_mass)
        self.min_split_mass = float(min_split_mass)
        self.remerge_cooldown_ticks = remerge_cooldown_ticks
        self.remerge_cooldown_mass_factor = float(remerge_cooldown_mass_factor)
        self.split_boost_speed = split_boost_speed
        self.split_boost_decay = split_boost_decay
        self.eject_loss_mass = eject_loss_mass
        self.eject_spawn_mass = eject_spawn_mass
        self.mass_decay_rate = mass_decay_rate

        self.rng = np.random.default_rng(seed)
        self.spatial_grid = SpatialHashGrid(self.width, self.height, cell_size=spatial_cell_size)

        # Entity arrays
        self.pellets_xy: np.ndarray = np.zeros((num_pellets, 2), dtype=np.float32)
        self.viruses_xy: np.ndarray = np.zeros((num_viruses, 2), dtype=np.float32)
        self.virus_masses: np.ndarray = np.full(num_viruses, self.virus_mass, dtype=np.float32)
        self.virus_radii: np.ndarray = np.full(num_viruses, self.virus_radius, dtype=np.float32)

        # Active player cells: stored in structured lists for dynamic count
        # player_id -> list of Cell
        self.cells: List[Cell] = []
        self.ejected: List[EjectedMass] = []
        self._next_cell_id = 1
        self._next_ejected_id = 1

        # Entity cache for ultra-fast bot queries and step processing
        self._cells_cache_valid = False
        self._player_cells_cache: Dict[int, List[Cell]] = {}
        self._player_mass_cache: Dict[int, float] = {}
        self._player_centroid_cache: Dict[int, Tuple[float, float, float]] = {}

        # Preallocated buffers for zero-allocation cell arrays
        self._cells_buf_cap = 256
        self._cells_xy_buf = np.empty((self._cells_buf_cap, 2), dtype=np.float32)
        self._cells_mass_buf = np.empty(self._cells_buf_cap, dtype=np.float32)
        self._cells_pid_buf = np.empty(self._cells_buf_cap, dtype=np.int32)
        self._cells_r_buf = np.empty(self._cells_buf_cap, dtype=np.float32)
        self.cells_xy: np.ndarray = self._cells_xy_buf[:0]
        self.cells_mass: np.ndarray = self._cells_mass_buf[:0]
        self.cells_pid: np.ndarray = self._cells_pid_buf[:0]
        self.cells_r: np.ndarray = self._cells_r_buf[:0]

        # Event tracking per step
        self.step_events: Dict[int, Dict[str, Any]] = {}
        self.profile_enabled = False
        self.last_profile: Dict[str, float] = {}

        self.reset(seed)

    def _spawn_pellet_coords(self, count: int) -> Tuple[np.ndarray, np.ndarray]:
        """Generate pellet coordinates with high-density halos concentrated around viruses."""
        if count == 0:
            return np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.float32)

        # Ultra-fast path for incremental step-by-step pellet respawns
        if count < 100 and self.num_viruses > 0 and len(self.viruses_xy) > 0:
            rfloats = self.rng.random(count * 8, dtype=np.float32)
            return spawn_pellet_coords_fast(
                count, float(self.width), float(self.height), self.viruses_xy, 28.0, rfloats
            )

        xs = np.zeros(count, dtype=np.float32)
        ys = np.zeros(count, dtype=np.float32)

        # Allocate dense halos around viruses (approx 35 pellets per virus)
        halo_quota = 0
        if self.num_viruses > 0 and len(self.viruses_xy) > 0:
            pellets_per_virus = 35
            halo_quota = min(count // 2, len(self.viruses_xy) * pellets_per_virus)

        if halo_quota > 0:
            v_indices = self.rng.integers(0, len(self.viruses_xy), size=halo_quota)
            v_xy = self.viruses_xy[v_indices]
            angles = self.rng.uniform(0.0, 2.0 * np.pi, size=halo_quota).astype(np.float32)
            dists = self.rng.uniform(self.virus_radius * 1.35, self.virus_radius * 2.5, size=halo_quota).astype(np.float32)
            xs[:halo_quota] = np.clip(v_xy[:, 0] + np.cos(angles) * dists, 20.0, self.width - 20.0)
            ys[:halo_quota] = np.clip(v_xy[:, 1] + np.sin(angles) * dists, 20.0, self.height - 20.0)

        # Disperse remaining pellets across arena
        free_count = count - halo_quota
        if free_count > 0:
            free_xs = self.rng.uniform(20.0, self.width - 20.0, size=free_count).astype(np.float32)
            free_ys = self.rng.uniform(20.0, self.height - 20.0, size=free_count).astype(np.float32)

            if self.num_viruses > 0 and len(self.viruses_xy) > 0:
                thresh_sq = (self.virus_radius * 1.35) ** 2
                for _ in range(2):
                    for vx, vy in self.viruses_xy:
                        dx = free_xs - vx
                        dy = free_ys - vy
                        dist_sq = dx * dx + dy * dy
                        close_mask = dist_sq < thresh_sq
                        if np.any(close_mask):
                            num_close = np.count_nonzero(close_mask)
                            angles = self.rng.uniform(0.0, 2.0 * np.pi, size=num_close).astype(np.float32)
                            dists = self.rng.uniform(self.virus_radius * 1.4, self.virus_radius * 2.5, size=num_close).astype(np.float32)
                            free_xs[close_mask] = np.clip(vx + np.cos(angles) * dists, 20.0, self.width - 20.0)
                            free_ys[close_mask] = np.clip(vy + np.sin(angles) * dists, 20.0, self.height - 20.0)

            xs[halo_quota:] = free_xs
            ys[halo_quota:] = free_ys

        # Ensure strict separation from all virus cores (multi-pass to prevent displacement into adjacent viruses)
        if self.num_viruses > 0 and len(self.viruses_xy) > 0:
            min_core_dist = 28.0
            for _ in range(10):
                has_violation = False
                for vx, vy in self.viruses_xy:
                    dx = xs - vx
                    dy = ys - vy
                    dists = np.hypot(dx, dy)
                    too_close = dists < min_core_dist
                    if np.any(too_close):
                        has_violation = True
                        num_bad = np.count_nonzero(too_close)
                        safe_angles = self.rng.uniform(0.0, 2.0 * np.pi, size=num_bad).astype(np.float32)
                        safe_dist = self.rng.uniform(min_core_dist + 5.0, min_core_dist + 30.0, size=num_bad).astype(np.float32)
                        xs[too_close] = np.clip(vx + np.cos(safe_angles) * safe_dist, 20.0, self.width - 20.0)
                        ys[too_close] = np.clip(vy + np.sin(safe_angles) * safe_dist, 20.0, self.height - 20.0)
                if not has_violation:
                    break

        return xs, ys

    def reset(self, seed: Optional[int] = None) -> None:
        """Reset simulation state, respawning pellets, viruses, and clearing cells."""
        if seed is not None:
            self.rng = np.random.default_rng(seed)

        # Randomize viruses first so pellets can cluster around them
        self.viruses_xy = np.zeros((self.num_viruses, 2), dtype=np.float32)
        self.viruses_xy[:, 0] = self.rng.uniform(100.0, self.width - 100.0, size=self.num_viruses)
        self.viruses_xy[:, 1] = self.rng.uniform(100.0, self.height - 100.0, size=self.num_viruses)
        self.virus_masses = np.full(self.num_viruses, self.virus_mass, dtype=np.float32)
        self.virus_radii = np.full(self.num_viruses, self.virus_radius, dtype=np.float32)

        # Randomize pellets with virus halos
        px, py = self._spawn_pellet_coords(self.num_pellets)
        self.pellets_xy[:, 0] = px
        self.pellets_xy[:, 1] = py
        self.spatial_grid.build(self.pellets_xy)

        self.cells.clear()
        self.ejected.clear()
        self._next_cell_id = 1
        self._next_ejected_id = 1
        self.step_events.clear()
        self._cells_cache_valid = False

    def set_profiling(self, enabled: bool = True) -> None:
        """Enable optional per-phase timing for short diagnostics only."""
        self.profile_enabled = bool(enabled)
        self.last_profile = {}

    def spawn_player(self, player_id: int, initial_mass: float = 20.0, xy: Optional[Tuple[float, float]] = None) -> Cell:
        """Spawn an initial single cell for a player safely outside existing player cells."""
        if xy is None:
            best_x = float(self.rng.uniform(100.0, self.width - 100.0))
            best_y = float(self.rng.uniform(100.0, self.height - 100.0))
            if self.cells:
                # Safe spawn rejection sampling: prevent spawning inside existing player cells or viruses
                for _ in range(25):
                    cx = float(self.rng.uniform(100.0, self.width - 100.0))
                    cy = float(self.rng.uniform(100.0, self.height - 100.0))
                    conflict = False
                    for other in self.cells:
                        dx = cx - other.x
                        dy = cy - other.y
                        safe_r = other.radius + 35.0
                        if (dx * dx + dy * dy) < (safe_r * safe_r):
                            conflict = True
                            break
                    if not conflict:
                        best_x, best_y = cx, cy
                        break
            x, y = best_x, best_y
        else:
            x, y = xy

        cell = Cell(
            id=self._next_cell_id,
            player_id=player_id,
            x=x,
            y=y,
            mass=float(initial_mass),
            vx=0.0,
            vy=0.0,
            boost_vx=0.0,
            boost_vy=0.0,
            remerge_cooldown=0,
        )
        self._next_cell_id += 1
        self.cells.append(cell)
        self._cells_cache_valid = False
        return cell

    def _refresh_player_cache(self) -> None:
        """Refresh dictionary lookups for active player cells and centroids (single-pass)."""
        if self._cells_cache_valid:
            return
        self._player_cells_cache.clear()
        self._player_mass_cache.clear()
        self._player_centroid_cache.clear()

        n = len(self.cells)
        if n > self._cells_buf_cap:
            self._cells_buf_cap = max(n * 2, 256)
            self._cells_xy_buf = np.empty((self._cells_buf_cap, 2), dtype=np.float32)
            self._cells_mass_buf = np.empty(self._cells_buf_cap, dtype=np.float32)
            self._cells_pid_buf = np.empty(self._cells_buf_cap, dtype=np.int32)
            self._cells_r_buf = np.empty(self._cells_buf_cap, dtype=np.float32)

        p_cells = self._player_cells_cache
        p_mass = self._player_mass_cache
        p_cent = self._player_centroid_cache
        xy_buf = self._cells_xy_buf
        m_buf = self._cells_mass_buf
        pid_buf = self._cells_pid_buf
        r_buf = self._cells_r_buf

        accum: Dict[int, List[float]] = {}

        for i, c in enumerate(self.cells):
            pid = c.player_id
            cx, cy, cm, cr = c.x, c.y, c.mass, c.radius
            xy_buf[i, 0] = cx
            xy_buf[i, 1] = cy
            m_buf[i] = cm
            pid_buf[i] = pid
            r_buf[i] = cr
            p_cells.setdefault(pid, []).append(c)

            if pid not in accum:
                accum[pid] = [cm, cx * cm, cy * cm, cx, cy, cr]
            else:
                acc = accum[pid]
                acc[0] += cm
                acc[1] += cx * cm
                acc[2] += cy * cm

        self.cells_xy = xy_buf[:n]
        self.cells_mass = m_buf[:n]
        self.cells_pid = pid_buf[:n]
        self.cells_r = r_buf[:n]

        scale = self.radius_scale
        for pid, acc in accum.items():
            tm = acc[0]
            p_mass[pid] = tm
            if tm > 0.0:
                cx = acc[1] / tm
                cy = acc[2] / tm
                eff_radius = scale * math.sqrt(tm)
            else:
                cx, cy, eff_radius = acc[3], acc[4], acc[5]
            p_cent[pid] = (float(cx), float(cy), float(eff_radius))

        self._cells_cache_valid = True

    def get_player_cells(self, player_id: int) -> List[Cell]:
        """Return all active cells belonging to a specific player (O(1) cached)."""
        if not self._cells_cache_valid:
            self._refresh_player_cache()
        return self._player_cells_cache.get(player_id, [])

    def get_player_mass(self, player_id: int) -> float:
        """Compute the total mass of a player across all their subcells (O(1) cached)."""
        if not self._cells_cache_valid:
            self._refresh_player_cache()
        return self._player_mass_cache.get(player_id, 0.0)

    def get_player_centroid(self, player_id: int) -> Tuple[float, float, float]:
        """Compute the mass-weighted centroid (x, y) and effective radius of a player (O(1) cached)."""
        if not self._cells_cache_valid:
            self._refresh_player_cache()
        return self._player_centroid_cache.get(player_id, (self.width / 2.0, self.height / 2.0, 10.0))

    def _compute_remerge_cooldown(self, mass: float) -> int:
        """Compute remerge cooldown ticks based on base ticks and cell mass."""
        if self.remerge_cooldown_ticks <= 10:
            return self.remerge_cooldown_ticks
        return int(self.remerge_cooldown_ticks + mass * self.remerge_cooldown_mass_factor)

    def _execute_split(self, player_id: int, target_raw: np.ndarray) -> int:
        """Split player cells into halves along target direction or towards target coordinate."""
        p_cells = self.get_player_cells(player_id)
        if not p_cells:
            return 0

        # Check if target_raw is normalized direction [-1, 1] or world coordinates
        is_normalized = (abs(float(target_raw[0])) <= 1.05 and abs(float(target_raw[1])) <= 1.05)
        if is_normalized:
            norm = np.linalg.norm(target_raw)
            default_dir = target_raw / norm if norm > 1e-6 else np.array([1.0, 0.0], dtype=np.float32)
        else:
            default_dir = None

        new_cells: List[Cell] = []
        splits_performed = 0

        # Sort cells by mass descending so largest split first
        p_cells.sort(key=lambda c: c.mass, reverse=True)

        current_total = len(p_cells)
        for cell in p_cells:
            if current_total >= self.max_subcells:
                break
            if cell.mass >= self.min_split_mass:  # Tactical threshold: produces viable offensive pieces (>= 27.5)
                half_mass = cell.mass / 2.0
                cell.mass = half_mass
                cooldown = self._compute_remerge_cooldown(half_mass)
                cell.remerge_cooldown = cooldown

                if default_dir is not None:
                    dir_norm = default_dir
                else:
                    cdx = float(target_raw[0]) - cell.x
                    cdy = float(target_raw[1]) - cell.y
                    cdist = math.hypot(cdx, cdy)
                    if cdist > 1e-6:
                        dir_norm = np.array([cdx / cdist, cdy / cdist], dtype=np.float32)
                    else:
                        dir_norm = np.array([1.0, 0.0], dtype=np.float32)

                # Projected new cell with boost
                r = cell.radius
                proj_x = float(np.clip(cell.x + dir_norm[0] * (r + 10.0), r, self.width - r))
                proj_y = float(np.clip(cell.y + dir_norm[1] * (r + 10.0), r, self.height - r))

                proj_cell = Cell(
                    id=self._next_cell_id,
                    player_id=player_id,
                    x=proj_x,
                    y=proj_y,
                    mass=half_mass,
                    vx=cell.vx,
                    vy=cell.vy,
                    boost_vx=float(dir_norm[0] * self.split_boost_speed),
                    boost_vy=float(dir_norm[1] * self.split_boost_speed),
                    remerge_cooldown=cooldown,
                )
                self._next_cell_id += 1
                new_cells.append(proj_cell)
                current_total += 1
                splits_performed += 1

        if new_cells:
            self.cells.extend(new_cells)
            self._cells_cache_valid = False
        return splits_performed

    def _execute_eject(self, player_id: int, target_raw: np.ndarray) -> int:
        """Eject mass from player cells towards target direction or target coordinate."""
        p_cells = self.get_player_cells(player_id)
        if not p_cells:
            return 0

        is_normalized = (abs(float(target_raw[0])) <= 1.05 and abs(float(target_raw[1])) <= 1.05)
        if is_normalized:
            norm = np.linalg.norm(target_raw)
            default_dir = target_raw / norm if norm > 1e-6 else np.array([1.0, 0.0], dtype=np.float32)
        else:
            default_dir = None

        ejected_count = 0
        for cell in p_cells:
            if cell.mass >= (self.eject_loss_mass + 10.0):
                cell.mass -= self.eject_loss_mass

                if default_dir is not None:
                    dir_norm = default_dir
                else:
                    cdx = float(target_raw[0]) - cell.x
                    cdy = float(target_raw[1]) - cell.y
                    cdist = math.hypot(cdx, cdy)
                    if cdist > 1e-6:
                        dir_norm = np.array([cdx / cdist, cdy / cdist], dtype=np.float32)
                    else:
                        dir_norm = np.array([1.0, 0.0], dtype=np.float32)

                r = cell.radius
                spawn_x = float(np.clip(cell.x + dir_norm[0] * (r + 15.0), 5.0, self.width - 5.0))
                spawn_y = float(np.clip(cell.y + dir_norm[1] * (r + 15.0), 5.0, self.height - 5.0))

                eject_piece = EjectedMass(
                    id=self._next_ejected_id,
                    player_id=player_id,
                    x=spawn_x,
                    y=spawn_y,
                    vx=float(dir_norm[0] * 18.0),
                    vy=float(dir_norm[1] * 18.0),
                    mass=self.eject_spawn_mass,
                    ticks_remaining=15,
                )
                self._next_ejected_id += 1
                self.ejected.append(eject_piece)
                ejected_count += 1

        return ejected_count

    def _explode_cell_on_virus(self, cell: Cell) -> None:
        """Explode a cell that collided with a virus into fragments up to max_subcells."""
        player_id = cell.player_id
        p_cells = self.get_player_cells(player_id)
        available_slots = self.max_subcells - len(p_cells)
        if available_slots <= 0:
            return

        # Explode into min(available_slots, max(2, int(mass / 20))) pieces
        num_pieces = min(available_slots + 1, max(2, int(cell.mass / 25.0)))
        piece_mass = cell.mass / num_pieces
        cell.mass = piece_mass
        cooldown = self._compute_remerge_cooldown(piece_mass)
        cell.remerge_cooldown = cooldown

        angles = np.linspace(0, 2 * np.pi, num_pieces, endpoint=False)
        for i in range(1, num_pieces):
            ang = angles[i]
            dx = math.cos(ang)
            dy = math.sin(ang)
            r = mass_to_radius(piece_mass, scale=self.radius_scale)
            nx = float(np.clip(cell.x + dx * (r + 5.0), r, self.width - r))
            ny = float(np.clip(cell.y + dy * (r + 5.0), r, self.height - r))

            frag = Cell(
                id=self._next_cell_id,
                player_id=player_id,
                x=nx,
                y=ny,
                mass=piece_mass,
                vx=cell.vx,
                vy=cell.vy,
                boost_vx=float(dx * self.split_boost_speed * 0.7),
                boost_vy=float(dy * self.split_boost_speed * 0.7),
                remerge_cooldown=cooldown,
            )
            self._next_cell_id += 1
            self.cells.append(frag)
        self._cells_cache_valid = False

    def step(self, actions: Dict[int, np.ndarray]) -> Dict[int, Dict[str, Any]]:
        """Advance the physics simulation by 1 step (vectorized).

        Args:
            actions: Dictionary mapping player_id to action array:
                     [target_x, target_y, trigger]
                     trigger: < -0.33 (none), [-0.33, 0.33] (eject), > 0.33 (split)

        Returns:
            Dictionary of event metrics per player (cells_eaten, pellets_eaten, deaths, splits).
        """
        profiling = self.profile_enabled
        phase_started = time.perf_counter() if profiling else 0.0
        if profiling:
            self.last_profile = {}

        # Initialize step stats
        unique_players = set(c.player_id for c in self.cells).union(actions.keys())
        self.step_events = {
            pid: {
                "pellets_eaten": 0,
                "cells_eaten": 0,
                "mass_eaten": 0.0,
                "subcells_lost": 0,
                "ejected_mass_eaten": 0,
                "died": False,
                "splits": 0,
                "ejects": 0,
                "virus_exploded": False,
                "virus_eaten": False,
            }
            for pid in unique_players
        }

        # 1. Process player actions (split / eject)
        for pid, act in actions.items():
            if act is None or len(act) < 3:
                continue
            trig = float(act[2])
            if trig > 0.6:
                target_vec = np.array([float(act[0]), float(act[1])], dtype=np.float32)
                splits = self._execute_split(pid, target_vec)
                self.step_events[pid]["splits"] += splits
            elif 0.2 < trig <= 0.6:
                target_vec = np.array([float(act[0]), float(act[1])], dtype=np.float32)
                ejects = self._execute_eject(pid, target_vec)
                self.step_events[pid]["ejects"] += ejects

        if profiling:
            self.last_profile["actions"] = time.perf_counter() - phase_started
            phase_started = time.perf_counter()

        # Resolve target world coordinates per player
        player_targets: Dict[int, Tuple[float, float]] = {}
        for pid in unique_players:
            act = actions.get(pid, None)
            if act is not None and len(act) >= 2:
                a0, a1 = float(act[0]), float(act[1])
                # Normalized direction or offset in [-1, 1]
                if abs(a0) <= 1.05 and abs(a1) <= 1.05:
                    cx, cy, _ = self.get_player_centroid(pid)
                    # If idle (0, 0), target is centroid exactly
                    # If non-zero, target is 400 world units along that direction
                    player_targets[pid] = (cx + a0 * 400.0, cy + a1 * 400.0)
                else:
                    # Absolute world coordinates passed directly (e.g. mouse in play_human.py)
                    player_targets[pid] = (a0, a1)
            else:
                cx, cy, _ = self.get_player_centroid(pid)
                player_targets[pid] = (cx, cy)

        # 2. Update cell movements & impulses
        for cell in self.cells:
            # Cooldown decay
            if cell.remerge_cooldown > 0:
                cell.remerge_cooldown -= 1

            tx, ty = player_targets.get(cell.player_id, (cell.x, cell.y))
            cdx = tx - cell.x
            cdy = ty - cell.y
            cdist = math.hypot(cdx, cdy)

            spd = mass_to_speed(cell.mass, v_base=self.v_base, v_min=self.v_min)

            if cdist > 0.5:
                # Smooth linear damping within 32 units to avoid jitter/orbiting (as in MultiOgar)
                factor = min(1.0, cdist / 32.0)
                step = min(cdist, spd * factor)
                cell.vx = (cdx / cdist) * step
                cell.vy = (cdy / cdist) * step
            else:
                cell.vx = 0.0
                cell.vy = 0.0

            # Apply authentic Agar.io scaling mass decay for large cells (mass > 100.0)
            if self.mass_decay_rate > 0.0 and cell.mass > 100.0:
                scale_factor = 1.0 + max(0.0, cell.mass - 100.0) / 800.0
                decay = cell.mass * self.mass_decay_rate * scale_factor
                cell.mass = max(100.0, cell.mass - decay)

        if profiling:
            self.last_profile["movement"] = time.perf_counter() - phase_started
            phase_started = time.perf_counter()

        # Centroid attraction:
        # 1. Idle grouping: when target is near centroid (e.g. mouse placed on centroid or idle action).
        # 2. SOTA / Agar.io Remerge Magnetism: when remerge_cooldown expires (== 0), subcells are
        #    actively pulled inward toward the player centroid even when moving at full speed!
        for pid in unique_players:
            p_cells = self.get_player_cells(pid)
            if len(p_cells) > 1:
                tx, ty = player_targets.get(pid, (0.0, 0.0))
                cx, cy, _ = self.get_player_centroid(pid)
                is_idle = math.hypot(tx - cx, ty - cy) < 50.0

                for c in p_cells:
                    cdx = cx - c.x
                    cdy = cy - c.y
                    cdist = math.hypot(cdx, cdy)
                    if cdist > 1.0:
                        pull = 0.0
                        if is_idle:
                            pull = min(2.5, cdist * 0.08)
                        elif c.remerge_cooldown == 0:
                            # Strong magnetic centripetal acceleration to guarantee remerge
                            pull = min(4.0, max(0.8, cdist * 0.12))

                        if pull > 0.0:
                            c.vx += (cdx / cdist) * pull
                            c.vy += (cdy / cdist) * pull

        for cell in self.cells:
            # Apply and decay split boost
            vx_total = cell.vx + cell.boost_vx
            vy_total = cell.vy + cell.boost_vy
            cell.boost_vx *= self.split_boost_decay
            cell.boost_vy *= self.split_boost_decay
            if abs(cell.boost_vx) < 0.05:
                cell.boost_vx = 0.0
            if abs(cell.boost_vy) < 0.05:
                cell.boost_vy = 0.0

            r = cell.radius
            nx = cell.x + vx_total
            ny = cell.y + vy_total
            if nx < r: cell.x = r
            elif nx > self.width - r: cell.x = self.width - r
            else: cell.x = nx

            if ny < r: cell.y = r
            elif ny > self.height - r: cell.y = self.height - r
            else: cell.y = ny

        self._cells_cache_valid = False

        if profiling:
            self.last_profile["integration"] = time.perf_counter() - phase_started
            phase_started = time.perf_counter()

        # 3. Update ejected mass movements (with authentic wall bounce)
        if self.ejected:
            surviving_ejected: List[EjectedMass] = []
            for em in self.ejected:
                nx = em.x + em.vx
                ny = em.y + em.vy
                r = em.radius
                if nx < r:
                    em.x = r
                    em.vx = -em.vx * 0.75  # Bounce off left wall
                elif nx > self.width - r:
                    em.x = self.width - r
                    em.vx = -em.vx * 0.75  # Bounce off right wall
                else:
                    em.x = nx

                if ny < r:
                    em.y = r
                    em.vy = -em.vy * 0.75  # Bounce off top wall
                elif ny > self.height - r:
                    em.y = self.height - r
                    em.vy = -em.vy * 0.75  # Bounce off bottom wall
                else:
                    em.y = ny

                em.vx *= 0.82
                em.vy *= 0.82
                em.ticks_remaining -= 1
                surviving_ejected.append(em)
            self.ejected = surviving_ejected

        # 4. Intra-player cell overlap & remerge
        self._resolve_intra_player_remerge()

        if profiling:
            self.last_profile["remerge"] = time.perf_counter() - phase_started
            phase_started = time.perf_counter()

        # 5. Cell vs Pellet collisions (Vectorized with Spatial Hashing)
        self._resolve_pellet_collisions()

        if profiling:
            self.last_profile["pellets"] = time.perf_counter() - phase_started
            phase_started = time.perf_counter()

        # 6. Cell vs Ejected mass collisions
        self._resolve_ejected_collisions()

        if profiling:
            self.last_profile["ejected"] = time.perf_counter() - phase_started
            phase_started = time.perf_counter()

        # 7. Cell vs Virus collisions
        self._resolve_virus_collisions()

        if profiling:
            self.last_profile["viruses"] = time.perf_counter() - phase_started
            phase_started = time.perf_counter()

        # 8. Cell vs Cell collisions (Predator / Prey)
        self._resolve_cell_interplay()

        if profiling:
            self.last_profile["cell_interplay"] = time.perf_counter() - phase_started

        return self.step_events

    def _resolve_intra_player_remerge(self) -> None:
        """Resolve merging or soft repulsion of sub-cells belonging to the same player."""
        if len(self.cells) < 2:
            return

        if not self._cells_cache_valid:
            self._refresh_player_cache()

        # Fast path: check if any player actually has > 1 cell (O(1) zero allocation)
        if len(self.cells) == len(self._player_cells_cache):
            return

        surviving: List[Cell] = []
        for pid, p_cells in self._player_cells_cache.items():
            if len(p_cells) <= 1:
                surviving.extend(p_cells)
                continue

            merged_ids = set()
            for i in range(len(p_cells)):
                ci = p_cells[i]
                if ci.id in merged_ids:
                    continue
                for j in range(i + 1, len(p_cells)):
                    cj = p_cells[j]
                    if cj.id in merged_ids:
                        continue

                    dx = cj.x - ci.x
                    dy = cj.y - ci.y
                    dist_sq = dx * dx + dy * dy
                    r_sum = ci.radius + cj.radius

                    dist = math.sqrt(max(1e-6, dist_sq))
                    if ci.remerge_cooldown == 0 and cj.remerge_cooldown == 0:
                        # Once timers expire, cells are allowed to slide into each other (no rigid push)
                        if ci.mass >= cj.mass:
                            c_large, c_small = ci, cj
                        else:
                            c_large, c_small = cj, ci

                        # Deep penetration absorption: center of smaller cell must enter inside the boundary of larger cell
                        absorb_threshold = c_large.radius
                        if dist < absorb_threshold:
                            c_large.mass += c_small.mass
                            merged_ids.add(c_small.id)
                            if c_small is ci:
                                break
                            continue
                        elif dist < r_sum * 1.5:
                            # Gentle mass-weighted mutual attraction: smaller cell accelerates much faster towards larger cell
                            total_m = ci.mass + cj.mass
                            pull_mag = min(3.0, max(0.4, (r_sum * 1.5 - dist) * 0.10))
                            pull_i = pull_mag * (cj.mass / total_m)
                            pull_j = pull_mag * (ci.mass / total_m)
                            nx = dx / dist
                            ny = dy / dist
                            ci.x = float(np.clip(ci.x + nx * pull_i, ci.radius, self.width - ci.radius))
                            ci.y = float(np.clip(ci.y + ny * pull_i, ci.radius, self.height - ci.radius))
                            cj.x = float(np.clip(cj.x - nx * pull_j, cj.radius, self.width - cj.radius))
                            cj.y = float(np.clip(cj.y - ny * pull_j, cj.radius, self.height - cj.radius))
                    else:
                        # Elastic rigid push apart to maintain separation while unmerged
                        # Mass-weighted: smaller cell is displaced more (Ogar physics)
                        overlap = r_sum - dist
                        if overlap > 0:
                            total_m = max(1e-4, ci.mass + cj.mass)
                            ratio_i = cj.mass / total_m
                            ratio_j = ci.mass / total_m
                            nx = dx / dist
                            ny = dy / dist
                            ci.x = float(np.clip(ci.x - nx * overlap * ratio_i, ci.radius, self.width - ci.radius))
                            ci.y = float(np.clip(ci.y - ny * overlap * ratio_i, ci.radius, self.height - ci.radius))
                            cj.x = float(np.clip(cj.x + nx * overlap * ratio_j, cj.radius, self.width - cj.radius))
                            cj.y = float(np.clip(cj.y + ny * overlap * ratio_j, cj.radius, self.height - cj.radius))

            for c in p_cells:
                if c.id not in merged_ids:
                    surviving.append(c)

        self.cells = surviving
        self._cells_cache_valid = False

    def _resolve_pellet_collisions(self) -> None:
        """High-performance vectorized pellet consumption using Numba JIT."""
        if not self.cells:
            return

        self._refresh_player_cache()
        eaten_pellet_indices, cell_counts = check_pellet_collisions_fast(
            self.pellets_xy, self.cells_xy, self.cells_r
        )
        if len(eaten_pellet_indices) == 0:
            return

        new_cells_from_cap: List[Cell] = []
        for i, c in enumerate(self.cells):
            count = int(cell_counts[i])
            if count > 0:
                c.mass += count * self.pellet_mass
                self.step_events[c.player_id]["pellets_eaten"] += count
                if c.mass > self.max_cell_mass:
                    p_cells = self.get_player_cells(c.player_id)
                    if (len(p_cells) + len(new_cells_from_cap)) < self.max_subcells:
                        half_mass = c.mass / 2.0
                        c.mass = half_mass
                        cooldown = self._compute_remerge_cooldown(half_mass)
                        c.remerge_cooldown = cooldown
                        spd = math.hypot(c.vx, c.vy)
                        sdx = c.vx / spd if spd > 1e-4 else 1.0
                        sdy = c.vy / spd if spd > 1e-4 else 0.0
                        r = c.radius
                        nx = float(np.clip(c.x + sdx * (r + 10.0), r, self.width - r))
                        ny = float(np.clip(c.y + sdy * (r + 10.0), r, self.height - r))
                        new_cell = Cell(
                            id=self._next_cell_id,
                            player_id=c.player_id,
                            x=nx,
                            y=ny,
                            mass=half_mass,
                            vx=c.vx,
                            vy=c.vy,
                            boost_vx=float(sdx * self.split_boost_speed),
                            boost_vy=float(sdy * self.split_boost_speed),
                            remerge_cooldown=cooldown,
                        )
                        self._next_cell_id += 1
                        new_cells_from_cap.append(new_cell)
                        self.step_events[c.player_id]["splits"] += 1
                    else:
                        c.mass = self.max_cell_mass

        if new_cells_from_cap:
            self.cells.extend(new_cells_from_cap)

        # Vectorized instant respawn of eaten pellets with virus halo clustering
        new_x, new_y = self._spawn_pellet_coords(len(eaten_pellet_indices))
        self.pellets_xy[eaten_pellet_indices, 0] = new_x
        self.pellets_xy[eaten_pellet_indices, 1] = new_y
        for idx, nx, ny in zip(eaten_pellet_indices, new_x, new_y):
            self.spatial_grid.update_pellet(int(idx), float(nx), float(ny))

        self._cells_cache_valid = False

    def _resolve_ejected_collisions(self) -> None:
        """Resolve consumption of ejected mass fragments by cells and viruses."""
        if not self.ejected:
            return

        ejected_xy = np.array([[em.x, em.y] for em in self.ejected], dtype=np.float32)
        surviving_ejected: List[EjectedMass] = []
        eaten_ejected_indices = set()

        # 1. Cells eat ejected mass
        if self.cells:
            for cell in self.cells:
                dx = ejected_xy[:, 0] - cell.x
                dy = ejected_xy[:, 1] - cell.y
                dists_sq = dx * dx + dy * dy
                r_sq = cell.radius * cell.radius

                eaten = np.where(dists_sq < r_sq)[0]
                for idx in eaten:
                    em = self.ejected[idx]
                    # Grace period: player cannot instantly eat their own newly ejected pellet
                    if em.player_id == cell.player_id and em.ticks_remaining > 13:
                        continue
                    if idx not in eaten_ejected_indices:
                        eaten_ejected_indices.add(idx)
                        cell.mass += em.mass
                        self.step_events[cell.player_id]["ejected_mass_eaten"] += 1

        # 2. Viruses eat ejected mass (feed virus to make it grow and shoot)
        if len(self.viruses_xy) > 0:
            new_viruses_to_add = []
            for v_idx in range(len(self.viruses_xy)):
                vx, vy = self.viruses_xy[v_idx]
                vr = self.virus_radii[v_idx]
                dx = ejected_xy[:, 0] - vx
                dy = ejected_xy[:, 1] - vy
                dists_sq = dx * dx + dy * dy
                v_r_sq = vr * vr

                eaten = np.where(dists_sq < v_r_sq)[0]
                for idx in eaten:
                    if idx not in eaten_ejected_indices:
                        eaten_ejected_indices.add(idx)
                        self.virus_masses[v_idx] += self.ejected[idx].mass
                        self.virus_radii[v_idx] = mass_to_radius(self.virus_masses[v_idx], scale=self.radius_scale)
                        # Check threshold to shoot a new virus
                        if self.virus_masses[v_idx] >= 140.0:
                            self.virus_masses[v_idx] = 100.0
                            self.virus_radii[v_idx] = self.virus_radius
                            em = self.ejected[idx]
                            em_spd = math.hypot(em.vx, em.vy)
                            if em_spd > 1e-4:
                                shoot_dx = em.vx / em_spd
                                shoot_dy = em.vy / em_spd
                            else:
                                shoot_dx, shoot_dy = 1.0, 0.0

                            # Project shot virus: check if any large cell is in the line of fire (up to 350 units)
                            hit_cell = None
                            for cell in self.cells:
                                if cell.mass > self.virus_split_threshold:
                                    cdx = cell.x - vx
                                    cdy = cell.y - vy
                                    proj = cdx * shoot_dx + cdy * shoot_dy
                                    if 0.0 < proj < 350.0:
                                        perp_sq = (cdx * cdx + cdy * cdy) - proj * proj
                                        if perp_sq < ((cell.radius + self.virus_radius) ** 2):
                                            hit_cell = cell
                                            break

                            if hit_cell is not None:
                                self.step_events[hit_cell.player_id]["virus_exploded"] = True
                                self._explode_cell_on_virus(hit_cell)
                                nvx = float(self.rng.uniform(100.0, self.width - 100.0))
                                nvy = float(self.rng.uniform(100.0, self.height - 100.0))
                            else:
                                nvx = float(np.clip(vx + shoot_dx * 280.0, 50.0, self.width - 50.0))
                                nvy = float(np.clip(vy + shoot_dy * 280.0, 50.0, self.height - 50.0))
                            new_viruses_to_add.append((nvx, nvy))

            if new_viruses_to_add:
                new_arr = np.array(new_viruses_to_add, dtype=np.float32)
                self.viruses_xy = np.vstack([self.viruses_xy, new_arr])
                self.virus_masses = np.append(self.virus_masses, np.full(len(new_viruses_to_add), 100.0, dtype=np.float32))
                self.virus_radii = np.append(self.virus_radii, np.full(len(new_viruses_to_add), self.virus_radius, dtype=np.float32))
                self.num_viruses = len(self.viruses_xy)

        for idx, em in enumerate(self.ejected):
            if idx not in eaten_ejected_indices:
                surviving_ejected.append(em)

        self.ejected = surviving_ejected

    def _resolve_virus_collisions(self) -> None:
        """Resolve collisions between cells and static viruses using Numba JIT.

        Official Agar.io Rules:
        1. If cell.mass <= virus_split_threshold:
           Cell is smaller than virus -> hides safely inside/under virus (no explosion).
        2. If cell.mass > virus_split_threshold:
           - If player ALREADY has max_subcells (16):
             Cell absorbs the virus (+virus_mass to cell) without exploding!
           - If player has < max_subcells:
             Cell EXPLODES into fragments up to max_subcells!
           In both cases, the virus is consumed and respawns elsewhere.
        """
        if not self.cells or self.num_viruses == 0:
            return

        self._refresh_player_cache()
        v_hit, c_hit = find_virus_cell_collisions_numba(
            self.viruses_xy, self.cells_xy, self.cells_r, self.cells_mass, self.virus_split_threshold
        )
        if len(v_hit) == 0:
            return

        for v_idx, c_idx in zip(v_hit, c_hit):
            if c_idx >= len(self.cells):
                continue
            cell = self.cells[c_idx]
            p_cells = self.get_player_cells(cell.player_id)
            if len(p_cells) >= self.max_subcells:
                # 16-CELL ABSORPTION: player at maximum subcell cap absorbs the virus!
                cell.mass += self.virus_mass
                self.step_events[cell.player_id]["virus_eaten"] = True
            else:
                # CELL EXPLODES into fragments
                self.step_events[cell.player_id]["virus_exploded"] = True
                self._explode_cell_on_virus(cell)

            # Virus is consumed, respawns in a new location
            self.viruses_xy[v_idx, 0] = float(self.rng.uniform(100.0, self.width - 100.0))
            self.viruses_xy[v_idx, 1] = float(self.rng.uniform(100.0, self.height - 100.0))
            self._cells_cache_valid = False

    def _resolve_cell_interplay(self) -> None:
        """Resolve consumption between different players (Predator vs Prey).

        Rule: Cell A absorbs Cell B if dist(A, B) < r_A and m_A >= 1.1 * m_B.
        Mass conservation: m_A <- m_A + m_B.
        Zero nested distance loops: JIT-compiled C search with AABB pre-filtering.
        """
        n = len(self.cells)
        if n < 2:
            return

        self._refresh_player_cache()
        eaters, preys = find_cell_eat_events_numba(
            self.cells_xy, self.cells_mass, self.cells_r, self.cells_pid, self.eat_ratio
        )
        if len(eaters) == 0:
            return

        eaten_indices = set()
        # Sort distinct eaters by mass descending for deterministic resolution
        unique_eaters = sorted(set(eaters), key=lambda idx: self.cells_mass[idx], reverse=True)

        for i in unique_eaters:
            if i in eaten_indices or i >= len(self.cells):
                continue
            for k in range(len(eaters)):
                if eaters[k] == i:
                    j = preys[k]
                    if j in eaten_indices or j >= len(self.cells):
                        continue
                    # Cell i eats cell j
                    eaten_indices.add(j)
                    eaten_mass = float(self.cells[j].mass)
                    self.cells[i].mass += eaten_mass
                    self.step_events[self.cells[i].player_id]["cells_eaten"] += 1
                    self.step_events[self.cells[i].player_id]["mass_eaten"] += eaten_mass
                    self.step_events[self.cells[j].player_id]["subcells_lost"] += 1
                    if self.cells[i].mass > self.max_cell_mass:
                        p_cells = self.get_player_cells(self.cells[i].player_id)
                        if len(p_cells) < self.max_subcells:
                            half_m = self.cells[i].mass / 2.0
                            self.cells[i].mass = half_m
                            cd = self._compute_remerge_cooldown(half_m)
                            self.cells[i].remerge_cooldown = cd
                            spd = math.hypot(self.cells[i].vx, self.cells[i].vy)
                            sdx = self.cells[i].vx / spd if spd > 1e-4 else 1.0
                            sdy = self.cells[i].vy / spd if spd > 1e-4 else 0.0
                            r = self.cells[i].radius
                            nx = float(np.clip(self.cells[i].x + sdx * (r + 10.0), r, self.width - r))
                            ny = float(np.clip(self.cells[i].y + sdy * (r + 10.0), r, self.height - r))
                            new_c = Cell(
                                id=self._next_cell_id,
                                player_id=self.cells[i].player_id,
                                x=nx,
                                y=ny,
                                mass=half_m,
                                vx=self.cells[i].vx,
                                vy=self.cells[i].vy,
                                boost_vx=float(sdx * self.split_boost_speed),
                                boost_vy=float(sdy * self.split_boost_speed),
                                remerge_cooldown=cd,
                            )
                            self._next_cell_id += 1
                            self.cells.append(new_c)
                            self.step_events[self.cells[i].player_id]["splits"] += 1
                        else:
                            self.cells[i].mass = self.max_cell_mass

        if eaten_indices:
            self.cells = [c for idx, c in enumerate(self.cells) if idx not in eaten_indices]
            self._cells_cache_valid = False

        # A player is ONLY dead when ALL their subcells have been completely eliminated
        surviving_pids = set(c.player_id for c in self.cells)
        for pid in self.step_events:
            if pid not in surviving_pids:
                self.step_events[pid]["died"] = True
