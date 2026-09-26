"""Numba JIT accelerated physics and observation kernels for Agar.io."""

from __future__ import annotations
import math
import numpy as np
import numba as nb


@nb.njit(cache=True)
def resolve_same_player_cell_interactions_numba(
    xy: np.ndarray,
    mass: np.ndarray,
    cooldown: np.ndarray,
    group_offsets: np.ndarray,
    width: float,
    height: float,
):
    """Resolve same-player subcell merge, attraction and separation natively.

    `xy`, `mass`, and `cooldown` contain only players with multiple cells,
    grouped by the half-open ranges in `group_offsets`. Pair iteration order
    matches AgarEngine's prior Python implementation.
    """
    count = len(mass)
    merged = np.zeros(count, dtype=np.bool_)
    for group in range(len(group_offsets) - 1):
        start = group_offsets[group]
        stop = group_offsets[group + 1]
        for i in range(start, stop):
            if merged[i]:
                continue
            for j in range(i + 1, stop):
                if merged[j]:
                    continue

                dx = xy[j, 0] - xy[i, 0]
                dy = xy[j, 1] - xy[i, 1]
                dist_sq = dx * dx + dy * dy
                r_i = math.sqrt(max(mass[i], 1.0)) * 3.0
                r_j = math.sqrt(max(mass[j], 1.0)) * 3.0
                r_sum = r_i + r_j

                if cooldown[i] == 0 and cooldown[j] == 0:
                    if mass[i] >= mass[j]:
                        large = i
                        small = j
                    else:
                        large = j
                        small = i
                    r_large = math.sqrt(max(mass[large], 1.0)) * 3.0

                    if dist_sq < r_large * r_large:
                        mass[large] += mass[small]
                        merged[small] = True
                        if small == i:
                            break
                        continue
                    elif dist_sq < (r_sum * 1.5) ** 2:
                        dist = math.sqrt(max(1e-6, dist_sq))
                        inv_d = 1.0 / dist
                        nx = dx * inv_d
                        ny = dy * inv_d
                        total_mass = mass[i] + mass[j]
                        pull = min(3.0, max(0.4, (r_sum * 1.5 - dist) * 0.10))
                        pull_i = pull * (mass[j] / total_mass)
                        pull_j = pull * (mass[i] / total_mass)
                        xy[i, 0] = max(r_i, min(width - r_i, xy[i, 0] + nx * pull_i))
                        xy[i, 1] = max(r_i, min(height - r_i, xy[i, 1] + ny * pull_i))
                        xy[j, 0] = max(r_j, min(width - r_j, xy[j, 0] - nx * pull_j))
                        xy[j, 1] = max(r_j, min(height - r_j, xy[j, 1] - ny * pull_j))
                elif dist_sq < r_sum * r_sum:
                    dist = math.sqrt(max(1e-6, dist_sq))
                    inv_d = 1.0 / dist
                    nx = dx * inv_d
                    ny = dy * inv_d
                    overlap = r_sum - dist
                    total_mass = max(1e-4, mass[i] + mass[j])
                    ratio_i = mass[j] / total_mass
                    ratio_j = mass[i] / total_mass
                    xy[i, 0] = max(r_i, min(width - r_i, xy[i, 0] - nx * overlap * ratio_i))
                    xy[i, 1] = max(r_i, min(height - r_i, xy[i, 1] - ny * overlap * ratio_i))
                    xy[j, 0] = max(r_j, min(width - r_j, xy[j, 0] + nx * overlap * ratio_j))
                    xy[j, 1] = max(r_j, min(height - r_j, xy[j, 1] + ny * overlap * ratio_j))
    return merged


