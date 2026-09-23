# 01 — Vue d'Ensemble de l'Architecture

Le projet `build` est concu pour servir de fondation universelle, reproductible et deterministe pour l'ensemble des futurs developpements logiciels. Il repond a un objectif central : eliminer les imprecisions, les dependances superflues et les hallucinations d'outillage lors du travail avec des agents d'intelligence artificielle.

---

## 1. Matrice des Couches & Responsabilites

```
+-------------------------------------------------------------------------+
|                              CLIENT                                     |
|   SSR Léger : Templ + HTMX (80%)      |     SPA Riche : React + Vite (20%)|
+---------------------------------------+---------------------------------+
                    |                                        |
                    v                                        v
+-------------------------------------------------------------------------+
|                  ADAPTERS (internal/adapters/)                          |
|   httpserver/ (Routeur stdlib, Handlers, Middlewares, Static SPA Server) |
|   http/views/ (Composants Templ compiles)                               |
|   db/ (Dépôts SQL/PostgreSQL concrets - hors core)                      |
+-------------------------------------------------------------------------+
                                    |
                                    v (implémente)
+-------------------------------------------------------------------------+
|                    PORTS (internal/ports/)                              |
|   Interfaces et contrats de persistance, de notification et d'I/O       |
+-------------------------------------------------------------------------+
                                    ^ (consomme)
                                    |
+-------------------------------------------------------------------------+
|                    CORE (internal/core/)                                |
|   domain/ (Entités pures, objets-valeurs, erreurs sentinelles)          |
|   <services>/ (Cas d'usage, logique métier hermétique)                  |
+-------------------------------------------------------------------------+
```

---

## 2. Invariants d'Isolation

1. **Direction unique des dependances** : `adapters` -> `ports` <- `core`. Le paquet `core` ne depend directement d'aucun adaptateur d'entree ou de sortie.
2. **Ports au consommateur** : Les interfaces Go sont declarees dans le paquet qui les consomme (Go idiomatique), garantissant un couplage minimal.
3. **Typage structurel complet** :
   - Côté Go : aucun `interface{}` non type, aucun `any`.
   - Côté TypeScript : mode `strict: true`, `noImplicitAny: true`, aucun type `any` tolere (utiliser `unknown` avec type guards).
4. **Separation 80/20 du Frontend** :
   - **80% de l'application (SSR Templ + HTMX)** : formulaires, tableaux administratifs, pages statiques avec mises a jour partielles rapides sans runtime JavaScript client lourd.
   - **20% de l'application (SPA Vite + TanStack Router)** : tableaux de bord interactifs complexes, visualisations temps reel, interfaces a forte manipulation d'etat local.

