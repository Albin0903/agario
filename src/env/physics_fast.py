"""Numba JIT accelerated physics and observation kernels for Agar.io."""

from __future__ import annotations
import math
import numpy as np
import numba as nb


@nb.njit(fastmath=True)
def check_pellet_collisions_numba(
    pellets_xy: np.ndarray,
    cells_xy: np.ndarray,
    cells_r: np.ndarray,
):
    """Vectorized circle-point collision detection with AABB pre-filtering.

    Args:
        pellets_xy: (P, 2) float32 coordinates of pellets
        cells_xy: (C, 2) float32 coordinates of cells
        cells_r: (C,) float32 radii of cells

    Returns:
        pellet_eaten_by: (P,) int32 index of eater cell, or -1 if not eaten
        cell_counts: (C,) int32 number of pellets consumed per cell
    """
    num_pellets = len(pellets_xy)
    num_cells = len(cells_xy)
    pellet_eaten_by = np.full(num_pellets, -1, dtype=np.int32)
    cells_r_sq = cells_r * cells_r

    for p in range(num_pellets):
        px = pellets_xy[p, 0]
        py = pellets_xy[p, 1]
        for c in range(num_cells):
            r = cells_r[c]
            dx = px - cells_xy[c, 0]
            if abs(dx) < r:
                dy = py - cells_xy[c, 1]
                if abs(dy) < r:
                    if dx * dx + dy * dy < cells_r_sq[c]:
                        pellet_eaten_by[p] = c
                        break

    cell_counts = np.zeros(num_cells, dtype=np.int32)
    for p in range(num_pellets):
        c = pellet_eaten_by[p]
        if c >= 0:
            cell_counts[c] += 1

    return pellet_eaten_by, cell_counts


@nb.njit(fastmath=True)
def find_nearest_pellets_numba(
    cx: float,
    cy: float,
    pellets_xy: np.ndarray,
    view_r: float,
    k: int = 10,
):
    """Find up to k nearest pellets to (cx, cy) within view_r without full sort."""
    num_pellets = len(pellets_xy)
    view_r_sq = view_r * view_r

    # Fixed capacity min-heap or top-k tracker
    best_dists_sq = np.full(k, 1e12, dtype=np.float32)
    best_dx = np.zeros(k, dtype=np.float32)
    best_dy = np.zeros(k, dtype=np.float32)

    for p in range(num_pellets):
        dx = pellets_xy[p, 0] - cx
        if abs(dx) < view_r:
            dy = pellets_xy[p, 1] - cy
            if abs(dy) < view_r:
                d_sq = dx * dx + dy * dy
                if d_sq <= view_r_sq:
                    # Check if this d_sq qualifies for top-k
                    if d_sq < best_dists_sq[k - 1]:
                        # Insert in sorted order
                        idx = k - 1
                        while idx > 0 and d_sq < best_dists_sq[idx - 1]:
                            best_dists_sq[idx] = best_dists_sq[idx - 1]
                            best_dx[idx] = best_dx[idx - 1]
                            best_dy[idx] = best_dy[idx - 1]
                            idx -= 1
                        best_dists_sq[idx] = d_sq
                        best_dx[idx] = dx
                        best_dy[idx] = dy

    # Normalized relative dx, dy in [-1, 1]
    res = np.zeros(k * 2, dtype=np.float32)
    nearest_dist = -1.0
    if best_dists_sq[0] < 1e10:
        d0 = math.sqrt(max(1e-8, best_dists_sq[0]))
        nearest_dist = d0
        # High-signal unit direction towards closest food (norm = 1.0)
        res[0] = best_dx[0] / d0
        res[1] = best_dy[0] / d0

    for i in range(1, k):
        if best_dists_sq[i] < 1e10:
            val_x = best_dx[i] / view_r
            val_y = best_dy[i] / view_r
            res[i * 2] = -1.0 if val_x < -1.0 else (1.0 if val_x > 1.0 else val_x)
            res[i * 2 + 1] = -1.0 if val_y < -1.0 else (1.0 if val_y > 1.0 else val_y)

    return res, float(nearest_dist)


