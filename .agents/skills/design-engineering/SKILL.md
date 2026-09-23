---
name: design-engineering
description: >
  Invariants mathematiques de design (Ecole Suisse) : echelle typographique modulaire,
  grille spatiale 8px, physique d'animation (spring), contraste APCA, alignement optique,
  palette fonctionnelle Radix 12 niveaux. Utiliser des qu'une tache touche a la typographie,
  aux espacements, aux couleurs, aux animations ou a la conformite visuelle d'un composant.
allowed-tools: Bash, Read, Write
---

# Design Engineering System — Invariants Mathematiques

Ce document formalise les constantes de design applicables a tout projet issu du template Build.
Les valeurs ci-dessous ne sont pas arbitraires : elles derivent de formules mathematiques,
de standards d'accessibilite et de principes de perception humaine.

Les regles de ce document completent (sans dupliquer) la skill `frontend-design` qui couvre
le protocole de conception (phases de recherche, prototypage Stitch, squelette produit).
Ici, on traite exclusivement des **mesures, ratios et seuils numeriques**.

---

## 1. Echelle Typographique Modulaire

### Formule

```
taille(step) = base * ratio^step
```

### Echelle retenue : Major Second (ratio 1.125, base 16px)

| Token    | Step | Calcul             | Valeur   | rem     | Classe Tailwind |
|----------|------|--------------------|----------|---------|-----------------|
| `xs`     | -2   | 16 * 1.125^(-2)    | 12.64px  | 0.79rem | `text-xs`       |
| `sm`     | -1   | 16 * 1.125^(-1)    | 14.22px  | 0.89rem | `text-sm`       |
| `base`   |  0   | 16 * 1.125^0       | 16.00px  | 1.00rem | `text-base`     |
| `lg`     |  1   | 16 * 1.125^1       | 18.00px  | 1.125rem| `text-lg`       |
| `xl`     |  2   | 16 * 1.125^2       | 20.25px  | 1.266rem| `text-xl`       |
| `2xl`    |  3   | 16 * 1.125^3       | 22.78px  | 1.424rem| `text-2xl`      |
| `3xl`    |  4   | 16 * 1.125^4       | 25.63px  | 1.602rem| `text-3xl`      |
| `4xl`    |  5   | 16 * 1.125^5       | 28.83px  | 1.802rem| `text-4xl`      |

### Regle stricte

Utiliser **exclusivement** les classes de l'echelle Tailwind (`text-xs` a `text-9xl`).
Interdiction de `text-[Npx]` ou `text-[N.Nrem]` sauf cas documente dans un commentaire causal.

### Rythme vertical (line-height)

Le `line-height` doit toujours etre un multiple de 4px pour maintenir le rythme vertical :

| Classe Tailwind | Valeur  | Usage                          |
|-----------------|---------|--------------------------------|
| `leading-4`     | 16px    | Texte dense, labels compacts   |
| `leading-5`     | 20px    | Corps de texte `text-sm`       |
| `leading-6`     | 24px    | Corps de texte `text-base`     |
| `leading-7`     | 28px    | Sous-titres `text-lg`          |
| `leading-8`     | 32px    | Titres `text-xl` et au-dela    |

---

## 2. Systeme Spatial 8px

### Principe

Tous les espacements (padding, margin, gap, width, height) utilisent des multiples de 8px.
Les demi-pas de 4px sont reserves aux micro-ajustements internes (gap icone-texte, padding
dense dans un badge).

### Grille de reference

| Tailwind | Valeur | Usage                                           |
|----------|--------|-------------------------------------------------|
| `0.5`    | 2px    | Separation minimale (ring-offset)               |
| `1`      | 4px    | Demi-pas : gap icone-texte dans badge           |
| `1.5`    | 6px    | Demi-pas : gap icone-texte dans bouton          |
| `2`      | 8px    | Unite de base : padding interne compact         |
| `3`      | 12px   | Padding interne de badge, gap entre items denses|
| `4`      | 16px   | Padding standard de composant                   |
| `5`      | 20px   | Padding genereux de composant                   |
| `6`      | 24px   | Gap entre sections, padding de carte            |
| `8`      | 32px   | Marge entre blocs, gap de grille                |
| `10`     | 40px   | Marge de section                                |
| `12`     | 48px   | Padding de zone immersive (Stage)               |
| `16`     | 64px   | Marge verticale de page                         |
| `20`     | 80px   | Separation de sections majeures                 |
| `24`     | 96px   | Espace de respiration maximal                   |

