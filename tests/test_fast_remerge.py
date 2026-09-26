import math

import numpy as np

from src.env.physics_fast import resolve_same_player_cell_interactions_numba


def _python_reference(xy, mass, cooldown, offsets, width, height):
    merged = np.zeros(len(mass), dtype=np.bool_)
    for group in range(len(offsets) - 1):
        start, stop = offsets[group : group + 2]
        for i in range(start, stop):
            if merged[i]:
                continue
            for j in range(i + 1, stop):
                if merged[j]:
                    continue
                dx, dy = xy[j] - xy[i]
                dist_sq = dx * dx + dy * dy
                r_i = math.sqrt(max(mass[i], 1.0)) * 3.0
                r_j = math.sqrt(max(mass[j], 1.0)) * 3.0
                r_sum = r_i + r_j
                if cooldown[i] == 0 and cooldown[j] == 0:
                    large, small = (i, j) if mass[i] >= mass[j] else (j, i)
                    r_large = math.sqrt(max(mass[large], 1.0)) * 3.0
                    if dist_sq < r_large * r_large:
                        mass[large] += mass[small]
                        merged[small] = True
                        if small == i:
                            break
                        continue
                    if dist_sq < (r_sum * 1.5) ** 2:
                        dist = math.sqrt(max(1e-6, dist_sq))
                        nx, ny = dx * (1.0 / dist), dy * (1.0 / dist)
                        total = mass[i] + mass[j]
                        pull = min(3.0, max(0.4, (r_sum * 1.5 - dist) * 0.10))
                        pi, pj = pull * mass[j] / total, pull * mass[i] / total
                        xy[i, 0] = max(r_i, min(width - r_i, xy[i, 0] + nx * pi))
                        xy[i, 1] = max(r_i, min(height - r_i, xy[i, 1] + ny * pi))
                        xy[j, 0] = max(r_j, min(width - r_j, xy[j, 0] - nx * pj))
                        xy[j, 1] = max(r_j, min(height - r_j, xy[j, 1] - ny * pj))
                elif dist_sq < r_sum * r_sum:
                    dist = math.sqrt(max(1e-6, dist_sq))
                    nx, ny = dx * (1.0 / dist), dy * (1.0 / dist)
                    overlap = r_sum - dist
                    total = max(1e-4, mass[i] + mass[j])
                    ri, rj = mass[j] / total, mass[i] / total
                    xy[i, 0] = max(r_i, min(width - r_i, xy[i, 0] - nx * overlap * ri))
                    xy[i, 1] = max(r_i, min(height - r_i, xy[i, 1] - ny * overlap * ri))
                    xy[j, 0] = max(r_j, min(width - r_j, xy[j, 0] + nx * overlap * rj))
                    xy[j, 1] = max(r_j, min(height - r_j, xy[j, 1] + ny * overlap * rj))
    return merged


def test_numba_remerge_matches_previous_python_pair_order():
    rng = np.random.default_rng(24)
    xy_before = rng.uniform(100.0, 300.0, size=(32, 2)).astype(np.float64)
    mass_before = rng.uniform(20.0, 500.0, size=32).astype(np.float64)
    cooldown = rng.integers(0, 3, size=32, dtype=np.int64)
    offsets = np.array([0, 8, 16, 24, 32], dtype=np.int64)
    xy_ref, mass_ref = xy_before.copy(), mass_before.copy()
    xy_fast, mass_fast = xy_before.copy(), mass_before.copy()

    expected = _python_reference(xy_ref, mass_ref, cooldown, offsets, 1400.0, 1400.0)
    actual = resolve_same_player_cell_interactions_numba(
        xy_fast, mass_fast, cooldown, offsets, 1400.0, 1400.0
    )

    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_allclose(xy_fast, xy_ref, rtol=1e-13, atol=1e-13)
    np.testing.assert_allclose(mass_fast, mass_ref, rtol=1e-13, atol=1e-13)
