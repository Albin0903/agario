import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import time
import math
import numpy as np
import pytest
from src.env.agar_engine import AgarEngine
from src.env.entities import mass_to_radius, mass_to_speed, Cell, EjectedMass


def test_mass_radius_formula():
    """Verify r = sqrt(m) * 3."""
    for m in [1.0, 4.0, 9.0, 16.0, 100.0, 400.0]:
        expected = math.sqrt(m) * 3.0
        assert math.isclose(mass_to_radius(m), expected, rel_tol=1e-5)


def test_mass_speed_formula():
    """Verify v = max(0.5, 2.0 * m^(-0.2))."""
    # Mass 1: 2.0 * 1 = 2.0
    assert math.isclose(mass_to_speed(1.0), 2.0, rel_tol=1e-5)
    # Mass 32: 2.0 * 32^(-0.2) = 2.0 * 0.5 = 1.0
    assert math.isclose(mass_to_speed(32.0), 1.0, rel_tol=1e-3)
    # Very high mass should clamp to 0.5
    assert mass_to_speed(100000.0) == 0.5


def test_pellet_consumption_and_mass_conservation():
    """Verify mass conservation upon eating pellets."""
    engine = AgarEngine(width=1000.0, height=1000.0, num_pellets=100, pellet_mass=1.0)
    player = engine.spawn_player(0, initial_mass=20.0, xy=(500.0, 500.0))

    # Place 5 pellets directly inside the player's radius
    for i in range(5):
        engine.pellets_xy[i] = [500.0 + i, 500.0 + i]
    engine.spatial_grid.build(engine.pellets_xy)

    # Step with idle action
    engine.step({0: np.array([0.0, 0.0, -1.0], dtype=np.float32)})

    # Player mass should have increased by at least 5
    assert engine.get_player_mass(0) >= 25.0


def test_cell_predation_mass_conservation():
    """Verify predator absorbs prey and total mass transfers accurately."""
    engine = AgarEngine(width=1000.0, height=1000.0, num_pellets=0)
    # Predator (mass 100) and Prey (mass 50) overlapping
    predator = engine.spawn_player(0, initial_mass=100.0, xy=(500.0, 500.0))
    prey = engine.spawn_player(1, initial_mass=50.0, xy=(505.0, 500.0))

    # Check that predator eats prey (100 >= 1.1 * 50 = 55)
    events = engine.step({
        0: np.array([0.0, 0.0, -1.0], dtype=np.float32),
        1: np.array([0.0, 0.0, -1.0], dtype=np.float32),
    })

    assert events[0]["cells_eaten"] == 1
    assert events[1]["died"] is True
    # Mass conservation: 100 + 50 = 150
    assert math.isclose(engine.get_player_mass(0), 150.0, rel_tol=1e-5)
    assert len(engine.get_player_cells(1)) == 0


def test_predation_requires_eat_ratio():
    """Verify cells do not eat each other if mass ratio < 1.1."""
    engine = AgarEngine(width=1000.0, height=1000.0, num_pellets=0)
    # Cell A mass 100, Cell B mass 95 (100 < 1.1 * 95 = 104.5)
    cA = engine.spawn_player(0, initial_mass=100.0, xy=(500.0, 500.0))
    cB = engine.spawn_player(1, initial_mass=95.0, xy=(505.0, 500.0))

    events = engine.step({
        0: np.array([0.0, 0.0, -1.0], dtype=np.float32),
        1: np.array([0.0, 0.0, -1.0], dtype=np.float32),
    })

    assert events[0]["cells_eaten"] == 0
    assert events[1]["died"] is False
    assert len(engine.cells) == 2


def test_virus_explosion():
    """Verify cells with mass > 130 explode into fragments when colliding with a virus."""
    engine = AgarEngine(width=1000.0, height=1000.0, num_pellets=0, num_viruses=1)
    engine.viruses_xy[0] = [500.0, 500.0]

    # Spawn cell with mass 200 directly covering the virus
    cell = engine.spawn_player(0, initial_mass=200.0, xy=(500.0, 500.0))
    assert len(engine.get_player_cells(0)) == 1

    engine.step({0: np.array([0.0, 0.0, -1.0], dtype=np.float32)})

    p_cells = engine.get_player_cells(0)
    assert len(p_cells) > 1
    assert len(p_cells) <= 16
    # Total mass must be conserved (200.0)
    total_mass = sum(c.mass for c in p_cells)
    assert math.isclose(total_mass, 200.0, rel_tol=1e-4)