@nb.njit(fastmath=True)
def check_pellet_collisions_numba(
    pellets_xy: np.ndarray,
    cells_xy: np.ndarray,
    cells_r: np.ndarray,
):
    """Vectorized circle-point collision detection with AABB pre-filtering."""
    num_pellets = len(pellets_xy)
    num_cells = len(cells_xy)
    pellet_eaten_by = np.full(num_pellets, -1, dtype=np.int32)
    cell_counts = np.zeros(num_cells, dtype=np.int32)
    if num_cells == 0 or num_pellets == 0:
        return pellet_eaten_by, cell_counts

    min_x = 1e9
    max_x = -1e9
    min_y = 1e9
    max_y = -1e9
    for c in range(num_cells):
        cx = cells_xy[c, 0]
        cy = cells_xy[c, 1]
        r = cells_r[c]
        if cx - r < min_x: min_x = cx - r
        if cx + r > max_x: max_x = cx + r
        if cy - r < min_y: min_y = cy - r
        if cy + r > max_y: max_y = cy + r

    cells_r_sq = cells_r * cells_r

    for p in range(num_pellets):
        px = pellets_xy[p, 0]
        if px < min_x or px > max_x:
            continue
        py = pellets_xy[p, 1]
        if py < min_y or py > max_y:
            continue

        for c in range(num_cells):
            r = cells_r[c]
            dx = px - cells_xy[c, 0]
            if abs(dx) < r:
                dy = py - cells_xy[c, 1]
                if abs(dy) < r:
                    if dx * dx + dy * dy < cells_r_sq[c]:
                        pellet_eaten_by[p] = c
                        cell_counts[c] += 1
                        break

    return pellet_eaten_by, cell_counts


@nb.njit(fastmath=True)
def check_pellet_collisions_fast(
    pellets_xy: np.ndarray,
    cells_xy: np.ndarray,
    cells_r: np.ndarray,
):
    """Zero-allocation pellet collision detection with cell-envelope broadphase.

    Returns:
        eaten_pellet_ids: (K,) int32 indices of pellets eaten this step
        cell_counts: (C,) int32 number of pellets eaten by each cell
    """
    num_pellets = len(pellets_xy)
    num_cells = len(cells_xy)
    if num_cells == 0 or num_pellets == 0:
        return np.empty(0, dtype=np.int32), np.zeros(num_cells, dtype=np.int32)

    min_x = 1e9
    max_x = -1e9
    min_y = 1e9
    max_y = -1e9
    for c in range(num_cells):
        cx = cells_xy[c, 0]
        cy = cells_xy[c, 1]
        r = cells_r[c]
        if cx - r < min_x: min_x = cx - r
        if cx + r > max_x: max_x = cx + r
        if cy - r < min_y: min_y = cy - r
        if cy + r > max_y: max_y = cy + r

    eaten_pellet_ids = np.empty(num_pellets, dtype=np.int32)
    cell_counts = np.zeros(num_cells, dtype=np.int32)
    eaten_count = 0
    cells_r_sq = cells_r * cells_r

    for p in range(num_pellets):
        px = pellets_xy[p, 0]
        if px < min_x or px > max_x:
            continue
        py = pellets_xy[p, 1]
        if py < min_y or py > max_y:
            continue

        for c in range(num_cells):
            r = cells_r[c]
            dx = px - cells_xy[c, 0]
            if abs(dx) < r:
                dy = py - cells_xy[c, 1]
                if abs(dy) < r:
                    if dx * dx + dy * dy < cells_r_sq[c]:
                        eaten_pellet_ids[eaten_count] = p
                        cell_counts[c] += 1
                        eaten_count += 1
                        break

    return eaten_pellet_ids[:eaten_count], cell_counts


