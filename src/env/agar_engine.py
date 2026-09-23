"""Headless high-performance 2D vectorized simulation engine for Agar.io."""

from __future__ import annotations
import math
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from src.env.entities import mass_to_radius, mass_to_speed, Pellet, Virus, Cell, EjectedMass


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
        self.buckets: List[List[int]] = [[] for _ in range(self.total_cells)]
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
            self.buckets[idx].append(i)

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
            b = self.buckets[old_bucket]
            try:
                b.remove(idx)
            except ValueError:
                pass
            self.buckets[new_bucket].append(idx)
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
        num_pellets: int = 1200,
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
        remerge_cooldown_ticks: int = 300,
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
        self.remerge_cooldown_ticks = remerge_cooldown_ticks
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

        # Event tracking per step
        self.step_events: Dict[int, Dict[str, Any]] = {}

        self.reset(seed)

    def _spawn_pellet_coords(self, count: int) -> Tuple[np.ndarray, np.ndarray]:
        """Generate pellet coordinates, deflecting any pellets near viruses into a rich outer halo."""
        xs = self.rng.uniform(20.0, self.width - 20.0, size=count).astype(np.float32)
        ys = self.rng.uniform(20.0, self.height - 20.0, size=count).astype(np.float32)

        if self.num_viruses > 0 and len(self.viruses_xy) > 0:
            thresh_sq = (self.virus_radius * 1.5) ** 2
            for vx, vy in self.viruses_xy:
                dx = xs - vx
                dy = ys - vy
                dist_sq = dx * dx + dy * dy
                close_mask = dist_sq < thresh_sq
                if np.any(close_mask):
                    num_close = np.count_nonzero(close_mask)
                    # Deflect into outer ring (1.2 to 2.4 * virus_radius)
                    angles = self.rng.uniform(0.0, 2.0 * np.pi, size=num_close).astype(np.float32)
                    halo_dist = self.rng.uniform(self.virus_radius * 1.2, self.virus_radius * 2.4, size=num_close).astype(np.float32)
                    xs[close_mask] = np.clip(vx + np.cos(angles) * halo_dist, 20.0, self.width - 20.0)
                    ys[close_mask] = np.clip(vy + np.sin(angles) * halo_dist, 20.0, self.height - 20.0)

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

    def spawn_player(self, player_id: int, initial_mass: float = 20.0, xy: Optional[Tuple[float, float]] = None) -> Cell:
        """Spawn an initial single cell for a player."""
        if xy is None:
            x = float(self.rng.uniform(100.0, self.width - 100.0))
            y = float(self.rng.uniform(100.0, self.height - 100.0))
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
        return cell

    def get_player_cells(self, player_id: int) -> List[Cell]:
        """Return all active cells belonging to a specific player."""
        return [c for c in self.cells if c.player_id == player_id]

    def get_player_mass(self, player_id: int) -> float:
        """Compute the total mass of a player across all their subcells."""
        return sum(c.mass for c in self.cells if c.player_id == player_id)

    def get_player_centroid(self, player_id: int) -> Tuple[float, float, float]:
        """Compute the mass-weighted centroid (x, y) and effective radius of a player."""
        p_cells = self.get_player_cells(player_id)
        if not p_cells:
            return self.width / 2.0, self.height / 2.0, 10.0

        total_mass = sum(c.mass for c in p_cells)
        if total_mass <= 0:
            return p_cells[0].x, p_cells[0].y, p_cells[0].radius

        cx = sum(c.x * c.mass for c in p_cells) / total_mass
        cy = sum(c.y * c.mass for c in p_cells) / total_mass
        eff_radius = mass_to_radius(total_mass, scale=self.radius_scale)
        return float(cx), float(cy), float(eff_radius)

    def _execute_split(self, player_id: int, target_dir: np.ndarray) -> int:
        """Split player cells into halves along target direction."""
        p_cells = self.get_player_cells(player_id)
        if not p_cells:
            return 0

        norm = np.linalg.norm(target_dir)
        if norm > 1e-6:
            dir_norm = target_dir / norm
        else:
            dir_norm = np.array([1.0, 0.0], dtype=np.float32)

        new_cells: List[Cell] = []
        splits_performed = 0

        # Sort cells by mass descending so largest split first
        p_cells.sort(key=lambda c: c.mass, reverse=True)

        current_total = len(p_cells)
        for cell in p_cells:
            if current_total >= self.max_subcells:
                break
            if cell.mass >= 20.0:  # Must have at least 20 mass to split into two >= 10 pieces
                half_mass = cell.mass / 2.0
                cell.mass = half_mass
                cell.remerge_cooldown = self.remerge_cooldown_ticks

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
                    remerge_cooldown=self.remerge_cooldown_ticks,
                )
                self._next_cell_id += 1
                new_cells.append(proj_cell)
                current_total += 1
                splits_performed += 1

        self.cells.extend(new_cells)
        return splits_performed

    def _execute_eject(self, player_id: int, target_dir: np.ndarray) -> int:
        """Eject mass from player cells towards target direction."""
        p_cells = self.get_player_cells(player_id)
        if not p_cells:
            return 0

        norm = np.linalg.norm(target_dir)
        if norm > 1e-6:
            dir_norm = target_dir / norm
        else:
            dir_norm = np.array([1.0, 0.0], dtype=np.float32)

        ejected_count = 0
        for cell in p_cells:
            if cell.mass >= (self.eject_loss_mass + 10.0):
                cell.mass -= self.eject_loss_mass
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
        cell.remerge_cooldown = self.remerge_cooldown_ticks

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
                remerge_cooldown=self.remerge_cooldown_ticks,
            )
            self._next_cell_id += 1
            self.cells.append(frag)

    def step(self, actions: Dict[int, np.ndarray]) -> Dict[int, Dict[str, Any]]:
        """Advance the physics simulation by 1 step (vectorized).

        Args:
            actions: Dictionary mapping player_id to action array:
                     [target_x, target_y, trigger]
                     trigger: < -0.33 (none), [-0.33, 0.33] (eject), > 0.33 (split)

        Returns:
            Dictionary of event metrics per player (cells_eaten, pellets_eaten, deaths, splits).
        """
        # Initialize step stats
        unique_players = set(c.player_id for c in self.cells).union(actions.keys())
        self.step_events = {
            pid: {
                "pellets_eaten": 0,
                "cells_eaten": 0,
                "ejected_mass_eaten": 0,
                "died": False,
                "splits": 0,
                "ejects": 0,
            }
            for pid in unique_players
        }

        # 1. Process player actions (split / eject)
        for pid, act in actions.items():
            if act is None or len(act) < 3:
                continue
            trig = float(act[2])
            if trig > 0.33:
                target_vec = np.array([float(act[0]), float(act[1])], dtype=np.float32)
                splits = self._execute_split(pid, target_vec)
                self.step_events[pid]["splits"] += splits
            elif -0.33 <= trig <= 0.33:
                target_vec = np.array([float(act[0]), float(act[1])], dtype=np.float32)
                ejects = self._execute_eject(pid, target_vec)
                self.step_events[pid]["ejects"] += ejects

        # 2. Update cell movements & impulses
        for cell in self.cells:
            # Cooldown decay
            if cell.remerge_cooldown > 0:
                cell.remerge_cooldown -= 1

            act = actions.get(cell.player_id, None)
            if act is not None:
                tx, ty = float(act[0]), float(act[1])
                target_dist = math.hypot(tx, ty)
                if target_dist > 1e-4:
                    target_dir_x = tx / target_dist
                    target_dir_y = ty / target_dist
                else:
                    target_dir_x, target_dir_y = 0.0, 0.0
            else:
                target_dir_x, target_dir_y = 0.0, 0.0

            spd = mass_to_speed(cell.mass, v_base=self.v_base, v_min=self.v_min)
            cell.vx = target_dir_x * spd
            cell.vy = target_dir_y * spd

            # Apply slow mass decay for cells above min mass
            if self.mass_decay_rate > 0.0 and cell.mass > 20.0:
                decay = cell.mass * self.mass_decay_rate
                cell.mass = max(20.0, cell.mass - decay)

        # Natural centroid attraction when stationary / idle (subcells rejoin smoothly)
        for pid in unique_players:
            p_cells = self.get_player_cells(pid)
            if len(p_cells) > 1:
                act = actions.get(pid, None)
                is_idle = True
                if act is not None and len(act) >= 2:
                    if math.hypot(float(act[0]), float(act[1])) > 0.05:
                        is_idle = False
                if is_idle:
                    cx = sum(c.x for c in p_cells) / len(p_cells)
                    cy = sum(c.y for c in p_cells) / len(p_cells)
                    for c in p_cells:
                        cdx = cx - c.x
                        cdy = cy - c.y
                        cdist = math.hypot(cdx, cdy)
                        if cdist > 2.0:
                            pull = min(2.5, cdist * 0.08)
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

        # 3. Update ejected mass movements
        if self.ejected:
            surviving_ejected: List[EjectedMass] = []
            for em in self.ejected:
                nx = em.x + em.vx
                ny = em.y + em.vy
                r = em.radius
                if nx < r: em.x = r
                elif nx > self.width - r: em.x = self.width - r
                else: em.x = nx

                if ny < r: em.y = r
                elif ny > self.height - r: em.y = self.height - r
                else: em.y = ny

                em.vx *= 0.8
                em.vy *= 0.8
                em.ticks_remaining -= 1
                surviving_ejected.append(em)
            self.ejected = surviving_ejected

        # 4. Intra-player cell overlap & remerge
        self._resolve_intra_player_remerge()

        # 5. Cell vs Pellet collisions (Vectorized with Spatial Hashing)
        self._resolve_pellet_collisions()

        # 6. Cell vs Ejected mass collisions
        self._resolve_ejected_collisions()

        # 7. Cell vs Virus collisions
        self._resolve_virus_collisions()

        # 8. Cell vs Cell collisions (Predator / Prey)
        self._resolve_cell_interplay()

        return self.step_events

    def _resolve_intra_player_remerge(self) -> None:
        """Resolve merging or soft repulsion of sub-cells belonging to the same player."""
        if len(self.cells) < 2:
            return

        # Fast path: check if any player actually has > 1 cell
        pids = [c.player_id for c in self.cells]
        if len(pids) == len(set(pids)):
            return

        # Group cells by player
        player_groups: Dict[int, List[Cell]] = {}
        for c in self.cells:
            player_groups.setdefault(c.player_id, []).append(c)

        surviving: List[Cell] = []
        for pid, p_cells in player_groups.items():
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

                    if dist_sq < (r_sum * r_sum):
                        dist = math.sqrt(max(1e-6, dist_sq))
                        # If both cooldowns expired, merge smaller into larger!
                        if ci.remerge_cooldown == 0 and cj.remerge_cooldown == 0:
                            if ci.mass >= cj.mass:
                                ci.mass += cj.mass
                                merged_ids.add(cj.id)
                            else:
                                cj.mass += ci.mass
                                merged_ids.add(ci.id)
                                break
                        else:
                            # Elastic soft push apart to maintain separation while unmerged
                            overlap = (r_sum - dist) * 0.6
                            nx = dx / dist
                            ny = dy / dist
                            ci.x = float(np.clip(ci.x - nx * overlap, ci.radius, self.width - ci.radius))
                            ci.y = float(np.clip(ci.y - ny * overlap, ci.radius, self.height - ci.radius))
                            cj.x = float(np.clip(cj.x + nx * overlap, cj.radius, self.width - cj.radius))
                            cj.y = float(np.clip(cj.y + ny * overlap, cj.radius, self.height - cj.radius))
                    elif ci.remerge_cooldown == 0 and cj.remerge_cooldown == 0:
                        # Magnetic attraction force when remerge cooldown has expired
                        dist = math.sqrt(max(1e-6, dist_sq))
                        if dist < (r_sum * 2.5):
                            pull = 1.0 * (1.0 - dist / (r_sum * 2.5))
                            nx = dx / dist
                            ny = dy / dist
                            ci.x = float(np.clip(ci.x + nx * pull, ci.radius, self.width - ci.radius))
                            ci.y = float(np.clip(ci.y + ny * pull, ci.radius, self.height - ci.radius))
                            cj.x = float(np.clip(cj.x - nx * pull, cj.radius, self.width - cj.radius))
                            cj.y = float(np.clip(cj.y - ny * pull, cj.radius, self.height - cj.radius))

            for c in p_cells:
                if c.id not in merged_ids:
                    surviving.append(c)

        self.cells = surviving

    def _resolve_pellet_collisions(self) -> None:
        """Vectorized pellet consumption using spatial hash grid queries."""
        if not self.cells:
            return

        pellets_respawn_idx: List[int] = []

        # Query candidates for each cell
        for cell in self.cells:
            candidates = self.spatial_grid.query_circle(cell.x, cell.y, cell.radius)
            if not candidates:
                continue

            cand_idx = np.array(candidates, dtype=np.int32)
            cand_xy = self.pellets_xy[cand_idx]
            dx = cand_xy[:, 0] - cell.x
            dy = cand_xy[:, 1] - cell.y
            dist_sq = dx * dx + dy * dy
            r_sq = cell.radius * cell.radius

            eaten_mask = dist_sq < r_sq
            eaten_indices = cand_idx[eaten_mask]

            if len(eaten_indices) > 0:
                num_eaten = len(eaten_indices)
                cell.mass += num_eaten * self.pellet_mass
                self.step_events[cell.player_id]["pellets_eaten"] += num_eaten
                pellets_respawn_idx.extend(eaten_indices.tolist())

        # Vectorized instant respawn of eaten pellets with virus halo clustering
        if pellets_respawn_idx:
            unique_respawn = np.unique(pellets_respawn_idx)
            new_x, new_y = self._spawn_pellet_coords(len(unique_respawn))
            self.pellets_xy[unique_respawn, 0] = new_x
            self.pellets_xy[unique_respawn, 1] = new_y
            for idx, nx, ny in zip(unique_respawn, new_x, new_y):
                self.spatial_grid.update_pellet(int(idx), float(nx), float(ny))

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
                    if idx not in eaten_ejected_indices:
                        eaten_ejected_indices.add(idx)
                        cell.mass += self.ejected[idx].mass
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

                            nvx = float(np.clip(vx + shoot_dx * 200.0, 50.0, self.width - 50.0))
                            nvy = float(np.clip(vy + shoot_dy * 200.0, 50.0, self.height - 50.0))
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
        """Resolve collisions between cells and static viruses."""
        if not self.cells:
            return

        # Fast skip: viruses only explode cells with mass > virus_split_threshold
        if not any(c.mass > self.virus_split_threshold for c in self.cells):
            return

        cell_xy = np.array([[c.x, c.y] for c in self.cells], dtype=np.float32)
        cell_r = np.array([c.radius for c in self.cells], dtype=np.float32)
        cell_r_sq = cell_r * cell_r

        for v_idx in range(self.num_viruses):
            vx, vy = self.viruses_xy[v_idx]
            dx = cell_xy[:, 0] - vx
            dy = cell_xy[:, 1] - vy
            dist_sq = dx * dx + dy * dy

            for c_idx, cell in enumerate(list(self.cells)):
                if c_idx < len(dist_sq) and dist_sq[c_idx] < cell_r_sq[c_idx]:
                    if cell.mass > self.virus_split_threshold:
                        self._explode_cell_on_virus(cell)
                        self.viruses_xy[v_idx, 0] = float(self.rng.uniform(100.0, self.width - 100.0))
                        self.viruses_xy[v_idx, 1] = float(self.rng.uniform(100.0, self.height - 100.0))
                        return

    def _resolve_cell_interplay(self) -> None:
        """Resolve consumption between different players (Predator vs Prey).

        Rule: Cell A absorbs Cell B if dist(A, B) < r_A and m_A >= 1.1 * m_B.
        Mass conservation: m_A <- m_A + m_B.
        Zero nested distance loops: fully vectorized NumPy pairwise distance matrix.
        """
        n = len(self.cells)
        if n < 2:
            return

        xy = np.array([[c.x, c.y] for c in self.cells], dtype=np.float32)
        masses = np.array([c.mass for c in self.cells], dtype=np.float32)
        radii = np.array([c.radius for c in self.cells], dtype=np.float32)
        pids = np.array([c.player_id for c in self.cells], dtype=np.int32)

        # Pairwise displacement: shape (n, n, 2)
        diff = xy[:, np.newaxis, :] - xy[np.newaxis, :, :]
        dx = diff[:, :, 0]
        dy = diff[:, :, 1]
        dist_sq = dx * dx + dy * dy

        # Condition 1: different players
        diff_player = pids[:, np.newaxis] != pids[np.newaxis, :]
        # Condition 2: m_A >= 1.1 * m_B
        can_eat_mass = masses[:, np.newaxis] >= (self.eat_ratio * masses[np.newaxis, :])
        # Condition 3: dist(A, B) < r_A
        within_reach = dist_sq < (radii[:, np.newaxis] * radii[:, np.newaxis])

        # Composite eat matrix: eat_matrix[i, j] is True if cell i eats cell j
        eat_matrix = diff_player & can_eat_mass & within_reach

        eaten_indices = set()
        # Sort potential eaters by mass descending for deterministic resolution
        eater_candidates = np.where(np.any(eat_matrix, axis=1))[0]
        eater_candidates = sorted(eater_candidates, key=lambda idx: masses[idx], reverse=True)

        for i in eater_candidates:
            if i in eaten_indices:
                continue
            preys = np.where(eat_matrix[i])[0]
            for j in preys:
                if j in eaten_indices:
                    continue
                # Cell i eats cell j
                eaten_indices.add(j)
                self.cells[i].mass += self.cells[j].mass
                self.step_events[self.cells[i].player_id]["cells_eaten"] += 1
                self.step_events[self.cells[j].player_id]["died"] = True

        if eaten_indices:
            self.cells = [c for idx, c in enumerate(self.cells) if idx not in eaten_indices]
