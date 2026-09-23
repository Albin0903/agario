# 06 — Recherche UI & Protocole de Design Adaptatif

Ce document formalise la démarche d'ingénierie ergonomique et visuelle du socle Build. Il interdit toute règle visuelle dogmatique ou hardcodée et explicite le protocole d'exploration de design mené par les agents autonomes.

---

## 1. Pourquoi le Design ne doit Jamais Être Hardcodé (Luminosité & Clarté par Défaut)

Une dérive classique des assistants IA consiste à répliquer un style par défaut (palette sombre gris anthracite `bg-slate-950`, néons artificiels, faux design « cyberpunk » ou badges de télémétrie décoratifs) sur n'importe quel projet, ruinant la lisibilité grand public.

Dans le socle Build :

* **Luminosité par défaut :** Tout produit grand public (B2C, jeux familiaux, outils bureautiques) démarre obligatoirement sur un **thème clair satiné (`bg-slate-50` à `bg-white`)**, caractérisé par un fort contraste typographique (`text-slate-900`) et des ombrages solaires doux (`shadow-sm shadow-slate-200/50`). L'introduction d'un mode sombre doit être un choix utilisateur explicite ou un paramètre secondaire, jamais le canevas imposé.
* **Épuration radicale de l'information (No Vanity Metrics) :** Chaque donnée affichée doit avoir une utilité décisionnelle directe pour l'utilisateur. Toute métrique décorative, faux indicateur d'IA ou statistique non sollicitée est considérée comme un défaut de conception.
* **Contextualisation métier :**
  * *Un jeu de société (ex. Puissance 4)* : Plateau physique à la profondeur tangible, châssis bleu cobalt, jetons rouge vermillon et jaune solaire, interaction directe sur les colonnes.
  * *Un outil de gestion commerciale (CRM)* : Contrastes calmes, surfaces claires aérées (`bg-slate-50`), tableaux denses lisibles.
  * *Un utilitaire technique pour développeurs* : Thème sombre justifié, polices monospace et raccourcis clavier explicites.

---

## 2. Remplacer la Décoration Visuelle par la Tangibilité Physique (Physical Invariants)

Tout objet manufacturé ou plateau interactif doit être modélisé selon ses contraintes mécaniques réelles plutôt que comme de simples cercles SVG posés sur un fond plat :

1. **Sandwich de couches z-index réelles :**
   * `z-0` : Socle arrière / fond de cavité (matière de fond, ombres portées intérieures).
   * `z-10` : Coulisse interne / rails de guidage.
   * `z-20` : Pièces et pions physiques en mouvement.
   * `z-30` : Façade ajourée / montants avant créant l'effet de fenêtre et masquant les pièces derrière les parois.
   * `z-40` : Zone de frappe supérieure / boutons d'insertion directe.
   * `z-50` : Mécanisme inférieur de décharge (loquet de vidage gravitationnel).

2. **Cinématique physique réelle :**
   * Les pièces ne se déplacent pas à vitesse linéaire uniforme : elles accélèrent sous gravité (`cubic-bezier(0.5, 0, 0.75, 0)`), disparaissent derrière la façade et subissent un **rebond terminal réaliste** avec feedback sonore ou haptique discret.

---

## 2. Le Protocole de Découverte UI (UI Discovery)

Avant toute génération de code HTML/CSS, l'agent réalise une phase de cadrage et de recherche en 4 étapes :

### 1. Benchmark des Références Open-Source (GitHub)

* Recherche d'implémentations open-source reconnues dans le même domaine applicatif.
* Inspection des bibliothèques de composants modernes sans style imposé (*headless UI*, primitives Radix, Tailwind UI, shadcn/ui, Aceternity UI, icônes Lucide).
* Identification des conventions d'interaction universelles (ex. : clic direct sur la colonne d'un jeu, raccourci clavier `⌘K`, glisser-déposer).

### 2. Prototypage et Variantes avec Stitch MCP

L'agent utilise le serveur **Stitch MCP** pour explorer et matérialiser les idées :

