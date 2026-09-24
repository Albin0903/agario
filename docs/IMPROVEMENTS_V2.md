# 🚀 Feuille de Route d'Amélioration : Vers le Niveau Compétitif (V2)

Ce document formalise les axes prioritaires pour faire passer l'agent AGAR-RL du stade actuel (**chasseur efficace au corps-à-corps**) au stade **compétitif expert** (mécaniques de virus, projection de masse, split-kills tactiques et Self-Play League).

---

## 1. Mécanique Avancée des Virus : Nourrir & Propulser ("Virus Shooting")

### A. Constat Actuel
- Pour nourrir et propulser un virus dans les règles réelles d'Agar.io, une cellule doit éjecter **7 fois de la masse** (`7 * 16 = 112` de masse éjectée).
- Pour pouvoir le faire sans mourir, l'agent doit avoir au minimum **130 à 150 de masse**.
- Actuellement, les épisodes se terminent souvent ou se réinitialisent avant que l'agent n'accumule suffisamment de masse et d'opportunités d'angle pour viser un virus vers un adversaire.

### B. Améliorations Proposées
1. **Bonus de Palier de Masse (Milestone Rewards)** :
   - Donner un reward incitatif (+3.0) dès que l'agent atteint **130 de masse** (seuil de split agressif et d'interaction virus).
   - Donner un reward (+5.0) à **250 de masse**.
2. **Reward d'Éclatement Ennemi par Virus** :
   - Quand l'agent éjecte de la masse dans un virus qui se propage et touche un ennemi (faisant exploser l'adversaire en 16 fragments), accorder un gros reward ponctuel (`+10.0`).
3. **Observation Spécifique des Virus** :
   - Ajouter dans le vecteur d'observation la distance relative et le vecteur d'alignement avec les 2 virus les plus proches :
     - *Est-ce qu'un ennemi plus gros se trouve derrière le virus ?* (opportunité de tir).
     - *Est-ce que je suis plus petit que le virus (< 130) ?* (opportunité de se cacher sous le virus).

---

## 2. Allongement des Épisodes & Dynamique d'Arène

### A. Durée de Vie Maximale (`max_steps`)
- **Actuel** : 2 500 ticks (~83 secondes par épisode).
- **Proposition** : Passer à **4 000 ou 5 000 ticks** (~2.5 minutes).
- **Bénéfice** : Permet aux cellules géantes de fusionner après un split (le cooldown de recombinaison est de ~30 secondes pour une cellule de 200 de masse). Si l'épisode est trop court, l'agent reste divisé et ne découvre jamais la puissance de la réunification post-chasse.

### B. Densité & Régénération de l'Arène
- Passer à **8 à 10 bots par arène** (au lieu de 5) pour multiplier les opportunités de prédation et créer un écosystème plus dynamique.
- Augmenter les pellets à **2 000** pour soutenir la croissance de plusieurs grosses cellules simultanément.

---

## 3. Système de "League Training" (Diversité du Self-Play)

Votre idée d'avoir **50% de clones évolutifs + des modèles figés de niveaux variés** est exactement l'architecture utilisée par **AlphaStar (DeepMind)** et **OpenAI Five**.

### A. Le Problème Évité : La "Cyclicité" (Pierre-Feuille-Ciseaux)
Si un modèle ne s'entraîne que contre sa version précédente (N-1), il peut adopter une stratégie très spécialisée qui bat N-1 mais perd contre un bot naïf ou contre une stratégie plus ancienne.

### B. Architecture Proposée pour le Pool :
Au lieu d'un pool FIFO simple, nous définissons **3 catégories d'adversaires** dans l'arène :

| Catégorie | Pourcentage | Rôle |
|---|---|---|
| **Main Opponent (Dernier Checkpoint)** | **40%** | Pousse l'agent à s'adapter à la dernière méta et à battre son propre niveau actuel. |
| **Past Checkpoints Figés (Diversifiés)** | **40%** | Un échantillon figé couvrant les étapes (200k, 600k, 1M, 1.5M, etc.) pour garantir qu'il ne régresse sur aucune stratégie passée. |
| **Bots Heuristiques / Exploiteurs** | **20%** | Des bots à règles simples mais impitoyables (très agressifs sur la nourriture, ou fuite absolue) pour forcer l'agent à ne pas négliger les bases. |

---

## 4. Spécialisation du Split-Kill

- Actuellement, l'agent hésite parfois à split car la division divise la masse par 2 et augmente la vulnérabilité temporaire.
- **Récompense de Split Agressif Réussi** :
  - Si l'action `split` est exécutée ET qu'une cellule ennemie est dévorée dans les 1.5 secondes suivantes : accorder un bonus de **+8.0**.
  - Si un split est fait "dans le vide" sans ennemi à portée : légère pénalité de cooldown pour éviter le spam.

---

## 5. Synthèse des Priorités pour le Prochain Run (V2)

1. **Augmenter `max_steps` à 4 000** (permet d'atteindre 300+ de masse et de re-merger).
2. **Ajouter le bonus de palier de masse** (incitation à dépasser 130 de masse).
3. **Instaurer la répartition 40% dernier clone / 40% archives figées / 20% heuristique**.
4. **Augmenter la population de la carte (8 bots, 2000 pellets)**.

