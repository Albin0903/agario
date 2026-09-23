# AGAR-RL: Autonomous Multi-Agent Deep Reinforcement Learning Pipeline

Système de simulation headless haute performance (> 10 000 FPS) et d'entraînement par Deep Reinforcement Learning (PPO / Self-Play) pour générer des agents autonomes sur un environnement inspiré d'Agar.io, avec déploiement via WebSocket sur serveur Ogar local.

---

## 1. Vue d'ensemble du système

Le projet est divisé en trois briques logicielles modulaires et indépendantes :
1. **Core Engine (`src/env`)** : Simulateur 2D vectorisé pur Python/NumPy, conforme à l'interface standard **Farama Gymnasium**, sans dépendance graphique (mode headless, > 10 000 FPS sur CPU standard via spatial hashing).
2. **Training Pipeline (`src/training`)** : Orchestration de Deep Reinforcement Learning sous **Stable-Baselines3** (PPO multi-instances via `SubprocVecEnv` ou `DummyVecEnv` et protocole de self-play avec pool d'adversaires historiques et heuristiques). Conçu pour tourner sur GPU via Google Colab ou sur machine locale.
3. **Bridge & Inférence (`src/inference`)** : Exportation optimisée vers **ONNX** (latence CPU < 0.02 ms) et client d'inférence WebSocket temps réel traduisant les paquets binaires d'un serveur privé Ogar (Node.js) pour affronter des joueurs humains.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             AGAR-RL ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   [Core Engine: src/env]                                                    │
│   ├── AgarEngine (Vectorized NumPy 2D physics + SpatialHashGrid > 10k FPS)  │
│   ├── Entities (Cell, Pellet, Virus, EjectedMass)                           │
│   └── AgarEnv (Farama Gymnasium, Obs: 84 floats, Action: Box(3,))           │
│                                │                                            │
│                                ▼                                            │
│   [Training Pipeline: src/training]                                         │
│   ├── train_colab.py (PPO orchestrator, SubprocVecEnv, Colab GPU/CPU)       │
│   ├── SelfPlayPool (Generation tracking, adversary policy sampling)        │
│   └── SelfPlayCallback (Periodic checkpointing & adversary pool update)     │
│                                │                                            │
│                                ▼                                            │
│   [Bridge & Inference: src/inference]                                       │
│   ├── export_onnx.py (Static (1, 84) -> (1, 3) policy, latency < 0.02 ms)   │
│   └── bot_client.py (Real-time Ogar WebSocket client, binary protocol)       │
│                                │                                            │
│                                ▼                                            │
│   [Private Ogar Server (ws://127.0.0.1:443) & Web Client]                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Spécifications techniques du moteur (`agar_env`)

### 2.1. Physique et mécaniques
* **Arène** : Rectangle fermé de dimensions fixes $W \times H = 2\,000 \times 2\,000$.
* **Relation Masse-Rayon** :
  $$r = \sqrt{m} \times 3$$
* **Relation Vitesse-Masse** :
  $$v = \max\left(0.5,\, v_{base} \times m^{-0.2}\right) \quad \text{avec } v_{base} = 2.0$$
* **Consommation / Fusion** :
  * Une cellule $A$ absorbe une cellule $B$ si $\text{dist}(A, B) < r_A$ et $m_A \ge 1.1 \times m_B$.
  * Lors d'une ingestion, $m_A \leftarrow m_A + m_B$ (conservation stricte de masse).
* **Nourriture statique (Pellets)** :
  * $N = 500$ points fixes distribués aléatoirement, masse unitaire $m = 1$.
  * Respawn instantané après consommation avec mise à jour incrémentale de la grille spatiale.
* **Virus (Obstacles)** :
  * 10 virus de masse $m = 100$, rayon fixe $r = 30$.
  * Si une cellule de masse $m > 130$ entre en collision, elle explose en fragments (capacité max : 16 sous-cellules).
* **Actions spéciales** :
  * **Split (Touche Espace / Action > 0.33)** : La cellule se divise en deux parts égales le long du vecteur vitesse actuel. La moitié projetée reçoit un boost d'accélération temporaire.
  * **Eject Mass (Touche W / Action [-0.33, 0.33])** : Éjection d'un fragment de masse $m = 12$ vers le curseur, coût pour la cellule : $m_{perte} = 16$.

### 2.2. Espace d'observation (Vectorisé, egocentrique)
Chaque observation est normalisée dans $[-1, 1]$ par rapport à la position $(x_c, y_c)$ et au rayon $r_c$ du centroïde de l'agent.

Le vecteur plat de taille $D = 84$ comprend :
1. **État propre (4 floats)** :
   * Masse normalisée : $\tanh(m / 500)$
   * Vitesse actuelle : $(v_x, v_y) / v_{max}$
   * Nombre de sous-cellules : $k / 16$
2. **Entités locales (K plus proches, coordonnées relatives polarisées)** :
   * **10 Pellets les plus proches** ($10 \times 2 = 20$ floats) : $(\Delta x / R_{vue}, \Delta y / R_{vue})$
   * **5 Cellules Proies ($m_{autre} < 0.9 \times m$)** ($5 \times 4 = 20$ floats) : $(\Delta x / R_{vue}, \Delta y / R_{vue}, \tanh(\Delta m / 100), v_{rel} / v_{max})$
   * **5 Cellules Prédateurs ($m_{autre} > 1.1 \times m$)** ($5 \times 4 = 20$ floats) : $(\Delta x / R_{vue}, \Delta y / R_{vue}, \tanh(\Delta m / 100), v_{rel} / v_{max})$
   * **4 Virus les plus proches** ($4 \times 3 = 12$ floats) : $(\Delta x / R_{vue}, \Delta y / R_{vue}, \text{collision\_imminente\_bool})$
   * **Distances aux 4 murs de bordure** ($4$ floats) : $(d_{haut}, d_{bas}, d_{gauche}, d_{droite}) / R_{vue}$
   * **Propriétés globales de l'arène** ($4$ floats) : $(x_c / W, y_c / H, r_c / R_{vue}, \text{cooldown} / 300)$

*Rayon de vue dynamique : $R_{vue} = 500 + 2 \times r_c$. Si moins d'entités sont visibles, le vecteur est paddé avec des zéros.*

### 2.3. Espace d'action
Espace continuous normalisé `gymnasium.spaces.Box(low=-1.0, high=1.0, shape=(3,))` :
* `action[0]` : Direction continue $t_x \in [-1, 1]$
* `action[1]` : Direction continue $t_y \in [-1, 1]$
* `action[2]` : Déclencheur discret :
  * $< -0.33$ : Pas d'action spéciale (déplacement simple)
  * $[-0.33, 0.33]$ : Eject Mass
  * $> 0.33$ : Split

### 2.4. Fonction de Récompense (Reward Shaping)
À chaque pas de temps $t$ :
$$R_t = R_{masse} + R_{chasse} + R_{survie} - R_{pénalité}$$

* **Gain de masse relatif** : $R_{masse} = \frac{\sqrt{m_t} - \sqrt{m_{t-1}}}{\sqrt{m_{init}}}$
* **Consommation d'adversaires** : $+5.0$ par cellule adverse absorbée.
* **Mort** : $-10.0$ si absorbé par un prédateur.
* **Pénalité de split inefficace** : $-0.5$ si un split est exécuté sans consommer d'adversaire dans les 30 pas de temps suivants.
* **Survie passive** : $+0.001$ par pas de temps pour valoriser la survie continue.

---

## 3. Installation et Démarrage Rapide

### Prérequis
* Python 3.10, 3.11 ou 3.12
* `uv` (recommandé) ou `pip`

### Installation
```bash
# Cloner le dépôt
git clone <repo_url>
cd agar-ai

# Créer un environnement virtuel et installer les dépendances
uv venv --python 3.11 .venv
source .venv/bin/activate  # Sous Windows: .venv\Scripts\activate
uv pip install -r requirements.txt pygame
```

---

## 4. Tester et Jouer Immédiatement en Mode Visuel 🎮

Vous pouvez tester l'environnement en direct avec rendu visuel 60 FPS, caméra fluide et leaderboard en affrontant des bots ou l'IA entraînée :

```bash
# Lancer le jeu interactif (Souris = Direction, Espace = Split, W = Ejecter masse, R = Respawn)
python play_human.py --model models/model.onnx --bots 10
```

---

## 5. Entraînement PPO & Self-Play (`src/training/`)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Albin0903/agario/blob/main/notebooks/train_colab.ipynb)

Vous pouvez lancer l'entraînement directement sur **Google Colab** via le notebook [`notebooks/train_colab.ipynb`](notebooks/train_colab.ipynb) en un clic avec accélération GPU, ou en local :

```bash
# Entraînement multi-environnements distribué (16 instances en parallèle)
python src/training/train_colab.py --n-envs 16 --total-timesteps 10000000

# Entraînement local de test rapide
python src/training/train_colab.py --n-envs 4 --total-timesteps 50000 --use-dummy-vec
```

### Mécanisme de Self-Play
* Chaque arène contient 1 agent apprenant et 10 bots adverses.
* Les bots sont initialement pilotés par des heuristiques de survie et de chasse.
* Tous les 500 000 pas (`--pool-interval`), le checkpoint courant est évalué et ajouté au `SelfPlayPool`, remplaçant les modèles les plus faibles.
* Les environnements échantillonnent dynamiquement les adversaires entre les heuristiques et les générations passées.

---

## 5. Exportation vers ONNX (`src/inference/export_onnx.py`)

Convertit le checkpoint PyTorch/SB3 en graphe statique ONNX ultra-optimisé avec signature d'entrée `(1, 84)` et sortie `(1, 3)` :

```bash
python src/inference/export_onnx.py --model checkpoints/ppo/ppo_final.zip --output models/model.onnx
```

### Métriques de performance mesurées sur CPU :
* **Latence moyenne d'inférence** : **0.015 ms** (seuil exigé : < 2.0 ms)
* **Débit d'inférence** : > 65 000 inférences / seconde sur un seul cœur CPU
* **Écart maximal PyTorch vs ONNX** : $< 10^{-7}$

---

## 6. Déploiement et Test Réel sur Serveur Ogar Local

### Étape 1 : Lancement du serveur Ogar
```bash
git clone https://github.com/Crews/Ogar.git
cd Ogar
npm install
node index.js
```
Le serveur écoute par défaut sur `ws://127.0.0.1:443`.

### Étape 2 : Lancement du Bot ONNX
```bash
python src/inference/bot_client.py --model models/model.onnx --server ws://127.0.0.1:443 --name "AGAR-RL-Bot"
```

Le bot :
1. Établit la connexion WebSocket et envoie les paquets de handshake (254, 255) et de spawn (0).
2. Parse en continu les paquets binaires mondiaux (paquet 16).
3. Reconstruit le vecteur d'observation normalisé 84-D à chaque tick.
4. Exécute l'inférence via `onnxruntime` en 0.015 ms.
5. Émet les paquets de déplacement (16), de split (17) et d'éjection (21).

### Test en mode simulé (sans serveur Node.js externe) :
```bash
python src/inference/bot_client.py --model models/model.onnx --test-mock
```

---

## 7. Suite de Tests et Validation

L'ensemble des mécaniques physiques, de conformité Farama Gymnasium, de self-play et d'export ONNX est couvert par 20 tests unitaires :

```bash
pytest -v
```

### Résultats de validation :
```text
tests/test_bot_client.py::test_packet_builders PASSED                    [  5%]
tests/test_bot_client.py::test_packet_parsing_and_observation PASSED     [ 10%]
tests/test_engine_physics.py::test_mass_radius_formula PASSED            [ 15%]
tests/test_engine_physics.py::test_mass_speed_formula PASSED             [ 20%]
tests/test_engine_physics.py::test_pellet_consumption_and_mass_conservation PASSED [ 25%]
tests/test_engine_physics.py::test_cell_predation_mass_conservation PASSED [ 30%]
tests/test_engine_physics.py::test_predation_requires_eat_ratio PASSED   [ 35%]
tests/test_engine_physics.py::test_virus_explosion PASSED                [ 40%]
tests/test_engine_physics.py::test_split_action PASSED                   [ 45%]
tests/test_engine_physics.py::test_eject_mass_action PASSED              [ 50%]
tests/test_engine_physics.py::test_subcells_remerge PASSED               [ 55%]
tests/test_engine_physics.py::test_simulation_speed_benchmark PASSED     [ 60%]
tests/test_export_and_onnx.py::test_onnx_export_and_benchmark PASSED     [ 65%]
tests/test_gym_compliance.py::test_farama_check_env PASSED               [ 70%]
tests/test_gym_compliance.py::test_observation_space_bounds PASSED       [ 75%]
tests/test_gym_compliance.py::test_reward_mechanisms PASSED              [ 80%]
tests/test_gym_compliance.py::test_seed_reproducibility PASSED           [ 85%]
tests/test_self_play.py::test_heuristic_bot_behavior PASSED              [ 90%]
tests/test_self_play.py::test_self_play_pool_lifecycle PASSED            [ 95%]
tests/test_self_play.py::test_environment_multiagent_interaction PASSED  [100%]

======================= 20 passed in 4.97s =======================
```

---

## 8. Structure du Repository

```text
agar-ai/
├── README.md                    # Documentation complète
├── requirements.txt             # Dépendances du projet
├── pytest.ini                   # Configuration de test
├── config/
│   ├── env_config.yaml          # Paramètres physiques et d'arène
│   └── ppo_config.yaml          # Hyperparamètres PPO et Self-Play
├── src/
│   ├── env/
│   │   ├── __init__.py
│   │   ├── agar_engine.py       # Moteur physique vectorisé pur NumPy (> 11 000 FPS)
│   │   ├── entities.py          # Objets Cell, Pellet, Virus, EjectedMass
│   │   └── gym_wrapper.py       # Wrapper Farama Gymnasium standard (obs 84-D)
│   ├── training/
│   │   ├── __init__.py
│   │   ├── callbacks.py         # Checkpointing, métriques et mises à jour self-play
│   │   ├── self_play_pool.py    # Pool de modèles adverses passés et heuristiques
│   │   └── train_colab.py       # Script d'entraînement PPO multi-instances
│   └── inference/
│       ├── __init__.py
│       ├── export_onnx.py       # Export PyTorch/SB3 vers format universel ONNX
│       └── bot_client.py        # Client WebSocket connecté à Ogar (protocole binaire)
└── tests/
    ├── test_engine_physics.py   # Validation des collisions et conservation de masse
    ├── test_gym_compliance.py   # Test Farama check_env et bornes d'observation
    ├── test_self_play.py        # Tests du pool self-play et des interactions bots
    ├── test_export_and_onnx.py  # Validation ONNX et latence (< 2 ms)
    └── test_bot_client.py       # Validation du protocole binaire Ogar
```

