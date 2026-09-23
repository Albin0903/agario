# 03 — CI/CD, Automatisation & Caches

Ce document expose les principes d'automatisation continue du projet via GitHub Actions et Taskfile.

---

## 1. Philosophie d'Orchestration : Le Miroir Local / CI

La cause premiere d'echec en CI est la divergence entre les commandes tapees par le developpeur ou l'agent en local et les scripts executes sur les runners distants.

Pour neutraliser ce risque, **GitHub Actions n'execute aucune logique ad-hoc**. Toutes les etapes deleguent strictement l'execution aux cibles standardisees de `Taskfile.yml` :

* `task generate` : Generation des fichiers Go a partir des `.templ`.
* `task lint` : Verification de code Go (`golangci-lint`) et TypeScript (`biome check`).
* `task test:unit` : Tests unitaires Go sans compilation de code C (`CGO_ENABLED=0`).
* `task build:front` : Compilation Vite dans `web-app/dist/`.
* `task build:bin` : Compilation du binaire statique Go.
* `task check` : Pipeline local complet reproduisant fidelement les contraintes de la CI.

---

## 2. Strategie de Cache Multi-Niveaux

Le workflow `.github/workflows/ci.yml` tire parti de 4 caches distincts pour reduire le temps d'execution total a moins de 60 secondes :

1. **Cache Go Modules & Build Cache** :
   Gere via `actions/setup-go@v5` (`cache: true`). Conserve `~/go/pkg/mod` et le cache de compilation incrémental `~/.cache/go-build`.
2. **Cache npm** :
   Gere via `actions/setup-node@v4` (`cache: 'npm'`, cible `web-app/package-lock.json`). Evite les telechargements reseau lors de `npm ci`.
3. **Cache uv / Python** :
   Gere via `astral-sh/setup-uv@v5` (`enable-cache: true`, cible `services/worker-python/uv.lock`). Met en cache les distributions et roues Python pré-compilées.
4. **Cache Docker Buildx** :
   Dans `.github/workflows/docker.yml`, utilisation du backend `type=gha` pour mettre en cache les couches de l'image multi-stage.

---

## 3. Le Pattern « CI Gate »

Plutot que de declarer chaque job unitaire dans les regles de protection de branches GitHub (ce qui rend la configuration fragile au moindre renommage de job), un job final de synthese appele **`CI Gate`** collecte les resultats :

```yaml
ci-gate:
  name: CI Gate
  needs: [lint, test, build]
  runs-on: ubuntu-latest
  if: always()
  steps:
    - run: |
        if [ "${{ needs.lint.result }}" != "success" ] || \
           [ "${{ needs.test.result }}" != "success" ] || \
           [ "${{ needs.build.result }}" != "success" ]; then
          exit 1
        fi
```

Ce pattern garantit que les GitHub Rulesets n'ont besoin de surveiller qu'un seul statut invariant : `CI Gate`.