1. **Création du projet** : `create_project`.
2. **Génération de l'écran initial** : `generate_screen_from_text` avec un prompt décrivant la scène centrale et le contexte sans jargon technique.
3. **Exploration de variantes** : `generate_variants` pour explorer au minimum 2 à 3 directions artistiques contrastées :
   * **Direction 1 (Néo-Tactile / Expressive) :** Reliefs physiques marqués, bordures contrastées, micro-animations d'insertion.
   * **Direction 2 (Minimaliste / Épurée) :** Géométrie pure, teintes douces, espacement généreux.
   * **Direction 3 (Haute Densité / Métier) :** Rendu compact, contrôles précis, typographie hiérarchisée.
4. **Validation utilisateur** : Présentation des options sous forme de maquettes pour valider l'intention ergonomique.

### 3. Modélisation des Tokens (Tailwind CSS v4)

* Définition d'une palette cohérente exploitant les espaces colorimétriques **OKLCH** pour un rendu harmonieux.
* Configuration des conteneurs réactifs (`@container`) et de la typographie fluide (`clamp()`).

---

## 3. Le Squelette Produit Complet (Wireframing First)

Même pour un prototype rapide ou une première itération, l'agent structure toujours les 3 composantes fondamentales d'un produit fini :

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. BARRE SUPÉRIEURE PRODUIT (Header Contextuel)                        │
│    [Logo Produit]     [Contexte / Statut]     [Mode ▾]  [⚙] [? Règles] │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│ 2. SCÈNE CENTRALE (The Stage)                                          │
│    Espace interactif principal centré et dimensionné pour occuper      │
│    la vue sans scroll parasite indésirable (min-h-[calc(100vh-...)]).  │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│ 3. PÉRIPHÉRIQUES FONCTIONNELS & ACTIONS                                │
│    [Action Primaire]       [Actions Secondaires]      [Modales d'état] │
└────────────────────────────────────────────────────────────────────────┘
```

### 1. Barre Supérieure Produit

* Identité du produit et statut temps réel.
* Sélecteur de mode (ex. : Solo, Duo Local, Multijoueur).
* Accès direct aux règles du jeu (`? Règles`) et aux réglages (`⚙`).

### 2. Scène Centrale (The Stage)

* Le cœur immersif de l'application (plateau de jeu, toile de dessin, éditeur, espace de données).
* **Manipulation directe obligatoire** :
  * Clic direct sur l'élément interactif (ex. : clic sur une colonne de la grille pour insérer un pion).
  * Prévisualisation dynamique au survol (`hover:`).
  * Interdiction absolue de formulaires textuels déportés pour choisir une colonne ou une case.

### 3. Périphériques Fonctionnels & Scène Non-Bloquante

* **Principe de la Scène Non-Bloquante (Zero Obstructive Modals) :**
  * L'état d'arrêt ou d'achèvement d'un processus (victoire de jeu, validation de commande, confirmation de paiement) ne doit **jamais recouvrir l'élément focal par une modale opaque**.
  * L'humain souhaite observer et analyser la grille victorieuse ou l'artéfact principal.
  * La confirmation s'intègre en **périphérie directe** (bannière haute, volet latéral, pulsation lumineuse sur les pièces clés) tout en laissant l'artéfact central 100% visible et manipulable.
* Les modales natives `<dialog>` sont réservées exclusivement aux aides ponctuelles (`? Règles`) ou aux confirmations d'actions destructives.

---

## 4. Hiérarchie Stricte des Contrôles & Contrôle Direct à la Source

L'interface évite toute surcharge visuelle et élimine la navigation inutile dans les sous-menus :

1. **Contrôle direct à la source :** Tout indicateur contextuel affiché à l'écran (compte à rebours, compteur de points, statut audio) doit être **lui-même le commutateur de son propre état** (clic direct pour basculer actif/inactif, pause/reprise, sourdine).
2. **Action Primaire (1 seule par écran/état)** : Saillante, immédiatement identifiable, contraste marqué (`Nouvelle manche`, `Commencer`).
3. **Actions Secondaires** : Boutons fantômes ou bordures discrètes (`Règles`, `Historique`).
4. **Actions Destructives / Système** : Reléguées à l'écart avec confirmation obligatoire (`Réinitialiser`).
5. **Interaction Directe** : Gérée nativement sur les composants de la scène centrale.

---

## 5. Audit et Assurance Qualité avec Chrome DevTools MCP (Obligation Multi-Résolutions)

Avant de déclarer une interface ou une tâche terminée, l'agent valide l'implémentation via `chrome-devtools-mcp` :

* **Double capture obligatoire multi-résolutions :**
  * **Format Bureau (1200x900)** : Vérification du centrage de la scène, de l'absence de scroll parasite, des espacements et de l'harmonie des contrastes clairs satinés.
  * **Format Mobile (390x844)** : Vérification du repliement responsive des panneaux latéraux, de l'accessibilité tactile (cibles min 44x44px) et de l'absence de débordement horizontal.
* **Inspection des interactions au clic :** Vérification du comportement dynamique et des transitions d'état.
* **Conformité WCAG AA :** Contrastes vérifiés (> 4.5:1 pour le texte courant, > 3:1 pour les grands titres).
* **Accessibilité clavier :** Anneaux de focus (`focus-visible:ring-2`) visibles sur tous les éléments cliquables.
* **Console d'exécution hermétique :** Zéro avertissement ou exception non gérée dans les logs du navigateur (`list_console_messages`).

---

## 6. L'Alliance Hybride : Mobiliser le Frontend Riche et les Bibliothèques Externes

L'architecture Build est délibérément **hybride**. Les agents ne doivent jamais s'autocensurer en réduisant tout le projet à du pur SSR textuel lorsqu'une expérience interactive riche est demandée :

1. **Quand basculer sur le Frontend Riche React (`web-app/`) :**
   * Jeux interactifs et toiles temps réel à 60 FPS (Canvas, Web Audio, physiques gravitationnelles ou cinétiques).
   * Manipulation directe haute fréquence, drag-and-drop fluide, modélisations 3D, graphes dynamiques.
   * L'écosystème React 19 / Vite / Tailwind v4 / Lucide React est là précisément pour ces 20 % d'interfaces critiques.
2. **Quand enrichir le Frontend Léger Templ + HTMX :**
   * Pour les 80 % de vues serveur, utiliser les composants SVG d'icônes natifs du fichier `icons.templ` (`@IconHelp`, `@IconSettings`, etc.) pour des visuels soignés et légers sans aucune dépendance npm.
   * Injecter des keyframes d'animation, des ombres portées et des styles personnalisés avec `views.CustomCSS(css)` de `styles.go`.
   * Mobiliser l'API Web Audio native du navigateur pour les retours sonores haptiques.

---

## 7. Retours d'Expérience & Bonnes Pratiques Multiplateformes (Windows / Linux / macOS)

1. **Fins de lignes CRLF et Biome (`.gitattributes`) :**
   * Le fichier racine `.gitattributes` (`* text=auto eol=lf`) garantit des sauts de ligne Unix homogènes et prévient les faux-positifs de Biome sous Windows.
2. **VCS Stamping sur les nouveaux dépôts (`Taskfile.yml`) :**
   * L'argument `-buildvcs=false` est intégré par défaut dans la tâche `build:bin` pour immuniser la compilation Go contre l'erreur code 128 sur les dépôts neufs.
3. **Isolation des modales face aux swaps HTMX :**
   * Les dialogues HTML5 globaux (`<dialog id="rules-modal">`, modales de paramètres) sont obligatoirement hébergés dans `layout.templ` sous `<body>` et hors de `<main>` afin de ne jamais être détruits par un remplacement HTMX (`hx-swap`).
4. **Styles et Keyframes sans Prettier (`styles.go`) :**
   * Ne jamais utiliser de balise `<style>` brute dans un fichier `.templ` (qui déclenche un appel Prettier défaillant sous Windows lors de `templ fmt`). Utiliser systématiquement `views.CustomCSS(css)`.

