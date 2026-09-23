---
name: ci-cd-github-actions
description: >
  Conception, maintenance et debugging des workflows GitHub Actions : encapsulation
  stricte via Taskfile, configuration des caches hybrides (Go, Node), execution multi-plateforme
  et pattern CI Gate pour la protection des branches.
allowed-tools: Bash, Read, Write
---

# CI/CD & GitHub Actions

Ce document formalise les invariants des pipelines d'integration et de deploiement continu du repository.

---

## 1. Regle Absolue : Pas de Logique Non-Encapsulee

Un workflow GitHub Actions ne doit jamais executer de commandes bash complexes non encapsulees si un equivalent existe dans le `Taskfile.yml`.

```yaml
# ❌ INTERDIT (Logique dispersee non reproductible localement)
- run: |
    cd web-app
    npm run build
    cd ..
    CGO_ENABLED=0 go build -ldflags="-s -w" -o server ./cmd/server

# ✅ CONFORME (Delegation directe au Taskfile)
- run: task build
```

---

## 2. Structure Standard d'un Job GitHub Actions

Tout job CI doit garantir les elements suivants :
1. **Permissions minimales** : `permissions: contents: read` au niveau racine ou du job.
2. **Gestion des caches** :
   - Pour Go : `actions/setup-go@v5` avec `go-version-file: 'go.mod'` et `cache: true`.
   - Pour Node : `actions/setup-node@v4` avec `node-version: 22` et `cache: 'npm'`.
3. **Variables d'environnement d'hermetisme** :
   - `NO_COLOR: '1'` (desactive les codes d'echappement ANSI pour des logs de CI propres et lisibles).
   - `CGO_ENABLED: '0'` (garantit la compilation de binaires purement statiques).
4. **Outillage officiel Task** : Utiliser exclusivement `go-task/setup-task@v2`.

---

## 3. Le Pattern CI Gate

Tout ensemble de jobs paralleles (lint, test, build) doit converger vers un job unique `ci-gate` :

```yaml
ci-gate:
  name: CI Gate
  needs: [lint, test, build]
  runs-on: ubuntu-latest
  if: always()
  steps:
    - name: Verify All Preceding Checks
      run: |
        if [ "${{ needs.lint.result }}" != "success" ] || \
           [ "${{ needs.test.result }}" != "success" ] || \
           [ "${{ needs.build.result }}" != "success" ]; then
          echo "Erreur : Une ou plusieurs verifications CI ont echoue."
          exit 1
        fi
        echo "Succes : Toutes les verifications CI sont validees."
```

Ce pattern permet aux GitHub Rulesets de figer une seule verification obligatoire (`CI Gate`) sans etre affectes par l'ajout, la suppression ou le renommage de sous-jobs de build.

