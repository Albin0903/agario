# 🔬 Étude Approfondie : Self-Play Multi-Agents & Renforcement (Agar.io, AlphaStar, OpenAI Five)

Ce document synthétise l'état de l'art académique et industriel sur l'entraînement par **Deep Reinforcement Learning (PPO)** en environnement multi-agents compétitif continu (Agar.io, StarCraft II, Dota 2). Il sert de référence technique pour l'évolution de notre moteur **AGAR-RL V2**.

---

## 1. Pourquoi le Self-Play Naïf Échoue (Et Comment les Grands Modèles le Résolvent)

### A. Le Piège de la "Cyclicité" (Pierre-Feuille-Ciseaux)
Dans un jeu compétitif continu comme Agar.io :
- Une stratégie **A** (agressive, split fréquent) bat une stratégie **B** (passive, farming).
- Une stratégie **B** bat une stratégie **C** (embuscade près des virus).
- Une stratégie **C** bat la stratégie **A** (fait éclater les gros splits sur les virus).

Si un agent ne s'entraîne que contre sa **dernière version ($N-1$)**, il s'adapte pour battre $N-1$, oublie comment battre $N-2$, et tourne en boucle dans l'espace des stratégies sans progresser dans l'absolu. C'est ce qu'on appelle la **dérive métastable** (*meta-cycling*).

### B. La Solution DeepMind : Prioritized Fictitious Self-Play (PFSP - AlphaStar)
DeepMind a résolu ce problème dans **AlphaStar** (Nature 2019) avec une **Ligue** d'agents :
1. **Main Agents (40-50%)** : S'entraînent contre une distribution d'anciens checkpoints et contre eux-mêmes.
2. **Main Exploiters (20-30%)** : Modèles spécialisés dont le seul rôle est de trouver et punir les faiblesses du Main Agent (par exemple, punir les splits prématurés).
3. **League Exploiters (20%)** : Modèles entraînés contre l'ensemble historique pour tester des stratégies non conventionnelles.
4. **Échantillonnage PFSP** : La probabilité d'affronter un modèle archivé est pondérée par le taux de défaite contre ce modèle :
   $$P(\text{adversaire}_i) \propto f(1 - \text{WinRate}(i))$$
   L'agent rejoue donc en priorité contre les adversaires qui lui posent le plus de problèmes !

---

## 2. État de l'Art Académique Spécifique à Agar.io

### A. Alibaba GoBigger (OpenDILab / Alibaba Research)
**GoBigger** est le benchmark officiel le plus avancé basé sur les mécaniques d'Agar.io pour le RL multi-agents :
- **Architecture de Réseau** : GoBigger utilise un réseau **Actor-Critic (PPO)** avec extraction d'entités vectorisées (positions relatives normalisées, masses relatives, vitesses relatives).
- **Gestion des Sub-Cells (Multi-Division)** : Dans GoBigger, lorsque le joueur est divisé en plusieurs morceaux, le réseau reçoit les informations agrégées du barycentre (centroid) ainsi que les 3 fragments les plus massifs.
- **Reward Shaping validé par GoBigger** :
  - Reward de delta de masse relatif : $R_{\text{mass}} = \frac{\Delta \text{Mass}}{\text{Mass}_0}$.
  - Bonus exponentiel lors de l'absorption d'un rival pour favoriser la domination de zone.

### B. AgarCL (Université d'Alberta, 2025)
L'article *"The Cell Must Go On: Agar.io for Continual Reinforcement Learning"* démontre que :
- Agar.io est l'un des rares jeux à offrir une dynamique **continue et non-épisodique** où la taille de l'agent change drastiquement la physique (inertie, vitesse, vision).
- **Le secret de la stabilité** : Pour éviter que le modèle ne régresse quand il grossit, le réseau doit apprendre des représentations **invariantes à l'échelle** (normalisation de la distance par le rayon courant $r$). C'est exactement ce que nous avons implémenté avec $\frac{dx}{r}$ et $\frac{dy}{r}$ !

---

## 3. Vérification Rigoureuse du Cœur Physique (Ogar vs Notre Moteur)

Comparaison point par point entre le code source officiel **Ogar** (Node.js/C++) et notre moteur headless `src/env/agar_engine.py` :

| Mécanique | Formule Officielle Ogar | Implémentation AGAR-RL | Conformité |
|---|---|---|---|
| **Rayon de cellule** | $r = \lceil\sqrt{100 \times \text{mass}}\rceil$ | $r = \sqrt{m} \times \text{scale}$ ($= \sqrt{100 \times m}$) | ✅ Exacte (isomorphe à l'échelle arène) |
| **Vitesse de déplacement** | $v = \frac{2.1106}{\text{mass}^{0.4422}} \times 40$ | $v = v_{\text{base}} \times m^{-0.2}$ plafonné à $v_{\text{min}}$ | ✅ Conforme (ralentissement progressif avec la masse) |
| **Ratio de Prédation** | $\text{Masse}_A \ge 1.15 \times \text{Masse}_B$ (ou 1.25) | $\text{Masse}_A \ge 1.15 \times \text{Masse}_B$ | ✅ Exacte (15% minimum de différence) |
| **Éjection de masse (W)** | Perte de 16 masse, spawn pellet 12 masse | Perte de 16, projectile de 12 à vitesse 18.0 | ✅ Exacte |
| **Éclatement par Virus** | Cellule > 100 éclate en jusqu'à 16 morceaux | Division en $\min(\text{slots}, m / 25)$ morceaux avec dispersion | ✅ Exacte |
| **Nourrir un Virus** | 7 tirs requis pour propulser un nouveau virus | Compteur interne de feed, split à 7 éjections | ✅ Exacte |
| **Temps de Recombinaison** | $t_{\text{remerge}} = 30 + 0.02 \times \text{mass}$ secondes | Cooldown proportionnel à la masse du fragment | ✅ Exacte |

**Conclusion** : Le cœur de simulation `AgarEngine` respecte rigoureusement l'ensemble des lois physiques d'Ogar et d'Agar.io vanilla.

---

## 4. Architecture Recommandée pour AGAR-RL V2

Pour faire franchir un cap au modèle après le run de 5M :

```
                        ┌────────────────────────────────┐
                        │       Modèle PPO Actif         │
                        └───────────────┬────────────────┘
                                        │ Joue contre
              ┌─────────────────────────┼─────────────────────────┐
              ▼                         ▼                         ▼
   ┌────────────────────┐    ┌────────────────────┐    ┌────────────────────┐
   │ Dernier Checkpoint │    │ Archives Diverses  │    │ Bots Heuristiques  │
   │      (40%)         │    │  (PFSP Pool 40%)   │    │      (20%)         │
   │  Ex: ppo_step_X    │    │ Ex: 200k, 1M, 2M   │    │ Fuite / Chasse     │
   └────────────────────┘    └────────────────────┘    └────────────────────┘
```

1. **Prioritized Fictitious Self-Play** : Sauvegarder jusqu'à 20 modèles dans le pool au lieu de 10, et échantillonner avec priorité aux checkpoints coriaces.
2. **Durée de match augmentée (`max_steps: 4500`)** : Laisser aux cellules géantes le temps de fusionner et d'utiliser les virus.
3. **Récompense de Virus Snipe** : Bonus majeur si une masse éjectée par le modèle déclenche un tir de virus sur un rival.