def test_split_action():
    """Verify split divides cell into two equal halves with impulse."""
    engine = AgarEngine(width=1000.0, height=1000.0, num_pellets=0)
    cell = engine.spawn_player(0, initial_mass=100.0, xy=(500.0, 500.0))

    # Trigger split towards right (tx=1.0, ty=0.0, trigger=0.8)
    events = engine.step({0: np.array([1.0, 0.0, 0.8], dtype=np.float32)})

    assert events[0]["splits"] == 1
    p_cells = engine.get_player_cells(0)
    assert len(p_cells) == 2
    assert math.isclose(p_cells[0].mass, 50.0, rel_tol=1e-5)
    assert math.isclose(p_cells[1].mass, 50.0, rel_tol=1e-5)
    assert p_cells[0].remerge_cooldown > 0
    assert p_cells[1].remerge_cooldown > 0


def test_eject_mass_action():
    """Verify mass ejection deducts 16 mass and spawns 12 mass pellet."""
    engine = AgarEngine(width=1000.0, height=1000.0, num_pellets=0)
    cell = engine.spawn_player(0, initial_mass=100.0, xy=(500.0, 500.0))

    # Trigger eject mass towards right (trigger = 0.0 is in [-0.33, 0.33])
    events = engine.step({0: np.array([1.0, 0.0, 0.0], dtype=np.float32)})

    assert events[0]["ejects"] == 1
    assert math.isclose(cell.mass, 84.0, rel_tol=1e-5)
    assert len(engine.ejected) == 1
    assert math.isclose(engine.ejected[0].mass, 12.0, rel_tol=1e-5)


def test_subcells_remerge():
    """Verify sub-cells remerge after cooldown expires."""
    engine = AgarEngine(width=1000.0, height=1000.0, num_pellets=0, remerge_cooldown_ticks=2)
    engine.spawn_player(0, initial_mass=100.0, xy=(500.0, 500.0))

    # Split
    engine.step({0: np.array([1.0, 0.0, 0.8], dtype=np.float32)})
    assert len(engine.get_player_cells(0)) == 2

    # Step until cooldown expires
    for _ in range(5):
        # Force subcells to stay close
        p_cells = engine.get_player_cells(0)
        if len(p_cells) == 2:
            p_cells[1].x = p_cells[0].x + 2.0
            p_cells[1].y = p_cells[0].y
        engine.step({0: np.array([0.0, 0.0, -1.0], dtype=np.float32)})

    # After cooldown expires, they should merge back into 1 cell of mass 100
    p_cells = engine.get_player_cells(0)
    assert len(p_cells) == 1
    assert math.isclose(p_cells[0].mass, 100.0, rel_tol=1e-4)


def test_simulation_speed_benchmark():
    """Verify headless simulation achieves > 5000 FPS."""
    engine = AgarEngine(width=2000.0, height=2000.0, num_pellets=500, num_viruses=10)
    for i in range(11):
        engine.spawn_player(i, initial_mass=20.0)

    actions = {i: np.array([1.0, 0.0, -1.0], dtype=np.float32) for i in range(11)}

    # Warmup
    for _ in range(100):
        engine.step(actions)

    steps = 5000
    t0 = time.perf_counter()
    for _ in range(steps):
        engine.step(actions)
    t1 = time.perf_counter()

    fps = steps / (t1 - t0)
    print(f"\n[FPS Benchmark] Raw engine achieved: {fps:.1f} FPS")
    assert fps >= 5000.0, f"Expected FPS >= 5000, got {fps:.1f}"


def test_virus_feeding_and_shoot():
    """Verify feeding a virus with ejected mass causes it to grow and shoot a new virus at 140 mass."""
    engine = AgarEngine(width=1000.0, height=1000.0, num_pellets=0, num_viruses=1)
    engine.viruses_xy[0] = [500.0, 500.0]
    initial_virus_count = len(engine.viruses_xy)

    # Spawn 4 ejected mass pieces right on the virus to feed it (each is 12 mass: 100 + 4*12 = 148 >= 140)
    for i in range(4):
        em = EjectedMass(
            id=i + 1,
            player_id=0,
            x=500.0,
            y=500.0,
            vx=10.0,
            vy=0.0,
            mass=12.0,
            radius=10.0,
            ticks_remaining=10,
        )
        engine.ejected.append(em)

    engine.step({})

    # Virus should have shot a new virus!
    assert len(engine.viruses_xy) == initial_virus_count + 1
    # Original virus mass should be reset to 100
    assert engine.virus_masses[0] == 100.0