@nb.njit(cache=True)
def check_pellet_collisions_grid_numba(
    pellets_xy: np.ndarray,
    cells_xy: np.ndarray,
    cells_r: np.ndarray,
    width: float,
    height: float,
    grid_cell_size: float,
):
    """Pellet broadphase using a compact uniform grid built in compiled code.

    Cells are visited in original order, so a pellet covered by multiple
    cells is assigned to the same first cell as the former pellet-major loop.
    Returned eaten indices are sorted to preserve deterministic respawn order.
    """
    num_pellets = len(pellets_xy)
    num_cells = len(cells_xy)
    cell_counts = np.zeros(num_cells, dtype=np.int32)
    if num_cells == 0 or num_pellets == 0:
        return np.empty(0, dtype=np.int32), cell_counts

    cols = max(1, int(math.ceil(width / grid_cell_size)))
    rows = max(1, int(math.ceil(height / grid_cell_size)))
    bucket_count = cols * rows
    counts = np.zeros(bucket_count, dtype=np.int32)
    pellet_bucket = np.empty(num_pellets, dtype=np.int32)
    inv_size = 1.0 / grid_cell_size

    for p in range(num_pellets):
        col = min(cols - 1, max(0, int(pellets_xy[p, 0] * inv_size)))
        row = min(rows - 1, max(0, int(pellets_xy[p, 1] * inv_size)))
        bucket = row * cols + col
        pellet_bucket[p] = bucket
        counts[bucket] += 1

    offsets = np.empty(bucket_count + 1, dtype=np.int32)
    offsets[0] = 0
    for bucket in range(bucket_count):
        offsets[bucket + 1] = offsets[bucket] + counts[bucket]
    cursors = offsets[:-1].copy()
    items = np.empty(num_pellets, dtype=np.int32)
    for p in range(num_pellets):
        bucket = pellet_bucket[p]
        items[cursors[bucket]] = p
        cursors[bucket] += 1

    eaten = np.zeros(num_pellets, dtype=np.bool_)
    eaten_indices = np.empty(num_pellets, dtype=np.int32)
    eaten_count = 0
    for c in range(num_cells):
        cx = cells_xy[c, 0]
        cy = cells_xy[c, 1]
        radius = cells_r[c]
        radius_sq = radius * radius
        min_col = max(0, int(math.floor((cx - radius) * inv_size)))
        max_col = min(cols - 1, int(math.floor((cx + radius) * inv_size)))
        min_row = max(0, int(math.floor((cy - radius) * inv_size)))
        max_row = min(rows - 1, int(math.floor((cy + radius) * inv_size)))
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                bucket = row * cols + col
                for offset in range(offsets[bucket], offsets[bucket + 1]):
                    p = items[offset]
                    if eaten[p]:
                        continue
                    dx = pellets_xy[p, 0] - cx
                    dy = pellets_xy[p, 1] - cy
                    if dx * dx + dy * dy < radius_sq:
                        eaten[p] = True
                        cell_counts[c] += 1
                        eaten_indices[eaten_count] = p
                        eaten_count += 1

    eaten_indices = np.sort(eaten_indices[:eaten_count])
    return eaten_indices, cell_counts


@nb.njit(fastmath=True)
def find_virus_cell_collisions_numba(
    viruses_xy: np.ndarray,
    cells_xy: np.ndarray,
    cells_r: np.ndarray,
    cells_mass: np.ndarray,
    split_threshold: float,
):
    """Detect collisions between large cells and viruses in pure compiled C.

    Returns:
        v_hit: (K,) int32 virus indices consumed
        c_hit: (K,) int32 cell indices that struck the virus
    """
    num_viruses = len(viruses_xy)
    num_cells = len(cells_xy)
    v_hit = np.empty(num_viruses, dtype=np.int32)
    c_hit = np.empty(num_viruses, dtype=np.int32)
    count = 0

    for v in range(num_viruses):
        vx = viruses_xy[v, 0]
        vy = viruses_xy[v, 1]
        for c in range(num_cells):
            if cells_mass[c] <= split_threshold:
                continue
            r = cells_r[c]
            dx = cells_xy[c, 0] - vx
            if abs(dx) < r:
                dy = cells_xy[c, 1] - vy
                if abs(dy) < r:
                    if dx * dx + dy * dy < r * r:
                        v_hit[count] = v
                        c_hit[count] = c
                        count += 1
                        break
    return v_hit[:count], c_hit[:count]


