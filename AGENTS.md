# Instructions Système Agent — Architecture & Développement

Ce projet applique une architecture hybride Go / Templ / Vite sous contraintes strictes de typage statique, de performance d'exécution, de déterminisme outillé et de discipline d'ingénierie anti-vibe-coding.

---

## 1. Principes cardinaux & Anti-Vibe Coding

1. **Vérification avant validation :** Tout changement doit être validé par le Taskfile (`NO_COLOR=1 task check`) avant d'être considéré comme achevé. Aucun succès ne se déclare sur intuition.
2. **Pas d'outils ad-hoc :** Interdiction formelle d'exécuter des commandes brutes non encapsulées si un équivalent existe dans `Taskfile.yml`.
3. **Zéro dépendance implicite :** Privilégier la bibliothèque standard Go. L'ajout d'une dépendance externe requiert une justification explicite.
4. **Typage hermétique :** Aucun type `any` ou `interface{}` non contraint n'est toléré, que ce soit en Go ou en TypeScript (`strict: true`, `noImplicitAny: true`).
5. **Zéro emoji :** Emojis strictement proscrits dans le code source, les commentaires, les messages de commit, les logs et les PRs.
6. **Commentaires causaux :** Documenter exclusivement le « pourquoi » (contraintes métier, concurrence, invariants), jamais le « quoi » (paraphrase syntaxique).
7. **Diffs chirurgicaux :** Portée minimale d'édition. Pas de refactorisation opportuniste, pas de code mort ou commenté.
8. **Inviolabilité de l'expérience utilisateur & Épuration radicale de l'information (Zéro jargon technique & Zéro télémétrie décorative) :** L'interface utilisateur finale s'adresse exclusivement à l'utilisateur du produit métier. Il est formellement interdit d'afficher les noms des technologies (Go, HTMX, Templ, Vite, React, Docker, Tailwind, etc.), des métriques d'implémentation ou des labels techniques dans les vues. Chaque donnée affichée doit avoir une utilité décisionnelle directe : toute télémétrie décorative, faux indicateur d'IA ou statistique non sollicitée est proscrite.
9. **Squelette d'application complet & Scène non-bloquante (Wireframing First & Inviolabilité du sujet d'intérêt) :** Même pour un prototype rapide, l'agent ne livre jamais un composant orphelin au milieu d'une page vide. Tout écran structure obligatoirement : barre supérieure produit (identité, contexte, règles/paramètres), scène centrale (The Stage, centré sans scrolls parasites), et périphériques fonctionnels. L'état d'arrêt ou d'achèvement d'un processus (victoire, validation, confirmation) ne doit jamais recouvrir l'élément focal par une modale opaque : la confirmation s'intègre en périphérie directe (bannière haute, volet latéral, pulsation) en laissant l'artéfact principal 100% visible et manipulable.
10. **Luminosité par défaut & Thème clair satiné (Bannissement du thème sombre gamer) :** Tout produit grand public (B2C, jeux familiaux, outils bureautiques) démarre obligatoirement sur un thème clair satiné (`bg-slate-50` à `bg-white`), à fort contraste typographique (`text-slate-900`) et ombrages solaires doux (`shadow-slate-200/50`). L'introduction d'un mode sombre doit être un choix utilisateur explicite ou un paramètre secondaire, jamais le canevas imposé.
11. **Tangibilité physique & Invariants mécaniques :** Tout objet ou plateau interactif doit être conçu selon ses contraintes mécaniques réelles (sandwich de couches z-index : socle arrière -> cavité -> coulisse interne -> façade ajourée -> zone de frappe). Les animations de déplacement doivent refléter la cinématique physique réelle (traversée, masquage par les montants, rebond terminal, libération par gravité) plutôt qu'une simple transition de coordonnées.
12. **Hiérarchie d'action directe (Contrôle direct à la source) :** Tout indicateur contextuel affiché à l'écran (compte à rebours, compteur de points, statut audio) doit être lui-même le commutateur de son propre état (clic direct pour basculer actif/inactif). Les modales de réglages ne sont réservées qu'aux ajustements structurels peu fréquents.
13. **Obligation de revue visuelle multi-résolutions par MCP :** Aucune tâche d'interface ne peut être déclarée achevée sans au moins deux captures Chrome DevTools MCP vérifiées (format bureau 1200x900 et format mobile 390x844) inspectant le comportement au clic, l'alignement et les états limites.
14. **Génération en 1 Prompt & Focalisation du Regard (Gaze Direction) :** Dès le prompt initial, l'agent déduit le public cible (B2B, B2C, productivité, outil métier) et calibre la scène pour orienter spontanément l'attention vers l'action maîtresse en moins de 3 secondes. Le guidage s'opère par le contraste (palette niveaux 9–10 pour le point focal, niveaux 11–12 pour le texte, ombrages satinés doux) et les espaces de respiration, sans modale opaque d'accueil, sans bannière bruyante ni parcours tutoriel intrusif.
15. **Skeletons Zéro-Décalage & Expérience Réelle (Zero CLS & Real Data) :** Tout état de chargement asynchrone exploite des skeletons reproduisant fidèlement la géométrie finale (`w-*`, `h-*`, `gap-*`) afin de garantir l'absence totale de saut de mise en page (Cumulative Layout Shift = 0). Toute interface présente des entités métier réelles et plausibles : le *lorem ipsum*, les placeholders "foo/bar" et la télémétrie décorative non décisionnelle sont formellement proscrits.
16. **Initiative outillée & Recherche de vérité terrain (Bannissement de la conformité passive) :** L'agent ne doit jamais concevoir ou extrapoler de mémoire lorsqu'une référence externe existe (URL, jeu, produit existant, API tierce). Il a l'obligation formelle et spontanée de mobiliser ses outils (Chrome DevTools MCP, navigation, requêtes HTTP, extraction de code source, inspection réseau) pour collecter les spécifications réelles (assets exacts, dimensions, palette, cinématique, sons) avant d'écrire la moindre ligne de code.
17. **Invariants kinesthésiques & "Game Juice" (Priorité Canvas 60 FPS & Boucle sensorielle) :** Une interface interactive ne se juge pas à sa structure statique (cases DOM/SVG), mais à sa physique, sa réactivité et son retour sensoriel. Pour toute interaction à haute fréquence (>30 Hz), l'agent privilégie immédiatement un Canvas 2D/WebGL 60 FPS avec interpolation sous-cellulaire (delta time) plutôt qu'un découpage DOM/SVG par cellules. Il implémente obligatoirement les invariants de maniabilité (tampon d'entrée FIFO pour ne jamais perdre de touche rapide) et la boucle sensorielle complète (Web Audio procédural, expressions visuelles, anticipations).
18. **Obligation de dépassement d'attente (Exceed Expectations by Default & Anti-Satisficing) :** L'agent ne livre jamais un code minimaliste qui se contente de compiler et de valider les tests unitaires ("satisficing"). Il valide son travail selon 4 critères d'achèvement avant de déclarer la tâche terminée : (1) Fidélité visuelle absolue par rapport à la référence, (2) Maniabilité parfaite sans latence sous 50ms, (3) Sensibilité et vie (audio procédural, micro-animations expressives), et (4) Résilience locale (assets et logique embarqués sans dépendance réseau fragile).

---

## 2. Contrat de commandes (Taskfile)

Toute commande doit retourner un code de sortie strict (`0` = succès). Exécuter systématiquement avec `NO_COLOR=1`.

* `task init` : Initialise un nouveau projet issu du template avec le nom de module personnalisé.
* `task generate` : Exécute `templ generate` pour compiler les vues Templ en Go.
* `task fmt` : Formate automatiquement le code Go (`gofumpt`), Templ (`templ fmt`) et TypeScript (`biome check --write`).
* `task lint` : Exécute `golangci-lint` (Go), `biome check` (TypeScript), et `lint:design` (conformité des tokens de design).
* `task lint:design` : Audite la conformité des tokens de design (interdit les valeurs Tailwind arbitraires).
* `task test:unit` : Exécute `go test -v -count=1 ./internal/...`.
* `task test:integration` : Exécute les suites Testcontainers-go.
* `task test:e2e` : Exécute la suite complète d'exigences et de scénarios E2E (`tests/e2e/runner.ps1`).
* `task build:front` : Compile l'application TypeScript/Vite dans `web-app/dist/`.
* `task build:bin` : Compile le binaire statique Go (`CGO_ENABLED=0`).
* `task check` : Pipeline complet obligatoire avant tout commit (`generate` -> `lint` -> `test:unit` -> `build:front` -> `build:bin`).
* `task dev` : Lance le serveur Go avec templates compilés.
* `task dev:front` : Lance le serveur Vite de développement TypeScript avec HMR.

---

## 3. Règles techniques par domaine

### Backend (Go)

* **Architecture :** Modèle hexagonal pur. La logique métier (`internal/core/`) ne dépend d'aucun adaptateur (`internal/adapters/`). Les interfaces sont déclarées dans le paquet consommateur (`internal/ports/` ou `core`).
* **Gestion des erreurs :**
  * Pas de masquage : utiliser `fmt.Errorf("contexte de l'action %s: %w", id, err)`.
  * Ne jamais ignorer une erreur retournée. Pas de `_ = fn()`.
  * Interdiction stricte de `panic()` hors de l'initialisation critique (`main.go`).
* **Concurrence & Contexte :** Chaque fonction réseau, disque ou base de données prend obligatoirement un `ctx context.Context` en premier paramètre.
* **Tests :** Format unitaire systématique en tableaux (*table-driven tests* avec `map[string]struct{ ... }`) et `t.Parallel()`.

### Frontend Léger (Templ + HTMX)

* Emplacement : `internal/adapters/http/views/`.
* Tout fragment HTML dynamique est une fonction Templ Go compilée recevant un struct typé (jamais de `map[string]any`).
* Zéro logique JavaScript inline : toutes les interactions passent par les attributs standards HTMX (`hx-get`, `hx-post`, `hx-target`, `hx-swap`).
* Après toute modification de fichier `.templ`, exécuter obligatoirement `task generate`.

### Frontend Riche (TypeScript + Vite)

* Emplacement : `web-app/`.
* Mode strict activé : `noImplicitAny: true`, `strict: true`.
* Formatage et linting délégués exclusivement à **Biome** (`npx @biomejs/biome check --apply`).
* Routage déclaratif et typé (TanStack Router). Interdiction d'URLs codées en dur sans validation statique.
* Styling : Tailwind CSS v4 via `@tailwindcss/vite`.

### Services Asynchrones, Scraping & Data (Python)

* Emplacement : `services/worker-python/`.
* Gestionnaire d'environnement & dépendances : **`uv`** exclusivement (aucun `pip install` ad-hoc).
* Formatage et linting : **`ruff`** (`uv run ruff format . && uv run ruff check --fix .`).
* Typage statique strict : **`mypy --strict`** obligatoire (aucun type implicite ou `Any` non justifié).
* Tests unitaires : **`pytest`** avec mocks réseau stricts (zéro dépendance externe non maîtrisée durant les tests unitaires).

### Packaging & Déploiement (Docker)

* Build multi-stage obligatoire.
* Le stage final doit cibler **exclusivement** `scratch` (image minimale 15–25 Mo).
* Le binaire doit être lié statiquement : `CGO_ENABLED=0 go build -ldflags="-s -w"`.
* Injecter les certificats racines SSL dans l'image finale : `COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/`.

---

## 4. Règles de Cycle Git & GitHub

1. **Stratégie de branches :**
   * `main` : Production stable, protégée par GitHub Ruleset. Déploiements étiquetés uniquement.
   * `develop` : Tronc d'intégration continue. Toute branche de travail en est issue.
   * `feat/<issue-id>-<slug>` ou `fix/<issue-id>-<slug>` : Branches de travail éphémères.
2. **Conventional Commits v1.0.0 :**
   * Structure : `<type>(<scope>): <description>` (ex: `feat(core): implement user registration`).
   * Types autorisés : `feat`, `fix`, `refactor`, `perf`, `test`, `chore`, `ci`, `docs`.
   * Scopes reconnus : `core`, `adapter`, `templ`, `spa`, `python`, `design`, `task`, `docker`, `ci`, `wiki`.
3. **Pull Requests :**
   * Doit lier l'issue résolue : `Fixes #<id>`.
   * Rebase obligatoire sur `develop` avant ouverture.
   * Fusion par squash & merge ou rebase (historique linéaire imposé par ruleset).

---

## 5. Skills disponibles

Les compétences spécialisées sont dans `.agents/skills/`. Charger impérativement la skill correspondante selon la tâche :

| Skill | Déclencheur |
| --- | --- |
| `code-discipline` | Invariants anti-vibe-coding, zéro emoji, commentaires « pourquoi », diffs minimaux |
| `git-workflow` | Cycle git, branches depuis `develop`, Conventional Commits, préparation de PR |
| `ci-cd-github-actions` | Workflows GitHub Actions, caches, matrice et portail CI Gate |
| `testing-quality` | Table-driven unit tests, Testcontainers-go, isolation par contextes et ports |
| `github-governance` | Gestion des issues, tableaux GitHub Projects, labels, milestones |
| `arch-boundaries` | Découplage hexagonal, interfaces, ports/adapters, sens des dépendances |
| `go-backend` | Handlers, services, repositories, tests Go, gestion d'erreurs |
| `templ-htmx` | Templates Templ typés, fragments HTMX et compilation |
| `htmx-ui-patterns` | Interactions HTMX avancées (recherche live avec debounce, modales, toasts OOB) |
| `ts-spa` | Application TypeScript/Vite, composants React 19, TanStack Router strict |
| `frontend-design` | Protocole de design adaptatif, recherche UI (GitHub / composants modernes), prototypage Stitch MCP, tokens contextuels, Squelette Produit |
| `design-engineering` | Invariants mathématiques de design : échelle typographique, grille spatiale 8px, physique d'animation, contraste APCA, alignement optique |
| `deploy-docker` | Dockerfile, build multi-stage, conteneurisation vers scratch |
| `python-worker` | Moteur de calcul Python, pipeline dynamique, uv, ruff, mypy et pytest |
| `mcp-tooling` | Exploitation et configuration des serveurs Model Context Protocol |

---

## 6. Intégration MCP (Model Context Protocol)

Le projet s'appuie sur le protocole MCP déclaré dans `.mcp/servers.json` :

* **`gopls`** : Pour la navigation de code et l'inspection statique de types Go.
* **`Stitch`** : Pour la génération de maquettes texte-vers-UI, l'exploration de variantes graphiques et l'extraction de design systems sans règles hardcodées.
* **`chrome-devtools`** : Pour l'audit visuel multi-résolutions obligatoire (captures bureau 1200x900 et mobile 390x844), l'exécution de scénarios de test et l'inspection de console sans avertissements.
* **`fetch`** : Pour l'interrogation de documentation officielle sans dérive contextuelle.
