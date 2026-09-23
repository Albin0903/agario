# [TODO: Nom de votre application]

> [TODO: Description concise en une phrase de la finalité de l'application.]

<!--
================================================================================
SECTION 1 : PROJET (À PERSONNALISER)
Cette section est dédiée aux spécificités de votre application.
Remplacer les balises [TODO: ...] par la documentation propre à votre projet.
================================================================================
-->

## Présentation du projet

[TODO: Décrire la finalité métier du projet, le contexte, le public cible et la valeur ajoutée apportée par votre application.]

### Fonctionnalités principales

- [TODO: Fonctionnalité 1 — Description de l'action utilisateur ou du traitement métier]
- [TODO: Fonctionnalité 2 — Description de l'action utilisateur ou du traitement métier]
- [TODO: Fonctionnalité 3 — Description de l'action utilisateur ou du traitement métier]

### Endpoints applicatifs

| Méthode | Route | Description | Consommateur |
| --- | --- | --- | --- |
| `GET` | `/` | [TODO: Page d'accueil / Tableau de bord SSR] | Navigateur (Templ + HTMX) |
| `GET` | `/app/` | [TODO: Console riche / Interface interactive] | Navigateur (React SPA) |
| `GET` | `/api/health` | Diagnostic de santé et de temps de fonctionnement | Monitoring / Sonde k8s |
| `GET` | `/api/health/fragment` | Fragment HTML dynamique d'état | HTMX Polling |
| `GET` | `/api/[TODO]` | [TODO: Endpoint API métier JSON] | Client API / SPA |

### Initialisation d'un nouveau projet depuis ce template

Pour créer un nouveau projet à partir de ce template GitHub :

```bash
# 1. Cloner votre nouveau dépôt GitHub
git clone <url-de-votre-nouveau-depot> && cd <nom-du-depot>

# 2. Renommer automatiquement le module Go et le package front en une commande
task init -- github.com/<votre-organisation>/<nom-du-projet>

# 3. Installer les dépendances du frontend riche
cd web-app && npm install && cd ..

# 4. Valider l'intégrité de la stack complète
task check

# 5. Lancer le serveur de développement
task dev
```

---

<!--
================================================================================
SECTION 2 : SOCLE TECHNIQUE & COMMANDES (STANDARD PARTAGÉ)
Cette section constitue le contrat architectural, technique et d'ingénierie
commun à tous les projets issus du template. Elle reste identique et pérenne.
================================================================================
-->

## Socle Technique & Commandes Standard

Ce socle applique une architecture hybride **Go / Templ / Vite** sous contraintes strictes de typage statique, de performance d'exécution, de déterminisme outillé et de discipline d'ingénierie anti-vibe-coding.

---

### 1. Stack Technique

| Composant | Rôle dans la stack | Version / Spécification |
| --- | --- | --- |
| **Go** | Backend & API métier pure | 1.26+ (Stdlib pure, `log/slog`, `net/http`) |
| **Templ + HTMX** | Frontend léger (SSR / 80 % de l'application) | Templ v0.3.1020, HTMX v2.0.10 |
| **TypeScript + Vite** | Frontend riche (SPA isolée / 20 % de l'application) | React 19, TanStack Router v1.170, Tailwind CSS v4 |
| **Taskfile (`go-task`)** | Orchestration locale déterministe | v3.53+ (YAML multiplateforme) |
| **Biome** | Linter & Formatter TypeScript | v1.9+ (Exécution Rust sub-50ms) |
| **golangci-lint** | Linter hermétique Go | v2.13+ (Formatters stricts `gofumpt`) |
| **Docker Scratch** | Packaging applicatif minimal | Image multi-stage 15–25 Mo, `CGO_ENABLED=0` |
| **Devcontainer** | Environnement standardisé conteneurisé | Go 1.26, Node 22, Docker-in-Docker |
| **GitHub Actions** | Intégration continue & Rulesets | Workflows CI Gate, Docker scratch, PR sémantiques |
| **Model Context Protocol (MCP)** | Intégration outillée pour agents IA | Spécification `.mcp/servers.json` (`gopls`, `devtools`, `fetch`) |

---

### 2. Prérequis & Installation de l'outillage

- **Go** : 1.26+
- **Node.js** : 22+
- **Docker** : Requis pour les builds de conteneurs et les tests Testcontainers
- **go-task** : `go install github.com/go-task/task/v3/cmd/task@latest` (ou via `winget` / `scoop` / `brew`)
- **templ** : `go install github.com/a-h/templ/cmd/templ@latest`
- **golangci-lint** : v2+ (`curl -sSfL https://golangci-lint.run/install.sh | sh -s -- -b $(go env GOPATH)/bin v2.13.2`)

---

### 3. Commandes Déterministes (Taskfile)

Toutes les opérations d'ingénierie sont encapsulées dans `Taskfile.yml`. L'usage direct de commandes ad-hoc non encapsulées est proscrit.

```bash
# ─── Initialisation & Démarrage ────────────────────────────
task init -- <nouveau-module> # Renomme le module Go, les imports et le package.json
task dev                      # Génère les templates Templ et lance le serveur local (:8080)
task dev:front                # Lance le serveur Vite en mode développement avec HMR (:5173)

# ─── Validation & Qualité ───────────────────────────────────
task check                    # Pipeline complet obligatoire (generate -> lint -> test -> build)
task fmt                      # Formate l'ensemble du code (Templ fmt, Go fumpt, Biome write)
task lint                     # Analyse statique complète (golangci-lint + Biome check)
task test:unit                # Exécute les tests unitaires table-driven Go
task test:integration         # Exécute les tests d'intégration Testcontainers

# ─── Compilation & Packaging ────────────────────────────────
task generate                 # Compile les fichiers .templ en code source Go
task build:front              # Compile l'application TypeScript/Vite dans web-app/dist/
task build:bin                # Compile le binaire statique Go dans tmp/server(.exe)
task build                    # Compile l'ensemble des cibles (generate -> front -> bin)
task docker:build             # Construit l'image Docker multi-stage finale sur scratch
task docker:run               # Exécute le conteneur Docker en local (:8080)
task clean                    # Nettoie les artefacts de compilation temporaires
```

---

### 4. Architecture Hexagonale & Invariants Métier

Le backend applique un découplage hexagonal strict :

```
internal/
├── core/             # Logique métier pure (indépendante de tout framework)
│   ├── domain/       # Entités, value objects, erreurs sentinelles
│   └── health/       # Service santé applicatif et métriques d'uptime
├── ports/            # Interfaces consommées par le core
└── adapters/         # Adaptateurs d'infrastructure et d'entrée/sortie
    ├── http/views/   # Vues et composants Templ compilés en Go
    └── httpserver/   # Routeur HTTP stdlib, handlers et middlewares
```

- **Sens des dépendances :** `adapters → ports ← core`. Le répertoire `core/` ne dépend d'aucun adaptateur.
- **Typage hermétique :** Aucun type `any` ou `interface{}` non contraint.
- **Gestion des erreurs :** Contexte systématique avec `%w` (`fmt.Errorf("contexte: %w", err)`). Zéro masquage, zéro `panic()`.

---

### 5. Gouvernance GitHub & Cycle de Vie du Code

Le cycle de développement suit les standards formalisés dans `docs/wiki/` et appliqués par les agents autonomes :

- **Stratégie de branches :**
  - `main` : Production stable, protégée par GitHub Ruleset. Déploiements taggés (`vX.Y.Z`).
  - `develop` : Tronc d'intégration continue. Branche parente de tout développement.
  - `feat/<issue-id>-<slug>`, `fix/<issue-id>-<slug>` : Branches de travail éphémères.
- **Conventional Commits v1.0.0 :** `<type>(<scope>): <description>` (ex: `feat(core): add authentication service`). Zéro emoji toléré.
- **Workflows GitHub Actions (`.github/workflows/`) :**
  - `ci.yml` : Exécute `task check` sur matrice et converge vers le portail obligatoire `CI Gate`.
  - `docker.yml` : Valide la compilation de l'image Docker minimale sur `scratch`.
  - `semantic-pr.yml` : Vérifie la conformité des titres de Pull Requests.
- **GitHub Rulesets (`.github/rulesets/main-protection.json`) :** PR obligatoire, 1 approbation, rebase/squash linéaire, statut `CI Gate` validé.

---

### 6. Arborescence du Dépôt

```
├── .github/                   # Gouvernance GitHub (workflows CI, rulesets, issue templates)
├── .agents/skills/            # 15 Agent Skills spécialisées (agentskills.io)
├── docs/wiki/                 # Wiki in-repo (architecture, git rulesets, CI, tests, governance, UI research)
├── cmd/server/                # Point d'entrée exécutable (main.go & run pattern)
├── internal/                  # Architecture hexagonale (core, ports, adapters)
├── services/worker-python/    # Moteur de calcul & design engineering Python (uv, ruff, mypy)
├── web-app/                   # Frontend riche SPA (React 19 + TanStack Router + Tailwind v4)
├── tests/                     # Tests d'intégration Testcontainers et harnais E2E 4-tiers
├── scripts/                   # Scripts d'outillage déterministes (init.go, lint-design.ps1)
├── build/                     # Dockerfile multi-stage vers scratch
├── Taskfile.yml               # Orchestration locale déterministe
├── AGENTS.md                  # Invariants système pour agents d'ingénierie IA
├── PROJECT.md                 # Spécification globale du projet (v1.0.0)
└── MCP.md                     # Guide d'intégration Model Context Protocol
```

---

### 7. Principes Cardinaux & Anti-Vibe Coding

1. **Vérification avant validation :** Tout changement doit être validé par `NO_COLOR=1 task check` avant d'être considéré comme achevé.
2. **Pas d'outils ad-hoc :** Interdiction d'exécuter des commandes hors `Taskfile.yml`.
3. **Zéro dépendance implicite :** Bibliothèque standard Go prioritaire.
4. **Typage hermétique :** Aucun type non contraint en Go ou TypeScript (`strict: true`).
5. **Zéro emoji :** Proscrits dans le code, les commentaires, les messages de commit et les PRs.
6. **Commentaires causaux :** Documenter exclusivement le « pourquoi », jamais le « quoi ».
7. **Diffs chirurgicaux :** Portée minimale d'édition. Pas de refactorisation opportuniste.
