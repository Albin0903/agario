# Project: build Template Foundation (v2.0.0)

## Architecture

The `build` project implements a production-grade tri-technology foundation (Go / TypeScript / Python) engineered for autonomous agentic generation from a single prompt.

```
┌───────────────────────────────────────────────────────────────────────────┐
│                      Client Layer (Browser / MCP)                         │
│  ┌───────────────────────────────┐     ┌───────────────────────────────┐  │
│  │   Vite TypeScript React SPA   │     │      Templ SSR + HTMX         │  │
│  │   (Tailwind v4, Motion,       │     │   (Server-rendered views,     │  │
│  │    TanStack Router, Skeletons,│     │    CSS Bezier springs,        │  │
│  │    Component Primitives)      │     │    Satin Light Theme)         │  │
│  └───────────────┬───────────────┘     └───────────────┬───────────────┘  │
└──────────────────┼─────────────────────────────────────┼──────────────────┘
                   │ HTTP JSON (Typed Client)            │ HTTP HTML (HTMX)
                   ▼                                     ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                      Backend Adapters Layer (Go)                          │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ internal/adapters/httpserver:                                       │  │
│  │ Router, Middleware (CORS, Logging), Handlers (JSON API & HTMX views)│  │
│  └──────────────────┬──────────────────────────────────┬───────────────┘  │
│                     │                                  │                  │
│  ┌──────────────────┴──────────────────┐               │ JSON IPC / CLI   │
│  │ internal/adapters/storage/memory:   │               ▼                  │
│  │ Thread-safe in-memory repository    │  ┌────────────────────────────┐  │
│  │ (sync.RWMutex) implementing ports   │  │ services/worker-python:    │  │
│  └──────────────────┬──────────────────┘  │ Design & Data Pipeline     │  │
└─────────────────────┼─────────────────────│ (uv, ruff, mypy, pytest)   │  │
                      │ Implements Ports    └────────────────────────────┘  │
                      ▼                                                     │
┌───────────────────────────────────────────────────────────────────────────┐
│                         Ports Layer (Contracts)                           │
│  internal/ports:                                                          │
│  - Repository: Context-aware CRUD & health check interfaces               │
│  - Service interfaces consumed by adapters                                │
└─────────────────────────────────────▲─────────────────────────────────────┘
                                      │ Consumed by Core
                                      │
┌───────────────────────────────────────────────────────────────────────────┐
│                         Core Layer (Pure Domain)                          │
│  internal/core/domain: Canonical entities, value objects, domain errors   │
│  internal/core/services: Pure business logic, state machines, invariants  │
│  (Strictly decoupled: zero imports of internal/adapters)                  │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Foundation Invariants & Feature Inventory

Every core architectural requirement is verified across automated test suites:

| # | Feature ID | Feature Name | Description | Status |
| --- | ------------ | -------------- | ------------- | -------- |
| 1 | REQ-R1-01 | 1-Prompt Elicitation Protocol | Deterministic 5-step elicitation engine (Audience, Intent, Scene, Typography, Non-blocking Completion) | VERIFIED (v2.0.0) |
| 2 | REQ-R1-02 | Product Skeleton (Wireframing First) | 3-tier layout: Contextual Header, The Stage (`min-h-[calc(100vh-...)]`), Functional Peripherals | VERIFIED (v2.0.0) |
| 3 | REQ-R1-03 | 3-Second Primary Action Salience | Exactly 1 prominent CTA with levels 9–10 palette; zero onboarding walkthrough popups | VERIFIED (v2.0.0) |
| 4 | REQ-R1-04 | Major Second Modular Typography | Proportional scale: base 16px, ratio 1.125, steps -2 to +5, line-height multiple of 4px | VERIFIED (v2.0.0) |
| 5 | REQ-R1-05 | APCA Contrast Compliance | Lightness contrast $L_c \ge 75$ body, $L_c \ge 60$ labels, $L_c \ge 45$ headings | VERIFIED (v2.0.0) |
| 6 | REQ-R1-06 | Non-Blocking State Completion | Terminal state leaves central artifact 100% visible and interactive with peripheral feedback | VERIFIED (v2.0.0) |
| 7 | REQ-R2-01 | Zero-Shift Skeletons (CLS = 0) | Skeletons mirror exact geometric footprint (`w-*`, `h-*`, `gap-*`) of final content | VERIFIED (v2.0.0) |
| 8 | REQ-R2-02 | Calibrated Spring Physics Presets | Presets: snappy ($k=400, c=30$), smooth ($k=200, c=25$), gentle, bouncy | VERIFIED (v2.0.0) |
| 9 | REQ-R2-03 | CSS Bezier Spring Approximation | Calibrated cubic-bezier curves for SSR Templ animations | VERIFIED (v2.0.0) |
| 10 | REQ-R2-04 | Contextual Indicator-as-Switch | All status indicators act as their own switches upon click (Rule 12 AGENTS.md) | VERIFIED (v2.0.0) |
| 11 | REQ-R2-05 | Mechanical Z-Index Sandwich | Layered depth: `z-0` cavity to `z-50` release latch with gravity kinematics | VERIFIED (v2.0.0) |
| 12 | REQ-R2-06 | 300ms Skeleton Debounce Rule | Suppress skeleton flash for instant responses; trigger only after 300ms network delay | VERIFIED (v2.0.0) |
| 13 | REQ-R2-07 | Embedded UI Component Primitives | Native accessible components: Badge, Button, Card, DataTable, Dialog, EmptyState, Input, Toast | VERIFIED (v2.0.0) |
| 14 | REQ-R2-08 | 5-Variable Semantic Theming | Immediate brand adaptation via 5 CSS custom properties in Tailwind v4 `@theme` | VERIFIED (v2.0.0) |
| 15 | REQ-R3-01 | Authentic Domain Modeling | Eliminate dummy text (lorem ipsum, foo, bar) in favor of realistic business entities | VERIFIED (v2.0.0) |
| 16 | REQ-R3-02 | Radix 12-Level Palette Mapping | Semantic color mapping: 1-2 canvas, 3-5 surface, 6-8 border, 9-10 solid, 11-12 text | VERIFIED (v2.0.0) |
| 17 | REQ-R3-03 | Satin Light Theme Default | Mandatory default light canvas (`bg-slate-50` to `bg-white`) with soft solar shadows | VERIFIED (v2.0.0) |
| 18 | REQ-R3-04 | Zero Technical Vanity Metrics | Prohibit tech stack names (`Go`, `HTMX`, `Vite`) and non-actionable metrics in UI | VERIFIED (v2.0.0) |
| 19 | REQ-R3-05 | Typed Data Fetching & API Client | Hermetic `apiFetch<T>` and `useQuery<T>` hook with automatic AbortController lifecycle | VERIFIED (v2.0.0) |
| 20 | REQ-R3-06 | Python Seed & Asset Generation | Authentic domain seeding (e-commerce, SaaS, CRM), SVG favicon creation, and token contrast audits | VERIFIED (v2.0.0) |
| 21 | REQ-R4-01 | Pure Core Domain Isolation | `core` business logic decoupled from adapters; core never imports adapters | VERIFIED (v2.0.0) |
| 22 | REQ-R4-02 | Consumer-Owned Port Interfaces | Context-aware interfaces declared in consuming package (`internal/ports`) | VERIFIED (v2.0.0) |
| 23 | REQ-R4-03 | Constructor Dependency Injection | Services, handlers, and repos instantiated via `New<Struct>(...)` constructors | VERIFIED (v2.0.0) |
| 24 | REQ-R4-04 | Mandatory Context Propagation | All I/O and storage methods take `ctx context.Context` as first parameter | VERIFIED (v2.0.0) |
| 25 | REQ-R4-05 | Causal Error Wrapping & No Panic | All errors wrapped with context; zero panics outside `main.go`; unified HTTP error mapping | VERIFIED (v2.0.0) |
| 26 | REQ-R4-06 | Table-Driven Unit Tests | Standardized `map[string]struct{ ... }` test layout with `t.Parallel()` isolation | VERIFIED (v2.0.0) |
| 27 | REQ-R4-07 | Thread-Safe Memory Persistence | In-memory repository with `sync.RWMutex` providing zero-dependency persistence | VERIFIED (v2.0.0) |
| 28 | REQ-R5-01 | Taskfile Deterministic Gate | `NO_COLOR=1 task check` executes `generate -> lint -> test:unit -> build:front -> build:bin` | VERIFIED (v2.0.0) |
| 29 | REQ-R5-02 | Design Token Compliance Lint | `task lint:design` audits arbitrary Tailwind values and gates in `task check` | VERIFIED (v2.0.0) |
| 30 | REQ-R5-03 | Mandatory Multi-Resolution MCP Review | Dual-resolution Chrome DevTools audit (1200x900 desktop & 390x844 mobile, 0 console errors) | VERIFIED (v2.0.0) |
| 31 | REQ-R5-04 | Scratch Runtime Packaging | Multi-stage Dockerfile producing static binary in minimal `scratch` image with SSL certs | VERIFIED (v2.0.0) |
| 32 | REQ-R5-05 | Conventional Commits & CI Gate | Strict Conventional Commits v1.0.0 and CI Gate pattern protection | VERIFIED (v2.0.0) |
| 33 | REQ-R5-06 | Procedural Audio & Kinematic Invariants | 60 FPS sub-cellular Canvas/DOM loop, FIFO input buffer, and Procedural Web Audio | VERIFIED (v2.0.0) |

---

## Interface Contracts

### Domain Core ↔ Repository Port (`internal/core` ↔ `internal/ports`)

- `ports.Repository`:
  - `Ping(ctx context.Context) error`
  - `Save(ctx context.Context, item domain.Item) error`
  - `GetByID(ctx context.Context, id string) (domain.Item, error)`
  - `List(ctx context.Context) ([]domain.Item, error)`
  - `Update(ctx context.Context, item domain.Item) error`
  - `Delete(ctx context.Context, id string) error`
- Error Contracts:
  - `domain.ErrNotFound`: item does not exist.
  - `domain.ErrConflict`: item already exists.
  - `domain.ErrValidation`: invariant violation.

### Frontend Client ↔ Backend API (`web-app/src/lib/api.ts`)

- `apiFetch<T>(path: string, options?: RequestInit): Promise<T>`
- Standardized methods: `api.get<T>`, `api.post<T>`, `api.put<T>`, `api.patch<T>`, `api.delete<T>`
- Structured error handling: `ApiClientError` with HTTP status and JSON payload parsing.

### Python Task Pipeline Interface (`services/worker-python`)

- Request: `{ "action": string, "payload": object }`
- Available Actions:
  - `design.contrast`: WCAG 2.1 & APCA contrast calculation
  - `design.palette`: 12-step Radix color scale generation
  - `design.favicon`: SVG favicon generation with custom glyph
  - `design.audit`: Multi-token contrast compliance audit
  - `data.summarize`: Statistical summary (mean, median, stdev, IQR)
  - `data.normalize`: Min-max feature scaling
  - `seed.items`: Authentic domain item generation (e-commerce, SaaS, CRM)
  - `seed.users`: Realistic user profile generation
- Response:
  - `{ "success": true, "data": object, "execution_ms": number }`
  - `{ "success": false, "error": string, "execution_ms": number }`

---

## Code Layout

```
build/
├── .agents/skills/                        # 15 Agent skills declarations
├── .devcontainer/                         # Devcontainer configuration
├── .github/                               # GitHub workflows, rulesets, templates
├── .vscode/                               # Workspace editor & MCP configuration
├── build/
│   └── Dockerfile                         # Scratch multi-stage Docker build
├── cmd/
│   └── server/
│       └── main.go                        # Entry point, dependency wiring
├── docs/wiki/                             # In-repo documentation (architecture, git, CI, testing, UI, components)
│   ├── 01-architecture-overview.md
│   ├── 02-branching-and-git-rulesets.md
│   ├── 03-ci-cd-and-automation.md
│   ├── 04-testing-playbook.md
│   ├── 05-project-boards-and-issue-lifecycle.md
│   ├── 06-ui-research-and-adaptive-design.md
│   └── 07-component-library.md
├── internal/
│   ├── adapters/
│   │   ├── http/views/                    # Templ components & styles
│   │   │   ├── health.templ
│   │   │   ├── home.templ
│   │   │   ├── icons.templ
│   │   │   ├── layout.templ
│   │   │   └── styles.go
│   │   ├── httpserver/                    # HTTP handlers, router, error mapping
│   │   │   ├── errors.go
│   │   │   ├── handlers.go
│   │   │   ├── handlers_test.go
│   │   │   ├── middleware.go
│   │   │   └── router.go
│   │   └── storage/memory/                # In-memory thread-safe persistence
│   │       ├── memory.go
│   │       ├── memory_test.go
│   │       └── stress_test.go
│   ├── core/
│   │   ├── domain/                        # Pure domain entities & errors
│   │   │   ├── errors.go
│   │   │   ├── item.go
│   │   │   └── item_test.go
│   │   ├── health/                        # Health service
│   │   │   ├── service.go
│   │   │   └── service_test.go
│   │   └── items/                         # Business aggregate service
│   │       ├── service.go
│   │       └── service_test.go
│   └── ports/
│       └── repository.go                  # Context-aware repository interface
├── scripts/
│   ├── init.go                            # Automated module renaming script
│   └── lint-design.ps1                    # Design token compliance scanner
├── services/worker-python/                # Generic Python design & data pipeline
│   ├── pyproject.toml                     # uv, ruff, mypy, pytest configuration
│   ├── worker_python/
│   │   ├── cli.py                         # JSON IPC CLI interface
│   │   ├── models.py                      # Pydantic data contracts
│   │   ├── pipeline.py                    # Extensible TaskPipeline
│   │   └── handlers/                      # Handlers: design, data, seed
│   └── tests/                             # Pytest test suites (23 tests)
├── tests/
│   ├── e2e/                               # 4-Tier E2E test harness
│   │   ├── runner.ps1                     # Test runner
│   │   ├── tier1_features/
│   │   ├── tier2_boundaries/
│   │   ├── tier3_combinations/
│   │   └── tier4_scenarios/
│   └── integration/                       # Go integration & stress tests
├── web-app/                               # Frontend rich SPA (React 19, Vite, Tailwind v4)
│   ├── src/
│   │   ├── components/                    # UI Primitives: Badge, Button, Card, DataTable, Dialog, etc.
│   │   ├── hooks/                         # useQuery (300ms debounce)
│   │   ├── lib/                           # api.ts, audio.ts, springs.ts
│   │   ├── theme/                         # tokens.ts (typed design tokens)
│   │   ├── App.tsx                        # Console Applicative with real entities
│   │   └── index.css                      # Tailwind v4 @theme configuration
├── AGENTS.md                              # System instructions & engineering constitution
├── MCP.md                                 # Model Context Protocol integration guide
├── PROJECT.md                             # Global project specification (v2.0.0)
├── README.md                              # Public repository documentation
└── Taskfile.yml                           # Task automation contract
```