### Regle stricte

Interdiction de valeurs arbitraires (`p-[13px]`, `gap-[7px]`, `mt-[22px]`).
Les exceptions documentees (ex. `min-h-[calc(100vh-...)]` pour le Stage) requierent
un commentaire causal expliquant pourquoi aucune classe standard ne convient.

---

## 3. Physique des Micro-Interactions (Spring Physics)

### Pourquoi remplacer les courbes de Bezier

Les courbes `cubic-bezier` sont des fonctions temporelles fixes : elles ne reagissent pas
a l'interruption par l'utilisateur (clic mid-animation). Les ressorts physiques (spring)
preservent la velocite et produisent un mouvement naturellement interruptible.

### Presets standardises

| Preset    | Stiffness | Damping | Mass | Usage                              |
|-----------|-----------|---------|------|------------------------------------|
| `snappy`  | 400       | 30      | 1.0  | Boutons, toggles, badges           |
| `smooth`  | 200       | 25      | 1.2  | Modales, panneaux lateraux         |
| `gentle`  | 120       | 20      | 1.5  | Transitions de page, fade-in       |
| `bouncy`  | 350       | 15      | 0.8  | Notifications, compteurs, feedback |

### Implementation React (framer-motion / motion)

```tsx
import { motion } from "motion/react";

// Preset snappy pour un bouton
<motion.button
  whileTap={{ scale: 0.97 }}
  transition={{ type: "spring", stiffness: 400, damping: 30, mass: 1 }}
>
  Valider
</motion.button>
```

### Fallbacks CSS pour Templ (SSR)

Quand les spring physics ne sont pas disponibles (pas de runtime JS), utiliser ces
courbes de Bezier calibrees comme approximation :

| Preset   | CSS `transition-timing-function`      |
|----------|---------------------------------------|
| snappy   | `cubic-bezier(0.22, 1, 0.36, 1)`     |
| smooth   | `cubic-bezier(0.16, 1, 0.3, 1)`      |
| gentle   | `cubic-bezier(0.33, 1, 0.68, 1)`     |
| bouncy   | `cubic-bezier(0.34, 1.56, 0.64, 1)`  |

### Durees standardisees

| Token         | Valeur | Usage                                    |
|---------------|--------|------------------------------------------|
| `fast`        | 150ms  | Micro-interactions (hover, focus, toggle) |
| `normal`      | 250ms  | Transitions de composant (modal open)     |
| `slow`        | 400ms  | Transitions de page, animations longues   |
| `very-slow`   | 600ms  | Cinematique physique (chute, rebond)      |

---

## 4. Contraste APCA & Accessibilite

### APCA Lightness Contrast (Lc) — seuils minimaux

L'algorithme APCA (Advanced Perceptual Contrast Algorithm, WCAG 3.0) remplace le ratio
lineaire 4.5:1 de WCAG 2.x par une mesure perceptive dynamique tenant compte de la taille,
de la graisse et de la polarite texte/fond.

| Lc minimum | Usage                                              |
|------------|----------------------------------------------------|
| Lc 75      | Texte courant (corps, paragraphes)                 |
| Lc 60      | Texte secondaire, labels, placeholders actifs      |
| Lc 45      | Titres grands (>= 24px normal, >= 18px bold)       |
| Lc 30      | Elements non-texte (icones, bordures, separateurs) |
| Lc 15      | Elements desactives, placeholders inactifs         |

### Palette fonctionnelle (modele Radix 12 niveaux)

La palette est structuree par **usage**, pas par luminosite brute :

| Niveaux | Fonction                | Exemples Tailwind (theme clair)      |
|---------|-------------------------|--------------------------------------|
| 1-2     | Fonds d'application     | `bg-white`, `bg-slate-50`           |
| 3-5     | Fonds de composants     | `bg-slate-100` / `hover:bg-slate-200` / `active:bg-slate-300` |
| 6-8     | Bordures                | `border-slate-200` (subtil) / `border-slate-300` / `hover:border-slate-400` |
| 9-10    | Surfaces solides        | `bg-indigo-600` (primaire) / `hover:bg-indigo-700` |
| 11-12   | Texte                   | `text-slate-600` (secondaire) / `text-slate-900` (primaire) |

### Regle stricte

