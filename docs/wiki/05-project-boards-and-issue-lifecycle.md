# 05 — Cycle de Vie des Tickets, GitHub Projects & Taxonomie des Labels

Ce guide formalise la gestion de projet sur GitHub (Issues, Tableaux Kanban, Jalons et Labels) afin de garantir une traçabilité intégrale de la conception au déploiement.

---

## 1. Cycle de Vie d'un Ticket (Issue Lifecycle)

Chaque fonctionnalite ou correction traverse 5 etats stricts :

```
[1. Backlog] ──► [2. A Faire / Ready] ──► [3. En Cours] ──► [4. En Revue / PR] ──► [5. Termine / Done]
```

1. **Backlog** : Idees, propositions et besoins non priorises.
2. **A Faire (Ready)** : Ticket cadre via les formulaires YAML, doté d'une estimation et de criteres d'acceptation precis.
3. **En Cours** : Developpement actif sur une branche dediee (`feat/<id>-...` ou `fix/<id>-...`).
4. **En Revue (PR)** : Pull Request ouverte liant le ticket (`Fixes #<id>`), CI au vert.
5. **Termine (Done)** : PR fusionnee dans `develop` apres revue et statut `CI Gate` valide.

---

## 2. Taxonomie Standardisee des Labels

Pour eviter la multiplication anarchique d'etiquettes, le projet utilise un schema a 4 dimensions avec prefixes imposes :

| Prefix | Label | Couleur | Usage |
|---|---|---|---|
| **`type/`** | `type/feat` | `#0E8A16` | Nouvelle fonctionnalite |
| | `type/fix` | `#D93F0B` | Correction d'anomalie |
| | `type/refactor` | `#FBCA04` | Remaniement architectural |
| | `type/perf` | `#1D76DB` | Optimisation de performance |
| | `type/docs` | `#0075CA` | Documentation ou Wiki |
| | `type/infra` | `#5319E7` | Taskfile, Docker, GitHub Actions |
| **`scope/`** | `scope/core` | `#C5DEF5` | Domaine metier Go pur |
| | `scope/adapter` | `#BFD4F2` | Handlers HTTP, SQL, serveurs |
| | `scope/templ` | `#D4C5F9` | Templates Templ et HTMX |
| | `scope/spa` | `#F9D0C4` | Application React / TypeScript |
| **`priority/`**| `priority/critical`| `#B60205` | Bloquant, empeche le fonctionnement |
| | `priority/high` | `#D93F0B` | Priorite elevee |
| | `priority/medium` | `#FBCA04` | Priorite standard |
| | `priority/low` | `#0E8A16` | Amelioration mineure |
| **`status/`** | `status/triage` | `#EDEDED` | En attente de qualification |
| | `status/blocked`| `#000000` | Bloque par une dependance externe |

---

## 3. Configuration Recommandee de GitHub Projects

Un tableau de projet GitHub Projects (v2) doit comporter les colonnes et automatisations suivantes :
* **Colonnes** : `Backlog`, `Ready`, `In Progress`, `In Review`, `Done`.
* **Flux automatises (Built-in workflows)** :
  * Lors de la creation d'une issue avec `status/triage` -> assigner a `Backlog`.
  * Lors de l'ouverture d'une Pull Request -> deplacer la carte associee dans `In Review`.
  * Lors du merge d'une Pull Request -> deplacer la carte dans `Done`.

