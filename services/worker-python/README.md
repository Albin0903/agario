# Worker Python — Moteur de Traitement & Calcul Complémentaire

Service Python générique et modulaire pour le template `build`. Il complète le backend Go et le frontend TypeScript en fournissant un accès direct à l'écosystème Python (calculs de design engineering, transformations de données, mathématiques, machine learning et tâches asynchrones complexes).

## Architecture

- `worker_python/models.py` : Contrats de données typés Pydantic (`TaskRequest`, `TaskResponse`, `ColorSpec`, `DatasetSummary`).
- `worker_python/pipeline.py` : Pipeline d'enregistrement et d'exécution dynamique de gestionnaires de tâches (`TaskPipeline`).
- `worker_python/handlers/` :
  - `design.py` : Ratios de contraste WCAG / APCA et génération de palettes 12 niveaux (conventions Radix).
  - `data.py` : Agrégations statistiques, normalisation min-max et filtrage de données.
- `worker_python/cli.py` : Interface CLI / IPC permettant l'invocation directe depuis Go (`os/exec`) ou le terminal via JSON.

## Commandes

- Formater : `uv run ruff format . && uv run ruff check --fix .`
- Linter et typage strict : `uv run ruff check . && uv run mypy worker_python`
- Tests unitaires : `uv run pytest -v`
- Invoquer une tâche :

  ```bash
  uv run python -m worker_python.cli '{"action":"design.contrast","payload":{"foreground":"#0f172a","background":"#ffffff"}}'
  ```