Tout texte de corps (`text-base` ou inferieur) sur fond clair doit atteindre Lc 75.
Tout label ou texte secondaire doit atteindre Lc 60.
La combinaison `text-slate-900` sur `bg-white` produit un Lc d'environ 106 (conforme).
La combinaison `text-slate-600` sur `bg-white` produit un Lc d'environ 66 (conforme pour labels).

---

## 5. Alignement Optique

### Compensation de centre geometrique vs centre perceptif

Le centre mathematique d'un element ne correspond pas toujours au centre percu par l'oeil
humain. L'alignement optique corrige cette dissonance.

### Regles de compensation

| Element                    | Compensation                                          |
|----------------------------|-------------------------------------------------------|
| Triangle play / fleche     | Decaler de +5-10% vers la droite (`pl-0.5` ou `ml-px`) |
| Icone dans bouton          | `gap-1.5` (6px) systematique entre icone et texte     |
| Formes rondes (O, icones)  | Depassement de 1-2% au-dela de la baseline            |
| Texte centre dans bouton   | `text-center` + `px` symetrique, verifier visuellement |

### Bordures de focus

Utiliser systematiquement `focus-visible:ring-2 focus-visible:ring-offset-2` avec une
couleur derivee de l'action principale du composant :

```html
<!-- Bouton primaire -->
<button class="... focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-indigo-500">
  Action
</button>

<!-- Bouton destructif -->
<button class="... focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-rose-500">
  Supprimer
</button>
```

---

## 6. Snippets de Reference

### Hierarchie de boutons (React / Tailwind)

```tsx
// Niveau 1 : Primaire (1 seul par ecran/etat)
<button className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white text-sm font-medium shadow-xs transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-indigo-500">
  Valider
</button>

// Niveau 2 : Secondaire
<button className="px-4 py-2 rounded-lg bg-white hover:bg-slate-50 border border-slate-200 hover:border-slate-300 text-slate-700 text-sm font-medium shadow-xs transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-slate-400">
  Consulter
</button>

// Niveau 3 : Ghost / Destructif
<button className="px-3 py-1.5 rounded-md text-rose-600 hover:bg-rose-50 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-rose-500">
  Supprimer
</button>
```

### Carte standard (Templ)

```go
templ StandardCard(title string) {
	<div class="rounded-xl border border-slate-200/90 bg-white p-6 shadow-xs">
		<h3 class="text-sm font-semibold text-slate-900 tracking-tight">{ title }</h3>
		<div class="mt-3 text-sm text-slate-600 leading-6">
			{ children... }
		</div>
	</div>
}
```

### Indicateur contextuel cliquable (regle 12 AGENTS.md)

```go
// L'indicateur est lui-meme le commutateur de son propre etat.
templ StatusIndicator(label string, active bool) {
	<button
		type="button"
		class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-indigo-500"
		if active {
			class="bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100"
		} else {
			class="bg-slate-100 text-slate-500 border border-slate-200 hover:bg-slate-200"
		}
	>
		<span
			class="w-2 h-2 rounded-full"
			if active {
				class="bg-emerald-500 animate-pulse"
			} else {
				class="bg-slate-400"
			}
		></span>
		{ label }
	</button>
}
```

---

## 7. Audit Statique (`task lint:design`)

Le script `scripts/lint-design.ps1` detecte les violations de tokens en scannant les
fichiers source pour les classes Tailwind arbitraires.

### Classes interdites (regex)

```regex
(p|m|gap|w|h|text|leading|tracking|rounded|border|shadow|inset|top|right|bottom|left|max-w|min-w|max-h|min-h|basis|space|indent|scroll-m|scroll-p)-\[\d+(\.\d+)?(px|rem|em)\]
```

### Exceptions documentees

Les patterns suivants sont autorises car ils dependent de calculs dynamiques :

- `min-h-[calc(...)]` : Dimensionnement du Stage base sur la hauteur du viewport
- `w-[calc(...)]` : Largeur dynamique en contexte de grille
- Classes arbitraires dans `@apply` au sein de `@layer components` dans `index.css`

Toute autre valeur arbitraire declenche un echec du lint.

---

## 8. Invariants Kinesthésiques & Game Juice

Une interface hautement interactive ou ludique ne se juge pas a sa structure statique (DOM/SVG par cellules), mais a sa physique, sa reactivite et sa boucle sensorielle.