def test_subcells_idle_centroid_attraction():
    """Verify separated sub-cells drift towards their center of mass when idle."""
    engine = AgarEngine(width=1000.0, height=1000.0, num_pellets=0, num_viruses=0)
    c1 = engine.spawn_player(0, initial_mass=50.0, xy=(450.0, 500.0))
    c2 = Cell(id=engine._next_cell_id, player_id=0, x=550.0, y=500.0, mass=50.0, remerge_cooldown=300)
    engine._next_cell_id += 1
    engine.cells.append(c2)

    initial_dist = abs(c2.x - c1.x)
    # Step with idle action
    engine.step({0: np.array([0.0, 0.0, -1.0], dtype=np.float32)})

    new_dist = abs(c2.x - c1.x)
    # Distance between subcells should have decreased due to centroid attraction
    assert new_dist < initial_dist


def test_virus_halo_spawning():
    """Verify pellets near viruses are displaced into outer halos."""
    engine = AgarEngine(width=2000.0, height=2000.0, num_pellets=1200, num_viruses=10)
    for vx, vy in engine.viruses_xy:
        dx = engine.pellets_xy[:, 0] - vx
        dy = engine.pellets_xy[:, 1] - vy
        dists = np.hypot(dx, dy)
        # No pellets should be buried under the virus core (< 25 radius)
        assert np.all(dists >= 25.0)


def test_subcells_mouse_target_convergence():
    """Verify sub-cells independently steer inward toward a centered mouse coordinate."""
    engine = AgarEngine(width=1000.0, height=1000.0, num_pellets=0, num_viruses=0)
    c1 = engine.spawn_player(0, initial_mass=50.0, xy=(400.0, 500.0))
    c2 = Cell(id=engine._next_cell_id, player_id=0, x=600.0, y=500.0, mass=50.0, remerge_cooldown=300)
    engine._next_cell_id += 1
    engine.cells.append(c2)

    # Place mouse target coordinate directly in the center between them (500.0, 500.0)
    engine.step({0: np.array([500.0, 500.0, -1.0], dtype=np.float32)})

    # Left cell must move right (vx > 0), right cell must move left (vx < 0)
    assert c1.vx > 0.0, f"Expected c1.vx > 0, got {c1.vx}"
    assert c2.vx < 0.0, f"Expected c2.vx < 0, got {c2.vx}"
    # Distance between subcells must decrease
    dist = abs(c2.x - c1.x)
    assert dist < 200.0, f"Expected distance < 200.0, got {dist}"


def test_mass_dependent_remerge_cooldown():
    """Verify subcell remerge cooldown scales dynamically with subcell mass."""
    engine = AgarEngine(
        width=2000.0,
        height=2000.0,
        num_pellets=0,
        num_viruses=0,
        remerge_cooldown_ticks=600,
        remerge_cooldown_mass_factor=0.5,
    )
    # Player 0: Small cell (mass 50)
    engine.spawn_player(0, initial_mass=50.0, xy=(500.0, 500.0))
    # Player 1: Large cell (mass 1000)
    engine.spawn_player(1, initial_mass=1000.0, xy=(1500.0, 1500.0))

    # Split both players
    engine.step({
        0: np.array([1.0, 0.0, 0.8], dtype=np.float32),
        1: np.array([1.0, 0.0, 0.8], dtype=np.float32),
    })

    p0_cells = engine.get_player_cells(0)
    p1_cells = engine.get_player_cells(1)
    assert len(p0_cells) == 2
    assert len(p1_cells) == 2

    # Small cell half mass is 25: cooldown = 600 + int(25 * 0.5) - 1 step tick = 611
    assert p0_cells[0].remerge_cooldown == 611
    # Large cell half mass is 500: cooldown = 600 + int(500 * 0.5) - 1 step tick = 849
    assert p1_cells[0].remerge_cooldown == 849
    assert p1_cells[0].remerge_cooldown > p0_cells[0].remerge_cooldown




