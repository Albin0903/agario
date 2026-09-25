# AGAR-RL V10 - Specification technique Deep RL

> Document de reference pour l'implementation, l'entrainement et l'evaluation de la V10.
> Les valeurs marquees **cible** sont des exigences de conception a verifier dans le code et les experiences; elles ne constituent pas automatiquement une preuve de performance.

## 1. Objectif et contexte

Agar.io combine commande partiellement observable, physique dependante de la masse, adversaires competitifs et distribution d'etats non stationnaire. Une politique qui apprend uniquement contre sa derniere version peut entrer dans un cycle strategique: elle bat l'adversaire recent, oublie les anciennes tactiques, puis reapprend a les contrer.

La V10 vise une politique solo robuste en self-play, sur un horizon cible de 15 a 20 millions de pas, avec:

- observation vectorielle egocentrique compacte et calibree;
- action `MultiDiscrete([24, 3])` et masquage strict des actions invalides;
- tronc et tetes actor-critic normalises;
- reward fonde sur le delta de masse, les eliminations et la mort, sans micro-penalites comportementales;
- pool d'adversaires historiques, bots heuristiques et clones courants;
- moteur physique vectorise et compatible avec les mecaniques Agar.io;
- reprise fiable sur Colab et Google Drive.

## 2. Positionnement scientifique

| Propriete | AgarCL | GoBigger | AGAR-RL V10 |
| --- | --- | --- | --- |
| Objectif | Continual RL et plasticite | MARL cooperatif/competitif | Survie et domination solo |
| Temps | Flux continu non episodique | Episodes bornes | Episodes tronques, `T_max=3500` cible |
| Observation | Pixels ou symbolique | Grille et entites | Vecteur egocentrique, 84 dimensions cible |
| Action | Hybride continue/discrete | Continue ou parametree | `MultiDiscrete([24, 3])`, masque strict |
| Reseau | CNN/GRU | CNN-MLP multi-tetes | MLP LayerNorm/RMSNorm |
| Simulation | Environ 1200 FPS/noeud | Environ 800-1500 FPS | Moteur accelere Numba/C++, objectif eleve |

La litterature signale un risque de policy collapse apres une longue phase d'apprentissage. La V10 doit donc suivre la plasticite, la stabilite PPO, la diversite du self-play et les metriques comportementales plutot que le reward seul.

## 3. Contrat de reward

Le reward V10 reste minimal et lie uniquement a la progression physique reelle:

$$
R_t = w_{mass}\frac{\Delta M_t}{M_0}
  + w_{peak}\frac{\max(0, PeakM_t-PeakM_{t-1})}{M_0}
  - \min\left(C_{death},\frac{PeakM_t}{M_0}\right)I_{death}
$$

Parametres de reference:

- `M0 = 20.0` a la reapparition;
- `Delta M = M_t - M_(t-1)`, incluant ingestion et perte metabolique;
- un kill est recompense naturellement par `Delta M`, sans bonus kill separe;
- `Cdeath = 10.0` dans l'espace de masse normalise;
- aucune penalite continue de bord, de virage, de proximite d'un predateur ou de split gaspille ne doit etre ajoutee sans experience ablationnee;
- les tentatives de split illegal sont gerees par le masque d'action, pas par une penalite reward.

### Extension V10: objectif peak mass

La V10 conserve le signal de croissance sous le record et ajoute un bonus quand un nouveau record est atteint:

$$
R_{peak,t}=w_{peak}\frac{\max(0, PeakM_t-PeakM_{t-1})}{M_0}
$$

Le delta de masse positif reste donc recompense meme si la masse courante reste sous `PeakM`; un delta negatif punit toute perte de masse. Un split legal n'est pas recompense en lui-meme: il est avantageux s'il produit une croissance nette, avec un bonus supplementaire lorsqu'il depasse le record.

**Source code a controler:** `src/env/gym_wrapper.py` et `config/env_config.yaml`.

