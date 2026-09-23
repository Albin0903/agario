"""Entities representation for the Agar.io simulation engine."""

from __future__ import annotations
from dataclasses import dataclass, field
import math


DEFAULT_MASS_DECAY_RATE: float = 0.00003  # ~0.18% mass loss per second (only over MIN_DECAY_MASS)
MIN_DECAY_MASS: float = 100.0  # Vanilla Agar.io: cells under 100 mass do not decay
SPLIT_IMPULSE_SPEED: float = 24.0
SPLIT_DRAG: float = 0.90


def mass_to_radius(mass: float, scale: float = 3.0) -> float:
    """Calculate cell radius from mass: r = sqrt(m) * scale."""
    m = mass if mass > 1.0 else 1.0
    return math.sqrt(m) * scale


def mass_to_speed(mass: float, v_base: float = 2.0, v_min: float = 0.5, exp: float = -0.2) -> float:
    """Calculate maximum cell speed based on mass: v = max(v_min, v_base * m^(-0.2))."""
    m = mass if mass > 1.0 else 1.0
    v = v_base * (m ** exp)
    return v if v > v_min else v_min


@dataclass(slots=True)
class Pellet:
    """Static food point with unit mass."""
    id: int
    x: float
    y: float
    mass: float = 1.0
    radius: float = 3.0


@dataclass(slots=True)
class Virus:
    """Hazard entity that explodes large cells."""
    id: int
    x: float
    y: float
    mass: float = 100.0
    radius: float = 30.0


@dataclass(slots=True)
class EjectedMass:
    """Ejected mass piece launched by a player."""
    id: int
    player_id: int
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    mass: float = 12.0
    radius: float = 10.3923  # sqrt(12) * 3
    ticks_remaining: int = 15


@dataclass(slots=True)
class Cell:
    """A single cell belonging to a player (a player can control up to 16 sub-cells)."""
    id: int
    player_id: int
    x: float
    y: float
    mass: float
    vx: float = 0.0
    vy: float = 0.0
    boost_vx: float = 0.0
    boost_vy: float = 0.0
    remerge_cooldown: int = 0  # Ticks until sub-cells of same player can merge back

    @property
    def radius(self) -> float:
        return mass_to_radius(self.mass)

    @property
    def speed(self) -> float:
        return mass_to_speed(self.mass)
