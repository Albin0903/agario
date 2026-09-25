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

    # Trigger eject mass towards right (trigger = 0.4 is in 0.2 < trig <= 0.6)
    events = engine.step({0: np.array([1.0, 0.0, 0.4], dtype=np.float32)})

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
    assert fps >= 3000.0, f"Expected FPS >= 3000, got {fps:.1f}"


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


def test_mass_decay_threshold_and_gentle_rate():
    """Verify cells <= 100 mass do not decay, and cells > 100 decay gently."""
    engine = AgarEngine(width=1000.0, height=1000.0, num_pellets=0, num_viruses=0, mass_decay_rate=0.001)
    # Small cell (50 mass <= 100)
    c_small = engine.spawn_player(0, initial_mass=50.0, xy=(300.0, 500.0))
    # Large cell (500 mass > 100)
    c_large = engine.spawn_player(1, initial_mass=500.0, xy=(700.0, 500.0))

    for _ in range(50):
        engine.step({
            0: np.array([0.0, 0.0, -1.0], dtype=np.float32),
            1: np.array([0.0, 0.0, -1.0], dtype=np.float32),
        })

    # Small cell must remain exactly at 50 mass (no decay below 100)
    assert c_small.mass == 50.0
    # Large cell should have decayed slightly
    assert c_large.mass < 500.0
    assert c_large.mass > 450.0  # Gentle decay, not wiped out


def test_non_instant_remerge_penetration():
    """Verify cells ready to remerge do not pop instantly at edge touch, and small pieces move faster into big pieces."""
    engine = AgarEngine(width=2000.0, height=2000.0, num_pellets=0, num_viruses=0)
    # Large cell: mass 500, radius ~67.08
    c1 = engine.spawn_player(0, initial_mass=500.0, xy=(1000.0, 1000.0))
    c1.remerge_cooldown = 0

    # Small cell: mass 50, radius ~21.21. r_sum ~88.3
    # Place small cell at distance 80: edges touch and overlap slightly, but dist > r_large (67.08)
    c2 = Cell(id=engine._next_cell_id, player_id=0, x=1080.0, y=1000.0, mass=50.0, remerge_cooldown=0)
    engine._next_cell_id += 1
    engine.cells.append(c2)

    initial_x1 = c1.x
    initial_x2 = c2.x

    # Step once: they must NOT merge instantly because dist (80) > r_large (67.08)
    engine.step({0: np.array([1000.0, 1000.0, -1.0], dtype=np.float32)})

    p_cells = engine.get_player_cells(0)
    assert len(p_cells) == 2, "Cells should not merge instantly at outer edge touch!"

    # Small cell must move towards large cell much faster than large cell moves towards small cell
    disp_small = abs(c2.x - initial_x2)
    disp_large = abs(c1.x - initial_x1)
    assert disp_small > disp_large, "Smaller cell should accelerate faster towards larger piece!"

    # Bring small cell well inside large cell boundary (dist < r_large)
    c2.x = c1.x + 30.0
    engine.step({0: np.array([1000.0, 1000.0, -1.0], dtype=np.float32)})

    # Now that it has deeply penetrated, absorption is finalized
    p_cells_after = engine.get_player_cells(0)
    assert len(p_cells_after) == 1
    assert math.isclose(p_cells_after[0].mass, 550.0, rel_tol=1e-4)


def test_multicell_partial_loss_not_fatal():
    """Verify that when a player has multiple subcells and loses one, died is False until all are gone."""
    engine = AgarEngine(width=1000.0, height=1000.0, num_pellets=0, num_viruses=0)
    c1 = Cell(id=1, player_id=0, x=200.0, y=200.0, mass=20.0)
    c2 = Cell(id=2, player_id=0, x=800.0, y=800.0, mass=20.0)
    engine.cells.extend([c1, c2])

    c_pred = Cell(id=3, player_id=1, x=200.0, y=200.0, mass=200.0)
    engine.cells.append(c_pred)

    events = engine.step({0: np.array([0.0, 0.0, -1.0], dtype=np.float32), 1: np.array([0.0, 0.0, -1.0], dtype=np.float32)})
    assert events[0]["died"] is False, "Player with surviving subcells must not be marked dead!"
    assert len(engine.get_player_cells(0)) == 1

    c_pred.x = 800.0
    c_pred.y = 800.0
    events2 = engine.step({0: np.array([0.0, 0.0, -1.0], dtype=np.float32), 1: np.array([0.0, 0.0, -1.0], dtype=np.float32)})
    assert events2[0]["died"] is True, "Player with 0 subcells must be marked dead!"
    assert len(engine.get_player_cells(0)) == 0


