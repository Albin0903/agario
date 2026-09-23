## Description du changement
<!-- Resume technique precis des modifications apportees et de l'approche retenue -->

Fixes #<!-- numero de l'issue, ex: Fixes #42 -->

## Perimetres monorepo affectes
- [ ] `internal/core` (Logique metier pure, domaines, sentinelles)
- [ ] `internal/adapters/httpserver` (Handlers HTTP, routeur, middlewares)
- [ ] `internal/adapters/http/views` (Templates Templ & fragments HTMX)
- [ ] `web-app` (SPA React 19 / TypeScript strict / Vite / Biome)
- [ ] `Taskfile.yml` / `build/Dockerfile` / GitHub Actions
- [ ] Documentation / `.agents/skills`

## Type de modification
- [ ] `feat`: Nouvelle fonctionnalite
- [ ] `fix`: Correction d'anomalie
- [ ] `refactor`: Remaniement sans changement de comportement
- [ ] `perf`: Optimisation de performance mesuree
- [ ] `test`: Ajout ou enrichissement de tests
- [ ] `chore`: Maintenance, outillage, Taskfile

## Checklist Qualite & Anti-Vibe Coding (Obligatoire avant merge)
- [ ] `NO_COLOR=1 task check` execute avec succes en local (exit code 0)
- [ ] Tests unitaires table-driven ajoutes ou mis a jour
- [ ] Zéro type `any` ou `interface{}` non contraint introduit
- [ ] Zéro emoji present dans le code, les commentaires, ou les messages de commit
- [ ] Commentaires strictement limites au « pourquoi » (aucune paraphrase de syntaxe)
- [ ] Titre de la PR et commits conformes a la norme Conventional Commits

