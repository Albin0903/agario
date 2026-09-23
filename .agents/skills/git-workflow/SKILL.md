---
name: git-workflow
description: >
  Regles de cycle Git et gestion de branches pour agents : creation depuis develop,
  convention de nommage de branches, Conventional Commits stricts, resolution sans
  merge commit et respect des rulesets de protection.
allowed-tools: Bash, Read, Write
---

# Git Workflow & Standards de Branches

Ce guide s'applique a toute operation de versionnement Git executee par un agent ou un developpeur.

---

## 1. Regles de Creation de Branche

1. **Branche d'origine** : Toute branche de travail doit imperativement etre issue de `develop` (a jour avec `origin/develop`), jamais de `main`.
2. **Convention de nommage** :
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b <type>/<issue-id>-<slug-court>
   ```
   * Exemples :
     - `feat/104-oauth-provider`
     - `fix/112-templ-nil-pointer`
     - `refactor/115-port-repository`
     - `chore/120-taskfile-update`

---

## 2. Format des Commits (Conventional Commits v1.0.0)

Chaque commit atomique doit respecter la structure :
```text
<type>(<scope optionnel>): <message imperatif court>

[corps optionnel expliquant le contexte technique]

[footer optionnel, ex: Closes #104]
```

### Types autorises
* `feat` : Nouvelle fonctionnalite livree a l'utilisateur.
* `fix` : Correction d'un bug averé.
* `refactor` : Modification du code sans impact fonctionnel ni correction de bug.
* `perf` : Optimisation mesurable.
* `test` : Ajout ou reecriture de tests.
* `chore` : Modification des outils de build, dependances ou Taskfile.
* `ci` : Fichiers GitHub Actions.
* `docs` : Documentation et Wiki.

### Scopes monorepo
* `core` : Domaine metier pur Go (`internal/core`).
* `adapter` : Adaptateurs HTTP, serveurs ou DB (`internal/adapters`).
* `templ` : Vues et fragments Templ/HTMX (`internal/adapters/http/views`).
* `spa` : Frontend React 19 et TanStack Router (`web-app`).
* `task` : Fichiers d'orchestration (`Taskfile.yml`).
* `docker` : Fichiers conteneurs (`build/Dockerfile`).

---

## 3. Preparation de Pull Request

1. **Rebase sur `develop`** : Toujours rebaser sa branche locale sur `develop` avant de soumettre pour eviter les commits de merge parasites :
   ```bash
   git fetch origin develop
   git rebase origin/develop
   ```
2. **Verification pre-push** :
   ```bash
   NO_COLOR=1 task check
   ```
   *Si cette commande retourne un code != 0, le push est interdit.*
3. **Titre de PR conforme** : Le titre de la PR doit suivre la meme norme Conventional Commits que les commits pour satisfaire le validateur GitHub Actions `semantic-pr`.

