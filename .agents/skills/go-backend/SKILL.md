---
name: go-backend-patterns
description: >
  Implémente des handlers d'API, services métier et repositories en Go strict.
  Utiliser dès qu'une tâche touche à la logique backend, aux modèles,
  aux routes HTTP, aux tests unitaires ou d'intégration Go.
allowed-tools: Bash, Read, Write
---

# Backend Go — Conventions et Patterns

## Gestion des erreurs

### Obligatoire
```go
// ✅ Toujours wrapper avec contexte
if err != nil {
    return fmt.Errorf("fetching user %s: %w", userID, err)
}
```

### Interdit
```go
// ❌ Ne jamais ignorer une erreur
_ = db.Close()

// ❌ Ne jamais panic hors de main.go
panic("unexpected state")

// ❌ Ne jamais masquer une erreur
if err != nil {
    log.Println(err) // sans retour !
}
```

## Context obligatoire

Toute fonction effectuant un appel réseau, disque ou base de données prend `ctx context.Context` en premier paramètre :

```go
func (r *UserRepo) GetByID(ctx context.Context, id string) (*domain.User, error) {
    row := r.db.QueryRowContext(ctx, "SELECT ...")
    // ...
}
```

## Tests table-driven

Format systématique :

```go
func TestMyFunction(t *testing.T) {
    t.Parallel()

    tests := map[string]struct {
        input    string
        expected int
        wantErr  bool
    }{
        "valid input": {
            input:    "hello",
            expected: 5,
        },
        "empty input returns error": {
            input:   "",
            wantErr: true,
        },
    }

    for name, tt := range tests {
        t.Run(name, func(t *testing.T) {
            t.Parallel()
            // test body
        })
    }
}
```

## Tests d'intégration (Testcontainers)

```go
//go:build integration

func TestWithPostgres(t *testing.T) {
    ctx := context.Background()

    pgContainer, err := postgres.Run(ctx,
        "postgres:16-alpine",
        postgres.WithDatabase("testdb"),
        postgres.WithUsername("test"),
        postgres.WithPassword("test"),
        testcontainers.WithWaitStrategy(
            wait.ForLog("database system is ready").WithOccurrence(2),
        ),
    )
    require.NoError(t, err)
    defer pgContainer.Terminate(ctx)

    connStr, err := pgContainer.ConnectionString(ctx, "sslmode=disable")
    require.NoError(t, err)

    // Use connStr to run tests...
}
```

## Logging

Utiliser exclusivement `log/slog` (bibliothèque standard) :

```go
slog.Info("user created", "user_id", user.ID, "email", user.Email)
slog.Error("failed to create user", "error", err)
```

## Constructeurs

Tout service/handler/repo expose un constructeur `New*` :

```go
func NewUserService(repo ports.UserRepository, logger *slog.Logger) *UserService {
    return &UserService{repo: repo, logger: logger}
}
```