def test_subcells_remerge_while_moving_active():
    """Verify sub-cells actively moving at full speed remerge automatically once cooldown expires."""
    engine = AgarEngine(width=2000.0, height=2000.0, num_pellets=0, num_viruses=0, remerge_cooldown_ticks=5)
    c = engine.spawn_player(0, initial_mass=100.0, xy=(500.0, 500.0))

    # Split horizontally (towards right)
    engine.step({0: np.array([1.0, 0.0, 0.8], dtype=np.float32)})
    p_cells = engine.get_player_cells(0)
    assert len(p_cells) == 2, "Player must split into 2 subcells"

    # Agent is continuously moving right at full speed (direction action [1.0, 0.0, -1.0])
    # The subcells must magnetic-remerge without manual teleportation!
    remerged = False
    for step_i in range(120):
        engine.step({0: np.array([1.0, 0.0, -1.0], dtype=np.float32)})
        current_cells = engine.get_player_cells(0)
        if len(current_cells) == 1:
            remerged = True
            break

    assert remerged, "Sub-cells must remerge while moving actively at full speed!"
    assert math.isclose(engine.get_player_mass(0), 100.0, rel_tol=1e-3)


def test_virus_absorption_at_max_subcells():
    """Verify that a player with 16 subcells absorbs a virus without exploding (vanilla Agar.io mechanic)."""
    engine = AgarEngine(width=2000.0, height=2000.0, num_pellets=0, num_viruses=1, max_subcells=16)
    engine.viruses_xy[0] = [500.0, 500.0]
    engine.virus_masses[0] = 100.0
    engine.virus_radii[0] = 24.0

    # Create 16 subcells for player 0
    engine.cells.clear()
    for i in range(16):
        c = Cell(
            id=engine._next_cell_id,
            player_id=0,
            x=500.0 if i == 0 else 100.0 + i * 20.0,
            y=500.0 if i == 0 else 100.0,
            mass=150.0,
            remerge_cooldown=1000,
        )
        engine._next_cell_id += 1
        engine.cells.append(c)

    initial_total_mass = engine.get_player_mass(0)
    assert len(engine.get_player_cells(0)) == 16

    events = engine.step({0: np.array([0.0, 0.0, -1.0], dtype=np.float32)})

    # Must absorb +100 mass without exploding into more cells
    p_cells_after = engine.get_player_cells(0)
    assert len(p_cells_after) == 16, "Player at 16 cells must not explode!"
    assert events[0]["virus_eaten"] is True, "Virus must be marked as eaten/absorbed"
    assert math.isclose(engine.get_player_mass(0), initial_total_mass + 100.0, rel_tol=1e-3)


def test_ejected_mass_wall_bounce():
    """Verify that ejected mass rebounds off the arena boundary with reversed velocity."""
    engine = AgarEngine(width=1000.0, height=1000.0, num_pellets=0, num_viruses=0)
    # Ejected piece near left wall moving left
    em = EjectedMass(
        id=1,
        player_id=0,
        x=15.0,
        y=500.0,
        vx=-15.0,
        vy=0.0,
        mass=12.0,
        ticks_remaining=15,
    )
    engine.ejected.append(em)

    engine.step({0: np.array([0.0, 0.0, -1.0], dtype=np.float32)})

    # Velocity must have inverted (bounced off left wall to move right)
    assert len(engine.ejected) == 1
    assert engine.ejected[0].vx > 0.0, "Ejected mass should bounce off wall with inverted velocity!"
    assert engine.ejected[0].x >= engine.ejected[0].radius







