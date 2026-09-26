# AGAR-RL

Environnement multi-agent inspiré d’Agar.io, moteur physique Python/Numba, apprentissage MaskablePPO et outils d’évaluation/replay.

## Entraînement V11 sur Colab

Ouvre [`notebooks/train_colab.ipynb`](notebooks/train_colab.ipynb) avec un runtime GPU L4 ou A100. Le notebook :

1. profile le moteur et un environnement complet sur le runtime actif ;
2. mesure plusieurs profils PPO sur ce GPU et choisit le débit réel le plus élevé ;
3. initialise V11 avec les **poids de politique** du checkpoint V10 ayant le compteur interne le plus élevé ;
4. entraîne jusqu’à 20 millions de pas V11 et sauvegarde les checkpoints dans `MyDrive/agario_rl_backup_v11`.

Le transfert V10→V11 ne reprend ni compteur, ni optimiseur, ni normalisation, ni pool. Une reprise interrompue restaure ces états depuis le checkpoint V11 et continue avec le profil d’environnements enregistré dans son manifeste. Pour arrêter proprement, interromps la cellule d’entraînement : le signal est transmis au processus qui sauvegarde puis synchronise Drive.

CLI équivalente :

```bash
# Nouvelle V11 depuis les poids V10
python -m src.training.train_v11 --v10-checkpoint /path/to/v10_checkpoint.zip \
  --n-envs 8 --batch-size 1024 --n-epochs 8 --total-timesteps 20000000

# Reprise V11 depuis son dossier local
python -m src.training.train_v11 --resume-v11 auto --save-dir checkpoints/v11 \
  --history-dir checkpoints/v11/self_play_pool --n-envs 8
```

Le notebook Colab profile automatiquement le choix CPU/CUDA, `n_envs` et `batch_size`; à la reprise il réutilise le profil du manifeste. Le moteur Numba et les workers d’environnement tournent sur CPU, avec un thread de calcul par worker; le notebook mesure si les mises à jour PPO sont plus rapides sur CPU ou sur le GPU actif.

## Évaluation et replay

[`notebooks/eval_drive_models.ipynb`](notebooks/eval_drive_models.ipynb) compare les checkpoints V11 sur les mêmes graines, puis enregistre un replay du dernier modèle. L’évaluation écrit les résultats partiels dans le dossier Drive V11 et peut reprendre après interruption.

Pendant l’entraînement, `metrics.jsonl` reçoit des fenêtres de comportement tous les 100k pas. À chaque million, `scenario_evaluations.jsonl` reçoit cinq graines fixes pour chacun des cas standard, demi-densité de pellets et 150% du nombre de bots. Le taux de split utile attribue un kill au split le plus récent dans les 30 décisions précédentes; c’est une mesure de diagnostic, pas une preuve causale.

```bash
python -m src.analysis.evaluate_v11 --checkpoint-dir checkpoints/v11 \
  --episodes 5 --output-csv evaluation.csv --output-json evaluation.json

python src/inference/record_match.py --model checkpoints/v11/ppo_latest.zip \
  --output recordings/latest.mp4 --steps 2400 --deterministic
```

Pour inspecter une politique :

```bash
python src/analysis/inspect_policy.py --model checkpoints/v11/ppo_latest.zip
```

## Moteur et récompense

Le moteur maintient une grille compacte des pellets et compile les étapes chaudes avec Numba. Les profils `src.analysis.profile_engine` et `src.analysis.profile_env` mesurent respectivement la physique seule et un pas complet avec bots et observation. Les nombres CPU ne prédisent pas le débit PPO sur GPU.

La récompense favorise le delta de masse signé, l’amélioration du record de masse et applique une pénalité bornée à la mort. Le document [`docs/V11_DESIGN.md`](docs/V11_DESIGN.md) décrit les choix, les approximations physiques et les évaluations recommandées ; les constantes de l’engine sont des paramètres de simulation, pas des valeurs officielles revendiquées par Miniclip.

## Développement

Python 3.10–3.12 recommandé. Installer `requirements.txt`, puis lancer les tests :

```bash
python -m pytest
```

Les scripts d’entraînement actifs sont dans `src/training/train_v11.py`; la politique partagée avec l’archive V10 est définie dans `src/training/policy_arch.py` pour permettre le warm start vérifié.
