---
name: arch-boundaries
description: >
  Applique les règles de découplage hexagonal et vérifie les frontières entre couches.
  Utiliser dès qu'une tâche touche aux interfaces Go, aux ports, aux adaptateurs,
  ou au découpage des paquets.
allowed-tools: Bash, Read, Write
---

# Architecture Hexagonale — Règles de Découplage

## Structure des couches

```
internal/
├── core/          # Logique métier pure (domain + services)
│   ├── domain/    # Entités, value objects, erreurs sentinelles
│   └── <service>/ # Services métier (health, user, etc.)
├── ports/         # Interfaces (contrats) consommées par le core
└── adapters/      # Implémentations concrètes
    ├── httpserver/ # HTTP handlers + middleware
    ├── db/        # Repositories SQL/NoSQL
    └── external/  # Clients API tierces
```

## Règles invariantes

1. **Sens unique des dépendances** : `adapters → ports ← core`. Le `core` ne doit **jamais** importer un paquet `adapters`.
2. **Interfaces dans le paquet consommateur** : Les interfaces sont déclarées dans le même paquet que le code qui les utilise (Go idiomatique).
3. **Pas d'import de drivers dans le core** : `database/sql`, `pgx`, `redis` et tout driver externe sont cantonnés aux `adapters`.
4. **DTOs à la frontière** : Les structures de requête/réponse HTTP sont définies dans `adapters/httpserver/`, **jamais** dans `core/domain/`.
5. **Injection par constructeur** : Chaque adaptateur reçoit ses dépendances via son constructeur (`NewXxx(deps ...)`), pas via des variables globales.

## Vérification

Avant de valider une modification :

```bash
# Vérifier qu'aucun import interdit n'existe dans le core
grep -rn '/internal/adapters' internal/core/ && echo "ERREUR: import interdit" || echo "OK"
```

## Anti-patterns à rejeter

- ❌ `core/domain/user.go` qui importe `"database/sql"`
- ❌ `core/service.go` qui instancie directement un `pgx.Pool`
- ❌ Interface déclarée dans `adapters/` et importée par `core/`
- ❌ Type `any` ou `interface{}` sans contrainte dans une signature publique
