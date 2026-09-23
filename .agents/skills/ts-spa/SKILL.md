---
name: ts-spa
description: >
  Développe l'application TypeScript/Vite/React avec typage strict.
  Utiliser pour toute tâche touchant au frontend riche (SPA),
  aux composants React, au routage, ou au build Vite.
allowed-tools: Bash, Read, Write
---

# TypeScript SPA — Conventions

## Rôle dans l'Architecture Hybride

Le frontend riche React 19 (`web-app/`) est le moteur privilégié pour les interfaces interactives exigeantes :
- **Jeux temps réel et toiles interactives (Canvas, Web Audio, animations 60 FPS, manipulation directe)**.
- **Visualisations complexes de données, drag-and-drop, éditeurs interactifs**.
- **Composants d'écosystème moderne** : Lucide React, primitives Radix, framer-motion/motion, Tailwind CSS v4.

Il n'est en aucun cas bridé ou réservé à des tableaux de bord administratifs : il doit être pleinement mobilisé dès que l'expérience utilisateur nécessite de la fluidité client.

## Emplacement

Tout le code SPA réside dans `web-app/`.

## Configuration TypeScript

- `strict: true` (obligatoire)
- `noImplicitAny: true` (obligatoire)
- `noUnusedLocals: true`
- `noUnusedParameters: true`

## Types interdits

```typescript
// ❌ INTERDIT
const data: any = fetchData();
function process(x: any): any { ... }

// ✅ CORRECT
const data: unknown = fetchData();
function process(x: UserInput): ProcessedResult { ... }

// ✅ Type guard pour unknown
function isUser(value: unknown): value is User {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    typeof (value as User).id === "string"
  );
}
```

## Linting & Formatage

Exclusivement Biome (pas ESLint, pas Prettier) :

```bash
# Vérification
npx @biomejs/biome check src/

# Auto-fix
npx @biomejs/biome check --write src/
```

## Conventions de composants React

```typescript
// Props typées avec interface
interface ButtonProps {
  label: string;
  onClick: () => void;
  variant?: "primary" | "secondary";
  disabled?: boolean;
}

export function Button({ label, onClick, variant = "primary", disabled = false }: ButtonProps): React.JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`btn btn-${variant}`}
    >
      {label}
    </button>
  );
}
```

## Client API Typé & Hook `useQuery`

Le socle fournit un client API unifié (`src/lib/api.ts`) et un hook avec debouncing de skeleton 300ms (`src/hooks/useQuery.ts`) :

```typescript
import { useQuery } from "../hooks/useQuery";
import { api } from "../lib/api";

// 1. Lecture déclarative avec protection CLS et annulation automatique
const { data, loading, showSkeleton, error, refetch } = useQuery<Item[]>("/api/items");

// 2. Mutations typées
const newItem = await api.post<Item>("/api/items", { name: "Projet Alpha" });
await api.delete(`/api/items/${newItem.id}`);
```

## Primitives UI Embarquées (`src/components/`)

Privilégier la composition à partir des composants locaux :
- `Badge` : Pastilles sémantiques (`active`, `pending`, `danger`, etc.)
- `Button` : Bouton tactile avec ressorts physiques et tailles de `xs` à `icon`
- `Card` : Surfaces satinées avec variantes `stage`, `interactive`, `compact`, `highlighted`
- `DataTable` : Grille typée avec tri et skeletons intégrés
- `Dialog` : Modale accessible `<dialog>` avec transition spring
- `EmptyState` : Affichage zéro-donnée explicatif
- `Input` : Champ accessible avec label permanent et état d'erreur
- `ToastContainer` : Notifications périphériques non-obstructives

## Build & Validation

```bash
# Type-check sans émission
npx tsc --noEmit

# Build production
npm run build

# Via Taskfile
task build:front
```
