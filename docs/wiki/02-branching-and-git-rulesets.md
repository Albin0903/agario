# 02 — Strategie de Branches, Rulesets & Git Workflow

Ce document detaille le cycle de vie du code source et les regles imposant un historique git propre, lineaire et auditable.

---

## 1. Modele de Branches (Issue-Driven Development)

Toutes les modifications s'articulent autour de deux branches protegees et de branches de fonctionnalites ephemeres :

```
main (Production, taggee vX.Y.Z)
  ^
  | (Pull Request de release validee)
develop (Tronc d'integration continue)
  ^
  | (Pull Request validee par CI)
  +---- feat/42-auth-jwt
  +---- fix/43-templ-refresh
  +---- chore/44-bump-deps
```

### Branches de reference
* **`main`** : Branche de production. Tout commit sur `main` doit etre pret a etre deploye et posseder un tag semantique (`v1.0.0`). Les fusions directes (`git push origin main`) sont interdites.
* **`develop`** : Branche principale de developpement et d'integration. Les fonctionnalites terminees y sont fusionnees apres validation de la CI.

### Nomenclature des branches de travail
Chaque branche de travail est creee a partir de `develop` et reference l'identifiant du ticket GitHub associe :
* `feat/<issue-id>-<slug>` : Ajout ou evolution fonctionnelle (ex: `feat/12-user-session`).
* `fix/<issue-id>-<slug>` : Correction de bug (ex: `fix/15-health-timeout`).
* `refactor/<issue-id>-<slug>` : Remaniement de code sans changement fonctionnel.
* `chore/<issue-id>-<slug>` : Taches techniques, dependances, outillage Taskfile.
* `hotfix/<slug>` : Correction critique appliquee d'urgence sur `main` puis re-fusionnee dans `develop`.

---

## 2. Conventional Commits v1.0.0

Chaque message de commit doit respecter la grammaire stricte :
```text
<type>(<scope optionnel>): <description imperative en minuscules>
```

### Types autorises
* `feat` : Ajout d'une fonctionnalite.
* `fix` : Correction d'anomalie.
* `refactor` : Remaniement de code.
* `perf` : Gain de performance mesure.
* `test` : Ajout ou modification de tests unitaires/integration.
* `chore` : Taches d'infrastructure, de dependances ou de build.
* `docs` : Documentation uniquement.
* `ci` : Modifications des pipelines GitHub Actions.

### Scopes standardises
`core`, `adapter`, `templ`, `spa`, `task`, `docker`, `ci`, `wiki`.

### Règle d'or : Zéro emoji
Les emojis sont interdits dans les messages de commit pour eviter la pollution de l'historique et les incompatibilites avec les outils CLI d'automatisation de releases.

---

## 3. GitHub Rulesets Declaratifs

La configuration des branches protegees est formalisee dans le fichier [`.github/rulesets/main-protection.json`](file:///c:/Users/albin/vie/build/.github/rulesets/main-protection.json) :
1. **Pull Request obligatoire** : Minimum 1 revue approbatrice requise.
2. **Resolution des fils de discussion** : Tous les commentaires doivent etre resolus avant merge.
3. **Historique lineaire obligatoire** : Interdiction des merge commits classiques (`--no-ff`). Seuls le Squash & Merge ou le Rebase sont acceptes.
4. **Verifications de statut strictes (CI Gate)** : Le job `CI Gate` du workflow GitHub Actions doit obligatoirement avoir reussi.
5. **Protection contre la destruction** : Suppression et push force (`--force`) interdits sur `main` et `develop`.