@nb.njit(fastmath=True)
def compute_heuristic_threat_prey(
    cx: float,
    cy: float,
    cr: float,
    my_mass: float,
    cells_xy: np.ndarray,
    cells_mass: np.ndarray,
    cells_pid: np.ndarray,
    my_pid: int,
    view_r: float,
):
    """Compute threat and prey navigation vectors in pure compiled C."""
    threat_x = 0.0
    threat_y = 0.0
    prey_dx = 0.0
    prey_dy = 0.0
    closest_prey_dist = 1e9
    closest_prey_mass = 0.0

    n = len(cells_xy)
    for i in range(n):
        if cells_pid[i] == my_pid:
            continue
        dx = cells_xy[i, 0] - cx
        if abs(dx) > view_r:
            continue
        dy = cells_xy[i, 1] - cy
        if abs(dy) > view_r:
            continue
        dist = math.hypot(dx, dy)
        if dist > view_r or dist < 1e-4:
            continue

        other_m = cells_mass[i]
        if other_m >= 1.1 * my_mass:
            weight = 1.0 / max(30.0, dist)
            threat_x -= (dx / dist) * weight
            threat_y -= (dy / dist) * weight
        elif other_m <= 0.9 * my_mass:
            if dist < closest_prey_dist:
                closest_prey_dist = dist
                closest_prey_mass = other_m
                prey_dx = dx / dist
                prey_dy = dy / dist

    return threat_x, threat_y, prey_dx, prey_dy, closest_prey_dist, closest_prey_mass


@nb.njit(fastmath=True)
def find_single_nearest_pellet_numba(
    cx: float,
    cy: float,
    pellets_xy: np.ndarray,
    max_dist: float = 350.0,
):
    """Find direction towards the single closest pellet to (cx, cy) within max_dist."""
    num_pellets = len(pellets_xy)
    max_d_sq = max_dist * max_dist
    best_dist_sq = max_d_sq
    best_dx = 0.0
    best_dy = 0.0
    found = False

    for p in range(num_pellets):
        dx = pellets_xy[p, 0] - cx
        if abs(dx) < max_dist:
            dy = pellets_xy[p, 1] - cy
            if abs(dy) < max_dist:
                d_sq = dx * dx + dy * dy
                if d_sq < best_dist_sq:
                    best_dist_sq = d_sq
                    best_dx = dx
                    best_dy = dy
                    found = True

    if found:
        dist = math.sqrt(max(1e-8, best_dist_sq))
        return True, float(best_dx / dist), float(best_dy / dist)
    return False, 0.0, 0.0


@nb.njit(fastmath=True)
def spawn_pellet_coords_fast(
    count: int,
    width: float,
    height: float,
    viruses_xy: np.ndarray,
    min_core_dist: float,
    random_floats: np.ndarray,
):
    """Ultra-fast rejection sampling of respawned pellet coordinates."""
    xs = np.empty(count, dtype=np.float32)
    ys = np.empty(count, dtype=np.float32)
    num_viruses = len(viruses_xy)
    min_core_sq = min_core_dist * min_core_dist
    rf_idx = 0
    rf_len = len(random_floats)

    for i in range(count):
        while True:
            rx = random_floats[rf_idx % rf_len] * (width - 40.0) + 20.0
            rf_idx += 1
            ry = random_floats[rf_idx % rf_len] * (height - 40.0) + 20.0
            rf_idx += 1

            valid = True
            for v in range(num_viruses):
                dx = rx - viruses_xy[v, 0]
                if abs(dx) < min_core_dist:
                    dy = ry - viruses_xy[v, 1]
                    if abs(dy) < min_core_dist:
                        if dx * dx + dy * dy < min_core_sq:
                            valid = False
                            break
            if valid:
                xs[i] = rx
                ys[i] = ry
                break
    return xs, ys