## 4. Espace d'observation et politique

L'observation cible de 84 dimensions doit conserver une calibration analytique dans `[-1, 1]` et contenir, selon le schema du moteur:

- etat propre, masse/rayon et vitesse normalises;
- directions des 10 nourritures les plus proches;
- positions, vitesses relatives et ratios de masse logarithmiques de 5 proies et 5 predateurs;
- menace et distance des 4 virus les plus proches;
- distances aux 4 bordures;
- position globale normalisee et nombre de fragments/fusion.

Architecture cible:

```text
observation[84]
  -> Linear(84, 512) -> LayerNorm(512) -> SiLU
  -> actor head: Linear(512, 512) -> LayerNorm(512) -> MultiDiscrete([24, 3])
  -> critic head: Linear(512, 512) -> LayerNorm(512) -> scalar value
```

RMSNorm peut remplacer LayerNorm si une experience comparative confirme un gain sans degradation de stabilite. Le tronc partage doit etre separe des tetes actor et critic apres l'extraction des features.

L'initialisation par behavioral cloning est ciblee sur 25 000 transitions heuristiques. Elle doit etre comparee a un demarrage aleatoire et ne doit pas modifier la formulation reward.

**Source code:** `src/training/policy_arch.py`, `src/training/pretrain_bc.py`.

## 5. Masquage strict des actions

Le split est valide uniquement si:

```text
mass >= 36.0 and number_of_cells < 16
```

Le masque doit etre expose par l'environnement et consomme par `MaskablePPO`. Conceptuellement, pour chaque logit `z_i`:

$$
z'_i = z_i \quad si\ a_i\in A_{valid}(s),
\qquad z'_i=-\infty \quad sinon
$$

Le masque doit etre applique avant l'echantillonnage et lors de l'evaluation de la log-probabilite. Les adversaires du pool doivent egalement recevoir leur masque. Les tests doivent verifier:

- masse inferieure a 36: split impossible;
- 16 cellules: split impossible;
- etat valide: split conserve;
- aucune action masquee n'est emise sur une longue trajectoire;
- le masque ne change pas le reward d'un etat valide.

**Source code:** `src/env/gym_wrapper.py`, `src/training/train_colab.py` et `sb3-contrib`.

## 6. Self-play: ligue et PFSP

La ligue V10 doit eviter le self-play contre le dernier checkpoint uniquement. Pour un adversaire historique `P_i`, utiliser une probabilite proportionnelle a la difficulte:

$$
P(P_i)=\frac{f(1-v(A,P_i))}
{\sum_j f(1-v(A,P_j))},
\qquad f(x)=x^p,\ p\in[1,2]
$$

Distribution cible des adversaires:

| Source | Part cible | Role |
| --- | ---: | --- |
| Checkpoints historiques PFSP | 50% | Couvrir les faiblesses connues |
| Bots heuristiques deterministes | 30% | Garantir les competences socles |
| Clones de la politique courante | 20% | Suivre la frontiere recente |

Le pool doit stocker le checkpoint, son score, son taux de victoire contre la politique active, sa date/etape et son origine. Les checkpoints doivent rester geles pendant une evaluation. Le sampling doit etre reproductible avec une seed.

La politique active doit etre evaluee contre:

- les historiques faciles, moyens et difficiles;
- les bots d'esquive de virus et de fuite des predateurs;
- les clones recents;
- au moins une distribution holdout jamais utilisee pour l'optimisation.

**Etat actuel a documenter:** le depot possede `SelfPlayPool` et un ratio heuristique configurable. L'implementation PFSP complete et la distribution 50/30/20 doivent etre verifiees avant d'etre annoncees comme garanties.

**Source code:** `src/training/self_play_pool.py`, `src/training/callbacks.py`, `config/ppo_config.yaml`.

## 7. Normalisation et stabilite d'apprentissage

La normalisation des retours doit etre activee sans modifier la semantique spatiale des observations:

