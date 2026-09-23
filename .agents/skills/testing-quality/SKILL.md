---
name: testing-quality
description: >
  Conception et execution des tests unitaires et d'integration : format table-driven Go,
  isolation par contextes et ports, conteneurisation ephemere Testcontainers-go,
  detection de courses de donnees et typage strict des tests.
allowed-tools: Bash, Read, Write
---

# Standards de Tests & Qualité Logicielle

Les tests constituent la seule preuve formelle du bon fonctionnement du systeme. Les assertions floues, les tests tautologiques et les tests dependants d'un etat global sont proscrits.

---

## 1. Tests Unitaires Go : Format Table-Driven Obligatoire

Tout test unitaire Go doit utiliser une map anonyme de cas de tests et `t.Parallel()` :

```go
func TestHealthService_Check(t *testing.T) {
	t.Parallel()

	tests := map[string]struct {
		setupTime time.Time
		wantOK    bool
	}{
		"active service returns healthy status": {
			setupTime: time.Now(),
			wantOK:    true,
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			svc := health.NewService()
			status := svc.Check()

			if status.OK != tt.wantOK {
				t.Errorf("Check().OK = %v, want %v", status.OK, tt.wantOK)
			}
		})
	}
}
```

### Regles de redaction
1. **Isolation des cas** : `t.Parallel()` a la racine et dans chaque sous-test de la boucle.
2. **Nommage explicite** : Le nom du cas dans la map doit decrire la condition et le resultat attendu sous forme de phrase complete en minuscules (ex: `"invalid payload returns validation error"`).
3. **Assertions sans bibliotheque exotique** : Privilegier la stdlib Go (`if got != want { t.Errorf(...) }`).

---

## 2. Tests d'Integration (Testcontainers-go)

1. **Tag de build obligatoire** : `//go:build integration` sur la premiere ligne du fichier.
2. **Nettoyage garanti** : Toujours executer `defer container.Terminate(ctx)` immediatement apres le demarrage du conteneur.
3. **Strategie d'attente (Wait Strategy)** : Toujours declarer une strategie d'attente explicite sur le port ou le log (`wait.ForLog(...)` ou `wait.ForListeningPort(...)`) avec un timeout borne (ex: 30s) pour eviter les blocages infinis en CI.

---

## 3. Anti-Patterns a Eliminer

- ❌ `time.Sleep()` pour attendre la fin d'une goroutine ou la reponse d'un serveur (utiliser des channels ou `sync.WaitGroup`).
- ❌ Mocker des types concrets au lieu de mocker les interfaces des ports.
- ❌ Ecrire un test qui redefinit la meme formule que la fonction testee (test tautologique).
- ❌ Ignorer les erreurs retournees dans les helpers de test (utiliser `t.Fatalf` immediatement).

