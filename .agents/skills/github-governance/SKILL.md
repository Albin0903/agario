---
name: github-governance
description: >
  Gouvernance de projet GitHub : cycle de vie des tickets, structuration des milestones,
  taxonomie des labels a 4 dimensions et automatisation des tableaux Kanban GitHub Projects.
allowed-tools: Bash, Read, Write
---

# Gouvernance de Projet GitHub & Gestion de Tickets

Ce document definit les regles d'organisation pour structurer la collaboration entre agents et equipes humaines sur GitHub.

---

## 1. Cycle de Vie des Tickets (Issues)

1. **Qualification Initiale (`status/triage`)** :
   Chaque ticket nouvellement cree doit obligatoirement utiliser un des formulaires YAML (`.github/ISSUE_TEMPLATE/bug_report.yml` ou `feature_request.yml`).
2. **Priorisation & Assignation** :
   Le ticket recoit au moins 3 labels :
   - `type/*` (ex: `type/feat`, `type/fix`)
   - `scope/*` (ex: `scope/core`, `scope/templ`, `scope/spa`)
   - `priority/*` (ex: `priority/high`, `priority/medium`)
3. **Mise en chantier** :
   Le ticket est rattache a un jalon (Milestone) et deplace dans la colonne `In Progress` du tableau GitHub Projects des qu'une branche de travail est ouverte.

---

## 2. Taxonomie des Labels

| Dimension | Pattern | Exemples | Rôle |
|---|---|---|---|
| **Nature** | `type/<nom>` | `type/feat`, `type/fix`, `type/refactor`, `type/perf`, `type/infra` | Categorie de travail |
| **Périmètre** | `scope/<nom>` | `scope/core`, `scope/adapter`, `scope/templ`, `scope/spa` | Composant monorepo impacte |
| **Priorité** | `priority/<nom>`| `priority/critical`, `priority/high`, `priority/medium`, `priority/low` | Urgence de traitement |
| **Statut** | `status/<nom>` | `status/triage`, `status/ready`, `status/blocked` | Etat de l'avancement |

---

## 3. Automatisation des Tableaux GitHub Projects

Dans GitHub Projects v2, les flux automatises sont configures ainsi :
1. **Item Added to Project** : Si `status/triage` est present -> statut positionne sur `Backlog`.
2. **Pull Request Linked** : Des qu'une PR contenant `Fixes #...` est ouverte -> statut passe sur `In Review`.
3. **Pull Request Merged** : Des que la PR est fusionnee -> statut passe automatiquement sur `Done`.

