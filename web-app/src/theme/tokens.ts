// Semantic Design Tokens matching Tailwind v4 @theme configuration
// Provides strongly typed access to design values for programmatic logic and animations.

export const typography = {
  fontSans: '"Inter", ui-sans-serif, system-ui, sans-serif',
  fontDisplay: '"Inter", ui-sans-serif, system-ui, sans-serif',
  fontMono: 'ui-monospace, "Cascadia Code", "Fira Code", monospace',
} as const;

export const durations = {
  fast: 150,
  normal: 250,
  slow: 400,
} as const;

export const easings = {
  snappy: [0.22, 1, 0.36, 1],
  smooth: [0.16, 1, 0.3, 1],
  gentle: [0.33, 1, 0.68, 1],
  bouncy: [0.34, 1.56, 0.64, 1],
} as const;

export const semanticColors = {
  surface: {
    canvas: "var(--color-surface-canvas)",
    card: "var(--color-surface-card)",
    muted: "var(--color-surface-muted)",
    subtle: "var(--color-surface-subtle)",
  },
  border: {
    subtle: "var(--color-border-subtle)",
    default: "var(--color-border-default)",
    strong: "var(--color-border-strong)",
  },
  text: {
    primary: "var(--color-text-primary)",
    secondary: "var(--color-text-secondary)",
    muted: "var(--color-text-muted)",
  },
  state: {
    success: "var(--color-success)",
    warning: "var(--color-warning)",
    danger: "var(--color-danger)",
  },
  brand: {
    primary: "var(--color-brand-primary)",
    hover: "var(--color-brand-hover)",
    surface: "var(--color-brand-surface)",
    border: "var(--color-brand-border)",
    text: "var(--color-brand-text)",
  },
} as const;