@nb.njit(fastmath=True)
def find_cell_eat_events_numba(
    cells_xy: np.ndarray,
    cells_mass: np.ndarray,
    cells_r: np.ndarray,
    cells_pid: np.ndarray,
    eat_ratio: float = 1.1,
):
    """Detect consumption pairs (predator eats prey) in compiled C with zero allocations.

    Returns:
        eaters: (K,) int32 indices of eating cells
        preys: (K,) int32 indices of consumed cells
    """
    n = len(cells_xy)
    eaters = np.empty(n * 2, dtype=np.int32)
    preys = np.empty(n * 2, dtype=np.int32)
    count = 0

    for i in range(n):
        pid_i = cells_pid[i]
        m_i = cells_mass[i]
        r_i = cells_r[i]
        r_i_sq = r_i * r_i
        xi = cells_xy[i, 0]
        yi = cells_xy[i, 1]

        for j in range(n):
            if i == j or cells_pid[j] == pid_i:
                continue
            if m_i < eat_ratio * cells_mass[j]:
                continue
            dx = xi - cells_xy[j, 0]
            if abs(dx) < r_i:
                dy = yi - cells_xy[j, 1]
                if abs(dy) < r_i:
                    if dx * dx + dy * dy < r_i_sq:
                        eaters[count] = i
                        preys[count] = j
                        count += 1
                        if count >= len(eaters):
                            break
        if count >= len(eaters):
            break

    return eaters[:count], preys[:count]


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
        dy = pellets_xy[p, 1] - cy
        d_sq = dx * dx + dy * dy
        if d_sq <= view_r_sq and d_sq < best_dists_sq[k - 1]:
            # Insert in sorted order.
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
def find_nearest_pellets_candidates_numba(
    cx: float,
    cy: float,
    pellets_xy: np.ndarray,
    candidate_indices: np.ndarray,
    view_r: float,
    k: int = 10,
):
    """Find nearest pellets from spatial-grid candidates instead of all pellets."""
    view_r_sq = view_r * view_r
    best_dists_sq = np.full(k, 1e12, dtype=np.float32)
    best_dx = np.zeros(k, dtype=np.float32)
    best_dy = np.zeros(k, dtype=np.float32)

    for candidate in candidate_indices:
        p = int(candidate)
        dx = pellets_xy[p, 0] - cx
        dy = pellets_xy[p, 1] - cy
        d_sq = dx * dx + dy * dy
        if d_sq <= view_r_sq and d_sq < best_dists_sq[k - 1]:
            idx = k - 1
            while idx > 0 and d_sq < best_dists_sq[idx - 1]:
                best_dists_sq[idx] = best_dists_sq[idx - 1]
                best_dx[idx] = best_dx[idx - 1]
                best_dy[idx] = best_dy[idx - 1]
                idx -= 1
            best_dists_sq[idx] = d_sq
            best_dx[idx] = dx
            best_dy[idx] = dy

    res = np.zeros(k * 2, dtype=np.float32)
    nearest_dist = -1.0
    if best_dists_sq[0] < 1e10:
        d0 = math.sqrt(max(1e-8, best_dists_sq[0]))
        nearest_dist = d0
        res[0] = best_dx[0] / d0
        res[1] = best_dy[0] / d0

    for i in range(1, k):
        if best_dists_sq[i] < 1e10:
            res[i * 2] = max(-1.0, min(1.0, best_dx[i] / view_r))
            res[i * 2 + 1] = max(-1.0, min(1.0, best_dy[i] / view_r))

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
def compute_bot_action_fast(
    cx: float,
    cy: float,
    cr: float,
    my_mass: float,
    num_subcells: int,
    split_cooldown: int,
    cells_xy: np.ndarray,
    cells_mass: np.ndarray,
    cells_pid: np.ndarray,
    my_pid: int,
    viruses_xy: np.ndarray,
    pellets_xy: np.ndarray,
    rng_val_split: float,
    rng_ang: float,
):
    """JIT-compiled tactical decision engine for opponent bots.

    Handles threat evasion, virus avoidance, tactical split attacks,
    prey pursuit, and pellet foraging in compiled C.
    """
    view_r = 500.0 + 2.0 * cr

    # 1. Threat & prey computation
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

    # 2. Virus avoidance (mass > 130)
    virus_avoid_x = 0.0
    virus_avoid_y = 0.0
    if my_mass > 130.0 and len(viruses_xy) > 0:
        thresh = cr + 50.0
        for v in range(len(viruses_xy)):
            v_dx = viruses_xy[v, 0] - cx
            if abs(v_dx) < thresh:
                v_dy = viruses_xy[v, 1] - cy
                if abs(v_dy) < thresh:
                    v_dist = math.hypot(v_dx, v_dy)
                    if 1e-4 < v_dist < thresh:
                        w = 1.0 / max(10.0, v_dist)
                        virus_avoid_x -= (v_dx / v_dist) * w
                        virus_avoid_y -= (v_dy / v_dist) * w

    threat_norm = math.hypot(threat_x, threat_y)
    virus_norm = math.hypot(virus_avoid_x, virus_avoid_y)

    # 1. Primary instinct: Flee from predators
    if threat_norm > 1e-4:
        return threat_x / threat_norm, threat_y / threat_norm, -1.0, split_cooldown

    # 2. Avoid popping on viruses
    if virus_norm > 1e-4:
        return virus_avoid_x / virus_norm, virus_avoid_y / virus_norm, -1.0, split_cooldown

    # 3. Disciplined tactical split
    can_split = (
        split_cooldown == 0
        and threat_norm < 1e-4
        and num_subcells <= 2
        and my_mass >= 60.0
        and 120.0 < closest_prey_dist < 240.0
        and my_mass >= 2.5 * closest_prey_mass
        and rng_val_split < 0.08
    )
    if can_split:
        return prey_dx, prey_dy, 0.8, 150

    # 4. Normal prey pursuit
    if closest_prey_dist < 320.0 and my_mass >= 1.2 * closest_prey_mass:
        return prey_dx, prey_dy, -1.0, split_cooldown

    # 5. Forage nearest pellet
    max_pellet_dist = min(view_r, 350.0)
    max_d_sq = max_pellet_dist * max_pellet_dist
    best_dist_sq = max_d_sq
    best_p_dx = 0.0
    best_p_dy = 0.0
    found_p = False

    num_pellets = len(pellets_xy)
    for p in range(num_pellets):
        pdx = pellets_xy[p, 0] - cx
        if abs(pdx) < max_pellet_dist:
            pdy = pellets_xy[p, 1] - cy
            if abs(pdy) < max_pellet_dist:
                d_sq = pdx * pdx + pdy * pdy
                if d_sq < best_dist_sq:
                    best_dist_sq = d_sq
                    best_p_dx = pdx
                    best_p_dy = pdy
                    found_p = True

    if found_p:
        dist = math.sqrt(max(1e-8, best_dist_sq))
        return best_p_dx / dist, best_p_dy / dist, -1.0, split_cooldown

    # 6. Random exploration
    return math.cos(rng_ang), math.sin(rng_ang), -1.0, split_cooldown


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
def find_single_nearest_pellet_candidates_numba(
    cx: float,
    cy: float,
    pellets_xy: np.ndarray,
    candidate_indices: np.ndarray,
    max_dist: float = 350.0,
):
    """Find one nearest pellet from spatial-grid candidates."""
    max_d_sq = max_dist * max_dist
    best_dist_sq = max_d_sq
    best_dx = 0.0
    best_dy = 0.0
    found = False

    for candidate in candidate_indices:
        p = int(candidate)
        dx = pellets_xy[p, 0] - cx
        dy = pellets_xy[p, 1] - cy
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


