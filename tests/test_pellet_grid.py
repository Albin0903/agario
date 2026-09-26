import numpy as np

from src.env.physics_fast import (
    check_pellet_collisions_fast,
    check_pellet_collisions_grid_numba,
)


def test_spatial_grid_pellet_collisions_match_quadratic_reference():
    rng = np.random.default_rng(884)
    width, height, cell_size = 900.0, 700.0, 80.0
    pellets = rng.uniform([0.0, 0.0], [width, height], size=(2500, 2)).astype(np.float32)
    cells = rng.uniform([0.0, 0.0], [width, height], size=(48, 2)).astype(np.float32)
    # Include realistic small and very large cells, including boundary overlaps.
    masses = rng.uniform(20.0, 2200.0, size=len(cells))
    radii = (np.sqrt(masses) * 3.0).astype(np.float32)
    cells[0] = [0.0, 0.0]
    cells[1] = [width, height]
    radii[:2] = [120.0, 150.0]

    expected_ids, expected_counts = check_pellet_collisions_fast(pellets, cells, radii)
    actual_ids, actual_counts = check_pellet_collisions_grid_numba(
        pellets, cells, radii, width, height, cell_size
    )

    np.testing.assert_array_equal(actual_ids, expected_ids)
    np.testing.assert_array_equal(actual_counts, expected_counts)


def test_spatial_grid_collision_prefers_first_overlapping_cell():
    pellets = np.asarray([[50.0, 50.0], [99.0, 50.0], [150.0, 50.0]], dtype=np.float32)
    cells = np.asarray([[50.0, 50.0], [52.0, 50.0]], dtype=np.float32)
    radii = np.asarray([60.0, 60.0], dtype=np.float32)
    expected = check_pellet_collisions_fast(pellets, cells, radii)
    actual = check_pellet_collisions_grid_numba(pellets, cells, radii, 200.0, 100.0, 50.0)
    np.testing.assert_array_equal(actual[0], expected[0])
    np.testing.assert_array_equal(actual[1], expected[1])
    assert actual[1].tolist() == [2, 0]
