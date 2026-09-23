// Calibrated spring physics presets for UI micro-interactions.
// Based on Swiss Design Engineering invariants:
// stiffness (tension), damping (friction), mass (inertia).

export interface SpringConfig {
  stiffness: number;
  damping: number;
  mass: number;
}

export const springs = {
  // Snappy: immediate tactile feedback for buttons, toggles, badges
  snappy: {
    stiffness: 400,
    damping: 30,
    mass: 1,
  },
  // Smooth: fluid transitions for modals, sidebars, expanded cards
  smooth: {
    stiffness: 200,
    damping: 25,
    mass: 1.2,
  },
  // Gentle: subtle page transitions and ambient fades
  gentle: {
    stiffness: 120,
    damping: 20,
    mass: 1.5,
  },
  // Bouncy: playful state confirmations and notifications
  bouncy: {
    stiffness: 350,
    damping: 15,
    mass: 0.8,
  },
} as const;
