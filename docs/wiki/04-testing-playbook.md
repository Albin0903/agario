# 04 — Playbook de Tests & Assurance Qualite

Ce guide definit les standards de test pour garantir l'absence de regressions et le determinisme de la stack.

---

## 1. Tests Unitaires Go (Format Table-Driven)

Chaque test unitaire suit obligatoirement la structure standard en tableau via une map anonyme indexee par le nom du cas de test :

```go
func TestService_Action(t *testing.T) {
 t.Parallel()

 tests := map[string]struct {
  input       domain.Input
  wantResult  domain.Result
  wantErr     error
 }{
  "nominal case returns expected result": {
   input:      domain.Input{ID: "valid-1"},
   wantResult: domain.Result{Status: "active"},
  },
  "empty identifier returns validation error": {
   input:   domain.Input{ID: ""},
   wantErr: domain.ErrValidation,
  },
 }

 for name, tt := range tests {
  t.Run(name, func(t *testing.T) {
   t.Parallel()

   svc := health.NewService()
   res, err := svc.DoSomething(tt.input)

   if tt.wantErr != nil {
    if !errors.Is(err, tt.wantErr) {
     t.Fatalf("err = %v, want %v", err, tt.wantErr)
    }
    return
   }

   if err != nil {
    t.Fatalf("unexpected error: %v", err)
   }

   if res != tt.wantResult {
    t.Errorf("got %v, want %v", res, tt.wantResult)
   }
  })
 }
}
```

### Invariants de test unitaire

1. **`t.Parallel()`** : Declare a la racine du test et dans chaque sous-test de la boucle pour valider l'absence de race condition.
2. **Pas d'assertions externes lourdes** : Utiliser la bibliotheque standard Go (`errors.Is`, verifications explicites).
3. **Hermétisme de la couche core** : Aucun appel reseau, disque ou base de donnees reelle dans `internal/core/`.

---

## 2. Tests d'Integration (Testcontainers-go)

Les tests d'integration testent de vrais adaptateurs techniques contre des conteneurs ephemeres lances a la volee :

```go
//go:build integration

package integration_test

import (
 "context"
 "testing"
 "time"

 "github.com/testcontainers/testcontainers-go"
 "github.com/testcontainers/testcontainers-go/modules/postgres"
 "github.com/testcontainers/testcontainers-go/wait"
)

func TestPostgresRepository(t *testing.T) {
 ctx := context.Background()

 pgContainer, err := postgres.Run(ctx,
  "postgres:16-alpine",
  postgres.WithDatabase("testdb"),
  postgres.WithUsername("testuser"),
  postgres.WithPassword("testpass"),
  testcontainers.WithWaitStrategy(
   wait.ForLog("database system is ready to accept connections").
    WithOccurrence(2).
    WithStartupTimeout(30*time.Second),
  ),
 )
 if err != nil {
  t.Fatalf("failed to start container: %v", err)
 }
 defer func() {
  if err := pgContainer.Terminate(ctx); err != nil {
   t.Logf("failed to terminate container: %v", err)
  }
 }()

 connStr, err := pgContainer.ConnectionString(ctx, "sslmode=disable")
 if err != nil {
  t.Fatalf("failed to get connection string: %v", err)
 }

 // Execution des verifications SQL avec connStr...
}
```

---

## 3. Tests Frontend (TypeScript & Biome)

Le frontend riche est valide a deux niveaux :

1. **Controle statique des types** : `npx tsc --noEmit` garantit l'absence d'erreurs de type et verifie la typologie des routes TanStack Router.
2. **Audit de code instantane** : `npx @biomejs/biome check src/` verifie la conformite du code aux regles de style et l'absence de `any`.

---

## 4. Harnais de Tests E2E Multicouche (`tests/e2e/`)

Le template integre un harnais de qualification E2E en boîte opaque articulé en 4 tiers (`tests/e2e/runner.ps1`) :

### Structure des 4 Tiers

| Tier | Périmètre | Assertions | Rôle |
| --- | --- | --- | --- |
| **Tier 1 : Features** | REQ-R1 à REQ-R5 | 135 | Couverture fonctionnelle unitaire des 27 exigences d'architecture |
| **Tier 2 : Limites & Charge** | BND-API, BND-CONC, BND-VIEW, BND-DESIGN | 25 | Cas limites d'API (400/404/405), 50 requêtes concurrentes, viewports 320px/2560px |
| **Tier 3 : Combinaisons** | COMBO-01 à COMBO-06 | 17 | Interactions croisées (Skeletons + Springs, Persistance + Header, Docker + Health) |
| **Tier 4 : Scénarios Métier** | SCENARIO-01 à SCENARIO-05 | 26 | Parcours complets : premier lancement, cycle CRUD, chargement CLS=0, intégrité pipeline |

### Invocation du Runner E2E

```powershell
# Execution complete de tous les tiers (203 assertions)
pwsh -NoProfile -File tests/e2e/runner.ps1 -Tier All

# Execution filtree par Tier
pwsh -NoProfile -File tests/e2e/runner.ps1 -Tier 1

# Mode strict (code de sortie 1 au moindre echec)
pwsh -NoProfile -File tests/e2e/runner.ps1 -Strict

# Via Taskfile
NO_COLOR=1 task test:e2e
```

---

## 5. Tests du Moteur de Traitement Python (`services/worker-python/`)

Le module Python est validé par un triple contrôle outillé :

1. **Tests unitaires (`pytest`)** : Exécute les suites isolées sans appel réseau externe (`uv run pytest -v`).
2. **Analyse statique (`ruff`)** : Contrôle du style et des règles d'import (`uv run ruff check .`).
3. **Typage strict (`mypy`)** : Aucun type implicite ou `Any` non justifié (`uv run mypy worker_python --strict`).