```python
VecNormalize(
    vec_env,
    norm_obs=False,
    norm_reward=True,
    clip_reward=10.0,
    gamma=0.99,
)
```

Les statistiques `VecNormalize` doivent etre sauvegardees et restaurees avec le checkpoint. Toute experience doit journaliser:

- norme des poids et fraction d'unites dormantes;
- norme des representations latentes ou un proxy de leur rang;
- `approx_kl`, `clip_fraction`, `entropy_loss`;
- `policy_loss`, `value_loss`, `explained_variance`;
- reward moyen et reward par composante si disponible.

Seuils de surveillance:

| Metrique | Zone cible | Alerte |
| --- | --- | --- |
| `approx_kl` | `<= 0.02` | `>= 0.05` |
| `clip_fraction` | `0.05-0.20` | hors zone durable |
| `explained_variance` | `> 0.60` | negative ou instable |
| Entropie | decroissance progressive | chute abrupte |

Une alerte ne doit pas declencher silencieusement une modification du reward. Elle doit provoquer une inspection de rollout, de masque, de normalisation et de composition du pool.

## 8. Hyperparametres V10

| Hyperparametre | Valeur de reference |
| --- | ---: |
| Algorithme | `MaskablePPO` |
| Environnements | 16-24 |
| `n_steps` | 2048 |
| `batch_size` | 1024 (2048 pour A100 si memoire suffisante) |
| `n_epochs` | 8-10 |
| `gamma` | 0.99 |
| `gae_lambda` | 0.95 |
| Learning rate initial | `3e-4` |
| Learning rate final | `1e-5` |
| Entropie initiale | `0.005` |
| Entropie finale cible | `0.001` |
| `max_grad_norm` | 0.5 |
| `action_repeat` | 3 sous-ticks physiques |
| Horizon total cible | 15M-20M pas |

Le learning rate doit suivre une cosine annealing monotone de `3e-4` vers `1e-5`, en fonction de l'avancement global et non du nombre de reprises Colab. La fraction de progression doit etre restauree avec le checkpoint ou reconstruite a partir de `num_timesteps`.

## 9. Moteur physique et debit

Le moteur doit conserver les invariants suivants:

- grille spatiale uniforme de cellule `100 x 100` pour filtrer les collisions;
- boucles critiques compilees Numba avec buffers `float32` reutilisables;
- amortissement des orbites sous 32 unites de distance;
- attraction magnetique apres expiration du cooldown de fusion;
- cellule de masse `<=130` glissant sous un virus;
- cellule de masse `>130` eclatant jusqu'a 16 fragments;
- cellule deja a 16 fragments absorbant le virus sans fragmentation supplementaire;
- trois sous-ticks physiques par macro-action.

Le debit reel doit etre mesure sur la machine courante. Les chiffres de recherche suivants sont des ordres de grandeur, pas des garanties:

| GPU | Environnements | Batch | Temps cible pour 15M pas |
| --- | ---: | ---: | ---: |
| L4 24 Go | 16-20 | 1024 | 30-45 min |
| A100 40 Go | 24 | 2048 | 18-28 min |
| T4 16 Go | 8-12 | 512 | 1.5-2.2 h |

Les adversaires du pool doivent tourner sur CPU afin de reserver le GPU a la politique active. `SubprocVecEnv` est preferable sous Linux/Colab; `DummyVecEnv` reste le fallback local ou Windows.

**Source code:** `src/env/agar_engine.py`, `src/env/physics_fast.py`, `src/env/gym_wrapper.py`.

## 10. Colab, sauvegarde et reprise

Le workflow V10 utilise un stockage local intermediaire puis une copie vers:

```text
/content/drive/MyDrive/agario_rl_backup_v10
```

Chaque sauvegarde doit inclure:

- checkpoint PPO `*.zip`;
- statistiques `vec_normalize.pkl`;
- configuration YAML utilisee;
- metriques et logs TensorBoard;
- version du code et seed;
- export ONNX periodique.

