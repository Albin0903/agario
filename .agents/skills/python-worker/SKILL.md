---
name: python-worker
description: >
  Guide de developpement pour le moteur de traitement et de calcul Python (services/worker-python/).
  Utiliser des qu'une tache necessite des algorithmes scientifiques, du calcul de design engineering,
  des transformations de donnees, ou de l'orchestration IA/ML avec uv, ruff, mypy et pytest.
allowed-tools: Bash, Read, Write
---

# Moteur de Traitement & Calcul Python (`services/worker-python/`)

Ce service fournit un acces direct a l'ecosysteme Python pour les calculs que Go ou TypeScript ne peuvent realiser simplement (design engineering, statistiques, machine learning, transformations d'actifs).

---

## 1. Outillage & Gestion de Paquets (`uv`)

Le projet utilise exclusivement **`uv`**. Les commandes `pip` globales ou ad-hoc sont formellement proscrites.

```bash
# Executer les tests unitaires
uv run pytest -v

# Formater le code source
uv run ruff format . && uv run ruff check --fix .

# Linter et verifier les types en mode strict
uv run ruff check . && uv run mypy worker_python --strict
```

---

## 2. Architecture du Moteur (`worker_python/`)

```
services/worker-python/
├── worker_python/
│   ├── models.py             # Modeles Pydantic immuables et valides (TaskRequest, TaskResponse)
│   ├── pipeline.py           # Pipeline asynchrone avec registre dynamique (TaskPipeline)
│   ├── cli.py                # Interface CLI / IPC recevant du JSON et retournant du JSON
│   └── handlers/             # Gestionnaires d'actions specialises
│       ├── design.py         # Contrastes WCAG / APCA et palettes 12 niveaux Radix
│       └── data.py           # Agregations statistiques, normalisation et filtrage
└── tests/                    # Tests unitaires pytest (100% isoles sans dependances externes)
```

---

## 3. Ajouter une Nouvelle Action

Pour etendre les capacites du moteur :

1. **Creer ou enrichir un gestionnaire dans `worker_python/handlers/` :**

```python
from worker_python.models import TaskRequest, TaskResponse

def mon_handler(request: TaskRequest) -> TaskResponse:
    # 1. Valider le payload
    valeur = request.payload.get("valeur")
    if not valeur:
        raise ValueError("Parametre 'valeur' obligatoire")

    # 2. Executer le traitement
    resultat = {"calcule": valeur * 2}

    # 3. Retourner la reponse
    return TaskResponse(success=True, data=resultat)
```

2. **Enregistrer l'action dans le pipeline (`worker_python/pipeline.py`) :**

```python
pipeline.register("mon_domaine.mon_action", mon_handler)
```

3. **Ajouter le test unitaire correspondant dans `tests/` :**

```python
def test_mon_action_succes() -> None:
    request = TaskRequest(action="mon_domaine.mon_action", payload={"valeur": 21})
    response = pipeline.execute(request)
    assert response.success is True
    assert response.data["calcule"] == 42
```

---

## 4. Invariants de Qualite

1. **Typage strict (`mypy --strict`) :** Aucun type non annote, aucun `Any` non justifie.
2. **Zero appel reseau en test :** Mocker toute requete externe avec `httpx.MockTransport` ou des fixtures locales.
3. **Zero emoji :** Conformite absolue avec la regle 5 d'`AGENTS.md`.
4. **Validation par Taskfile :** Verifier systematiquement avec `task test:unit` et `task lint`.

