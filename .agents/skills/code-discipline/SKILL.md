---
name: code-discipline
description: >
  Invariants d'ingenierie logicielle anti-vibe-coding pour agents autonomes : zero emoji,
  commentaires techniques sur le 'pourquoi' uniquement, diffs minimaux, elimination du
  code mort, typage hermetique et verification par Taskfile obligatoire avant toute conclusion.
allowed-tools: Bash, Read, Write
---

# Discipline de Code & Standards Anti-Vibe Coding

Le « vibe coding » (production de code superficiellement plausible mais non verifie, verbeux, fragile et non contraint) est strictement banni de ce repository. Chaque agent operant sur cette base doit appliquer des standards d'ingenierie militaire.

---

## 1. Regle d'Or : Zéro Emoji

Les emojis sont strictement interdits dans :
* Les fichiers sources (Go, TypeScript, Templ, SQL, CSS, JSON, YAML).
* Les commentaires de code.
* Les messages de commit Git.
* Les titres et corps de Pull Requests.
* Les logs de serveurs et sorties consoles (utiliser du texte clair ou des codes d'etat).

```go
// ❌ INTERDIT (Vibe coding)
// 🚀 Initialisation du super serveur web ✨
slog.Info("Serveur demarre avec succes ! 🎉")

// ✅ CONFORME (Ingenierie stricte)
// Configure the HTTP listener on the specified port with graceful shutdown timeouts.
slog.Info("server starting", "port", port, "read_timeout", srv.ReadTimeout)
```

---

## 2. Commentaires de Code : Le « Pourquoi », Jamais le « Quoi »

Un commentaire ne doit jamais paraphraser la syntaxe evidente d'un langage. Les commentaires servent uniquement a documenter :
1. Une decision d'architecture non triviale.
2. Une contrainte metier ou un invariant de securite.
3. Une synchronisation ou gestion d'etat concurrent.
4. Une raison justifiant de ne PAS utiliser une approche plus evidente.

```go
// ❌ INTERDIT (Paraphrase tautologique)
// Declare le statut OK a vrai
status.OK = true

// ❌ INTERDIT
// Boucle sur les utilisateurs pour les afficher
for _, u := range users { ... }

// ✅ CONFORME (Explication causale)
// We cancel the context explicitly prior to os.Exit to ensure that any active
// goroutines waiting on ctx.Done unblock and release OS file handles.
cancel()
```

---

## 3. Diffs Chirurgicaux & Portee Minimale

1. **Règle de scope minimal** : Modifier strictement et uniquement les lignes necessaires a l'accomplissement du besoin.
2. **Interdiction de refactorisation opportuniste** : Ne pas reformater des blocs de code adjacents non concernes par la tache.
3. **Zéro code mort** : Tout code commente (`// func oldFunction() { ... }`) ou fonction non utilisee doit etre supprime immediatement. Git est la memoire du projet, pas le code source.

---

## 4. Typage Hermétique : Pas de Bypasses

1. **Go** : Aucun type `any` ou `interface{}` generique hors de constructeurs de deserialisation JSON standardement encadres par des structs de validation.
2. **TypeScript** : `strict: true` et `noImplicitAny: true` sont non negociables.
   - Ne jamais utiliser le type `any`.
   - Utiliser `unknown` combine avec un predicat de type (type guard) ou une fonction de validation.
   - Ne jamais utiliser de cast aveugle `as User` sans validation structurelle des proprietes.

---

## 5. Boucle de Verification Fermee (Tool-Gated)

Aucune tache ne peut etre consideree comme terminee sur la seule intuition du modele :
1. Chaque modification de code doit etre verifiee par le pipeline local complet :
   ```bash
   NO_COLOR=1 task check
   ```
2. Si la commande echoue (code != 0), l'agent doit lire l'erreur textuelle brute, en deduire la cause racine et appliquer la correction minimale sans modifier d'autres fichiers.

---

## 6. Anti-Satisficing & Dépassement d'Attente ("Exceed Expectations by Default")

Le piège classique de l'agent est la **conformité passive** (*satisficing*) : considérer que le travail est achevé dès lors que les tests unitaires passent et que le code compile, en livrant une coquille vide ou une approximation générique.

1. **Intention vs Syntaxe :** La conformité syntaxique est un prérequis minimal, jamais la ligne d'arrivée. L'agent doit se demander : *« Est-ce que ce produit accomplit fidèlement et avec panache l'intention finale de l'utilisateur ? »*
2. **Démarche d'initiative outillée :** Dès qu'une référence externe est fournie, l'agent prend spontanément l'initiative d'observer la réalité avec ses outils (Chrome DevTools MCP, réseau, code source) avant d'écrire du code.
3. **Qualité sensorielle et kinesthésique :** Aucun composant interactif ne doit être rendu raide ou inerte. L'agent intègre d'emblée la tolérance aux commandes (buffer FIFO), la fluidité (60 FPS) et le retour sonore/visuel.