La procedure de reprise doit:

1. filtrer les archives valides par taille et nom;
2. choisir le checkpoint le plus avance de V10, puis V9, V8, V7, V6 ou V5;
3. restaurer l'optimiseur, `num_timesteps`, le pool et `VecNormalize`;
4. recalculer la progression de cosine annealing;
5. verifier la compatibilite de l'espace d'action, de l'observation et du masque.

Une copie distante ne doit pas remplacer directement un fichier en cours d'ecriture. Ecrire localement, valider la taille, puis copier vers Drive. L'export ONNX doit etre teste par `onnxruntime` avant archivage.

## 11. Protocole d'evaluation

### Metriques comportementales

- masse moyenne et maximale par episode;
- duree mediane de survie;
- taux de capture apres split dans les 30 sous-ticks;
- taux de splits invalides, qui doit etre nul;
- absorption correcte des virus a 16 cellules;
- taux d'eclatements involontaires;
- taux de victoire contre bots et checkpoints holdout.

### Phases de progression

| Phase | Pas | Critere de validation cible |
| --- | ---: | --- |
| Forage et evitement | 0-2M | masse moyenne >= 80, trajectoires suicidaires eliminees |
| Traque et predation | 2M-8M | au moins 1.2 capture/episode, survie > 1500 ticks |
| Maitrise et self-play | 8M-20M | victoire > 75% contre bots heuristiques, sans regression holdout |

Ces seuils servent au diagnostic et ne doivent pas etre utilises comme preuve causale sans plusieurs seeds et ablations.

### Ablations obligatoires

Comparer au minimum:

1. reward pur contre reward avec PBRS;
2. masque strict contre penalite de split illegal;
3. LayerNorm contre reseau non normalise;
4. cosine annealing contre learning rate constant;
5. pool PFSP contre dernier checkpoint uniquement;
6. `norm_obs=False` contre toute autre normalisation d'observation;
7. warm-start BC contre initialisation aleatoire.

## 12. Checklist d'implementation

- [ ] `sb3-contrib` et `MaskablePPO` sont installes.
- [ ] `action_masks()` encode exactement `mass >= 36` et `cells < 16`.
- [ ] Aucun split illegal n'est echantillonne pendant l'entrainement et l'evaluation.
- [ ] Reward minimal, mort bornee, kill proportionnel et PBRS suspendu au split.
- [ ] LayerNorm/RMSNorm active dans le tronc et les deux tetes.
- [ ] `VecNormalize(norm_obs=False, norm_reward=True, clip_reward=10.0)` est persiste.
- [ ] Cosine annealing restauree correctement apres reprise.
- [ ] Pool historique, bots heuristiques et clones suivent la distribution cible.
- [ ] Metriques PPO et comportementales sont journalisees.
- [ ] Tests physiques, Gym, masques, sauvegardes et export ONNX passent.
- [ ] Les resultats sont rapportes avec seed, hardware, debit reel et checkpoint source.

## 13. Fichiers du depot a maintenir

- `src/env/gym_wrapper.py`: observation, actions, masque et reward.
- `src/env/agar_engine.py`: dynamique de l'arene et interactions.
- `src/env/physics_fast.py`: boucles physiques accelerees.
- `src/training/policy_arch.py`: LayerNorm/RMSNorm et schedule LR.
- `src/training/train_colab.py`: orchestration PPO, VecNormalize, reprise et sauvegardes.
- `src/training/self_play_pool.py`: ligue et adversaires historiques.
- `src/training/callbacks.py`: checkpoints, pool et metriques.
- `src/training/pretrain_bc.py`: warm-start comportemental.
- `config/env_config.yaml`: physique et reward.
- `config/ppo_config.yaml`: hyperparametres et self-play.
- `notebooks/train_colab.ipynb`: execution Colab et export.