### 8.1 File d'Attente de Commandes (Input Buffering / FIFO)

Lors d'interactions rapides (ex. virages a 90 degres dans un jeu ou raccourcis clavier en rafale), l'utilisateur tape souvent la prochaine commande avant meme que la case ou le frame precedent ne soit termine. Sans tampon, la commande est perdue et le controle parait rigide ou defaillant.

**Pattern TypeScript standard (Buffer FIFO) :**

```typescript
export class InputBuffer<T> {
  private queue: T[] = [];
  private readonly maxSize: number;

  constructor(maxSize = 2) {
    this.maxSize = maxSize;
  }

  public push(action: T): void {
    if (this.queue.length < this.maxSize) {
      this.queue.push(action);
    }
  }

  public next(): T | undefined {
    return this.queue.shift();
  }

  public clear(): void {
    this.queue = [];
  }
}
```

### 8.2 Boucle de Rendu 60 FPS & Interpolation sous-cellulaire

Pour toute manipulation a haute frequence (>30 Hz), abandonner le re-rendu d'elements DOM/SVG au profit d'un **Canvas 2D ou WebGL** cadencé sur `requestAnimationFrame` avec calcul explicite du temps ecoule (`deltaTime`) :

```typescript
let lastTime = performance.now();

function gameLoop(currentTime: number): void {
  const dt = Math.min((currentTime - lastTime) / 1000, 0.1); // Plafonnement a 100ms
  lastTime = currentTime;

  // 1. Depiler les commandes du buffer FIFO
  processInputBuffer();

  // 2. Mettre a jour les positions physiques continues (vitesse * dt)
  updateKinematics(dt);

  // 3. Rendre sur Canvas 2D avec interpolation
  render(ctx);

  requestAnimationFrame(gameLoop);
}
```

### 8.3 Anticipation & États d'Expression

Donner vie aux composants interactifs implique de modeliser des micro-reactions visuelles prealables :
- **Regard directionnel :** Les pupilles s'orientent vers la direction du prochain deplacement ou vers l'element cible avant l'impact.
- **Anticipation faciale :** Ouverture de la bouche ou leger ecartement a l'approche d'un objet a consommer.
- **Rebond terminal :** Deformation elastique (squash and stretch) a l'impact ou a la reception.

### 8.4 Boucle Sensorielle Audio Procédurale (`web-app/src/lib/audio.ts`)

Toute interaction majeure doit generer un retour tactile immediat via le module Web Audio integre :

```typescript
import { audio } from "@/lib/audio";

// Clic tactile de bouton
audio.click();

// Evenement de score ou capture
audio.pop();

// Choc, impact ou collision
audio.thud();

// Reussite, franchissement de seuil
audio.success();
```

---

## 9. Invariants Ergonomiques E-Commerce & Accessibilité Légale (EAA 2025)

### 9.1 Ergonomie Mobile & Thumb-Zone (Steven Hoober)
Sur écran mobile (>6.5"), 73% des manipulations s'effectuent à une main dans le tiers inférieur de l'écran :
- **Zone naturelle (Tiers inférieur) :** Déployer les CTAs primaires (`Commander`, `Ajouter au panier`, `Confirmer`) dans un conteneur collant en bas d'écran (`position: sticky; bottom: 0`).
- **Zone intermédiaire :** Caractéristiques, images, sélecteurs d'options.
- **Zone d'accès difficile (Tiers supérieur) :** Contenu passif exclusivement (logo, navigation de retour, indicateurs de lecture).

### 9.2 La Règle des 300ms pour les Skeletons (Zéro Clignotement)
Pour les réponses réseau rapides (<300ms), **ne pas afficher de skeleton**. Un skeleton affiché pendant 80ms génère un flash visuel parasite perçu comme un défaut de performance. Le hook `useQuery` intègre cette temporisation par défaut.

### 9.3 Conformité Légale EAA 2025 & WCAG 2.2
- **Cible tactile minimale :** Tout bouton, pastille ou sélecteur interactif sur mobile doit offrir une zone de frappe minimale de **44x44 CSS pixels** (`min-h-[44px]` ou padding suffisant).
- **Indicateur de focus visible :** Contour d'au moins 2px avec ratio de contraste minimum 3:1 (`focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2`).
- **Alternative au glissement :** Toute commande gestuelle (swipe, drag) doit comporter un substitut cliquable / clavier (bouton pas-à-pas, flèches de pagination).