@nb.njit(fastmath=True)
def extract_entities_observation_numba(
    obs: np.ndarray,
    cx: float,
    cy: float,
    avg_vx: float,
    avg_vy: float,
    view_r: float,
    v_max: float,
    max_subcell_mass: float,
    min_subcell_mass: float,
    pid: int,
    cells_xy: np.ndarray,
    cells_mass: np.ndarray,
    cells_pid: np.ndarray,
    cells_vx: np.ndarray,
    cells_vy: np.ndarray,
    viruses_xy: np.ndarray,
    can_explode_on_virus: bool,
    width: float,
    height: float,
    cr: float,
    min_remerge: float,
):
    """JIT-compiled extraction of Prey, Predator, Virus, Wall, and Global observation vectors.

    Fills obs[24:84] in pure compiled C with zero heap allocations.
    """
    inv_view = 1.0 / max(1.0, view_r)
    inv_vmax = 1.0 / max(1.0, v_max)

    # 1. Prey & Predator top-5 tracking
    best_prey_dist = np.full(5, 1e9, dtype=np.float32)
    best_prey_dx = np.zeros(5, dtype=np.float32)
    best_prey_dy = np.zeros(5, dtype=np.float32)
    best_prey_lr = np.zeros(5, dtype=np.float32)
    best_prey_vrel = np.zeros(5, dtype=np.float32)
    best_prey_mass = np.zeros(5, dtype=np.float32)

    best_pred_dist = np.full(5, 1e9, dtype=np.float32)
    best_pred_dx = np.zeros(5, dtype=np.float32)
    best_pred_dy = np.zeros(5, dtype=np.float32)
    best_pred_lr = np.zeros(5, dtype=np.float32)
    best_pred_vrel = np.zeros(5, dtype=np.float32)

    closest_prey_dist = -1.0
    closest_prey_dx = 0.0
    closest_prey_dy = 0.0
    closest_prey_mass = 0.0

    n_cells = len(cells_xy)
    for c in range(n_cells):
        if cells_pid[c] == pid:
            continue
        dx = cells_xy[c, 0] - cx
        if abs(dx) > view_r:
            continue
        dy = cells_xy[c, 1] - cy
        if abs(dy) > view_r:
            continue
        dist = math.hypot(dx, dy)
        if dist > view_r:
            continue

        c_mass = cells_mass[c]
        v_rel = math.hypot(cells_vx[c] - avg_vx, cells_vy[c] - avg_vy)

        if c_mass * 1.1 <= max_subcell_mass:
            # Prey
            lr = math.log(max(1.0, c_mass) / max(1.0, max_subcell_mass))
            lr_norm = math.tanh(lr)
            if dist < best_prey_dist[4]:
                idx = 4
                while idx > 0 and dist < best_prey_dist[idx - 1]:
                    best_prey_dist[idx] = best_prey_dist[idx - 1]
                    best_prey_dx[idx] = best_prey_dx[idx - 1]
                    best_prey_dy[idx] = best_prey_dy[idx - 1]
                    best_prey_lr[idx] = best_prey_lr[idx - 1]
                    best_prey_vrel[idx] = best_prey_vrel[idx - 1]
                    best_prey_mass[idx] = best_prey_mass[idx - 1]
                    idx -= 1
                best_prey_dist[idx] = dist
                best_prey_dx[idx] = dx
                best_prey_dy[idx] = dy
                best_prey_lr[idx] = lr_norm
                best_prey_vrel[idx] = v_rel
                best_prey_mass[idx] = c_mass

        elif c_mass >= 1.1 * min_subcell_mass:
            # Predator
            lr = math.log(max(1.0, c_mass) / max(1.0, max_subcell_mass))
            lr_norm = math.tanh(lr)
            if dist < best_pred_dist[4]:
                idx = 4
                while idx > 0 and dist < best_pred_dist[idx - 1]:
                    best_pred_dist[idx] = best_pred_dist[idx - 1]
                    best_pred_dx[idx] = best_pred_dx[idx - 1]
                    best_pred_dy[idx] = best_pred_dy[idx - 1]
                    best_pred_lr[idx] = best_pred_lr[idx - 1]
                    best_pred_vrel[idx] = best_pred_vrel[idx - 1]
                    idx -= 1
                best_pred_dist[idx] = dist
                best_pred_dx[idx] = dx
                best_pred_dy[idx] = dy
                best_pred_lr[idx] = lr_norm
                best_pred_vrel[idx] = v_rel

    if best_prey_dist[0] < 1e8:
        closest_prey_dist = best_prey_dist[0]
        closest_prey_dx = best_prey_dx[0]
        closest_prey_dy = best_prey_dy[0]
        closest_prey_mass = best_prey_mass[0]

    # Write Preys (24 to 44)
    for i in range(5):
        base = 24 + i * 4
        if best_prey_dist[i] < 1e8:
            obs[base] = max(-1.0, min(1.0, best_prey_dx[i] * inv_view))
            obs[base + 1] = max(-1.0, min(1.0, best_prey_dy[i] * inv_view))
            obs[base + 2] = best_prey_lr[i]
            obs[base + 3] = max(-1.0, min(1.0, best_prey_vrel[i] * inv_vmax))
        else:
            obs[base] = 0.0
            obs[base + 1] = 0.0
            obs[base + 2] = 0.0
            obs[base + 3] = 0.0

    # Write Predators (44 to 64)
    for i in range(5):
        base = 44 + i * 4
        if best_pred_dist[i] < 1e8:
            obs[base] = max(-1.0, min(1.0, best_pred_dx[i] * inv_view))
            obs[base + 1] = max(-1.0, min(1.0, best_pred_dy[i] * inv_view))
            obs[base + 2] = best_pred_lr[i]
            obs[base + 3] = max(-1.0, min(1.0, best_pred_vrel[i] * inv_vmax))
        else:
            obs[base] = 0.0
            obs[base + 1] = 0.0
            obs[base + 2] = 0.0
            obs[base + 3] = 0.0

    # 2. Viruses (64 to 76)
    n_v = len(viruses_xy)
    best_v_dist = np.full(4, 1e9, dtype=np.float32)
    best_v_dx = np.zeros(4, dtype=np.float32)
    best_v_dy = np.zeros(4, dtype=np.float32)
    threat_sign = -1.0 if can_explode_on_virus else 1.0

    for v in range(n_v):
        v_dx = viruses_xy[v, 0] - cx
        v_dy = viruses_xy[v, 1] - cy
        dist = math.hypot(v_dx, v_dy)
        if dist < best_v_dist[3]:
            idx = 3
            while idx > 0 and dist < best_v_dist[idx - 1]:
                best_v_dist[idx] = best_v_dist[idx - 1]
                best_v_dx[idx] = best_v_dx[idx - 1]
                best_v_dy[idx] = best_v_dy[idx - 1]
                idx -= 1
            best_v_dist[idx] = dist
            best_v_dx[idx] = v_dx
            best_v_dy[idx] = v_dy

    for i in range(4):
        base = 64 + i * 3
        if best_v_dist[i] <= view_r:
            obs[base] = max(-1.0, min(1.0, best_v_dx[i] * inv_view))
            obs[base + 1] = max(-1.0, min(1.0, best_v_dy[i] * inv_view))
            obs[base + 2] = threat_sign
        else:
            obs[base] = 0.0
            obs[base + 1] = 0.0
            obs[base + 2] = 0.0

    # 3. Walls (76 to 80)
    obs[76] = max(0.0, min(1.0, (height - cy) * inv_view))
    obs[77] = max(0.0, min(1.0, cy * inv_view))
    obs[78] = max(0.0, min(1.0, cx * inv_view))
    obs[79] = max(0.0, min(1.0, (width - cx) * inv_view))

    # 4. Global pos & properties (80 to 84)
    obs[80] = max(-1.0, min(1.0, (cx / width) * 2.0 - 1.0))
    obs[81] = max(-1.0, min(1.0, (cy / height) * 2.0 - 1.0))
    obs[82] = max(0.0, min(1.0, cr * inv_view))
    obs[83] = max(0.0, min(1.0, min_remerge / 300.0))

    return closest_prey_dist, closest_prey_dx, closest_prey_dy, closest_prey_mass


@nb.njit(fastmath=True)
def compute_centroids_numba(
    n_cells: int,
    xy_buf: np.ndarray,
    m_buf: np.ndarray,
    pid_buf: np.ndarray,
    p_mass: np.ndarray,
    p_cent: np.ndarray,
    scale: float,
):
    """Compute player total masses and mass-weighted centroids in 1 microsecond."""
    p_mass.fill(0.0)
    p_cent.fill(0.0)
    for i in range(n_cells):
        pid = pid_buf[i]
        x = xy_buf[i, 0]
        y = xy_buf[i, 1]
        m = m_buf[i]
        if pid < len(p_mass):
            p_mass[pid] += m
            p_cent[pid, 0] += x * m
            p_cent[pid, 1] += y * m

    for p in range(len(p_mass)):
        tm = p_mass[p]
        if tm > 0.0:
            p_cent[p, 0] /= tm
            p_cent[p, 1] /= tm
            p_cent[p, 2] = scale * math.sqrt(tm)

