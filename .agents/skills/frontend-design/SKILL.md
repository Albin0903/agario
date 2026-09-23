---
name: frontend-design
description: >
  Guide et protocole de design adaptatif pour interfaces web modernes avec Tailwind CSS v4.
  Exclut formellement les règles visuelles hardcodées. Impose une phase de recherche UI (benchmarks GitHub,
  composants modernes), le prototypage de variantes via Stitch MCP, l'application du Squelette Produit
  (Wireframing First), l'exploitation sans tabou du frontend riche et des bibliothèques externes,
  la hiérarchie de contrôles et le principe d'inviolabilité de l'expérience utilisateur.
allowed-tools: Bash, Read, Write
---

# Protocole de Design Adaptatif & Découverte UI

Ce guide formalise l'approche de conception d'interface du socle Build. Il **interdit toute règle visuelle dogmatique ou hardcodée** et établit un protocole systématique d'exploration, de recherche et de prototypage adapté à la nature spécifique de chaque application.

---

## 1. Règle Cardinale : Zéro Dogme Visuel Hardcodé

> **Le design ne s'impose pas : il émerge du domaine métier, des besoins de l'utilisateur final et d'une recherche active.**

* **Interdiction formelle** de figer par défaut des thèmes arbitraires ou sombres (bannir le réflexe du thème sombre « gamer » ou « cyberpunk » par défaut).
* **Luminosité par défaut & Thème clair satiné** : Tout produit grand public (B2C, jeux familiaux, outils bureautiques) démarre obligatoirement sur un **thème clair satiné (`bg-slate-50` à `bg-white`)**, à fort contraste typographique (`text-slate-900`) et ombrages solaires doux (`shadow-sm shadow-slate-200/50`). L'introduction d'un mode sombre doit être un choix utilisateur explicite ou un paramètre secondaire, jamais le canevas imposé.
* **Direction Artistique (DA) personnalisée dès le départ** : Dès l'initialisation d'un projet, l'agent formule et applique une identité visuelle propre (ambiance, palette OKLCH, typographie, physique des interactions, textures, micro-animations).
* **Interdiction de concevoir à l'aveugle** : Chaque interface doit être précédée d'une recherche de références du domaine, de composants modernes open-source et d'une proposition de variantes visuelles via les outils de prototypage (Stitch MCP).
* **Inviolabilité de l'expérience utilisateur** : L'interface s'adresse exclusivement à l'utilisateur du produit. Zéro mention de technologies (`Go`, `HTMX`, `Templ`, `Vite`, `React`, `Docker`, `Tailwind`), zéro métrique d'implémentation (p99, polling rate) dans l'UI finale.
* **Épuration radicale de l'information (No Vanity Metrics)** : Chaque donnée affichée doit avoir une utilité décisionnelle directe pour l'utilisateur. Toute métrique décorative, faux indicateur d'IA ou statistique non sollicitée est considérée comme un défaut de conception majeur.

---

## 2. Fin du Tabou : Exploitation Complète du Frontend Riche & des Libs Externes

Le socle Build repose sur une **architecture hybride** conçue pour combiner la robustesse serveur et la fluidité client. Il est formellement erroné de s'interdire le frontend riche ou les bibliothèques clientes par dogmatisme :

1. **Frontend Riche React (`web-app/`) :**
   * Dès qu'une interface requiert une manipulation haute fréquence (60 FPS), un état local complexe, des interactions canvas, de la 3D, ou une physique temps réel (ex. : jeu interactif, éditeur visuel, canvas interactif, dashboard financier ultra-réactif), **le frontend riche React 19 + TanStack Router + Tailwind CSS v4 est le choix naturel**.
   * Les bibliothèques modernes de l'écosystème React/TS (Lucide React, framer-motion/motion, Radix primitives, canvas libraries, Web Audio API) sont pleinement autorisées et recommandées.
2. **Frontend Léger SSR (Templ + HTMX) :**
   * Parfait pour 80 % des vues applicatives, la navigation, les formulaires et les interfaces pilotées par le serveur.
   * L'agent ne doit pas s'interdire d'y adjoindre des composants modernes :
     * **Composants d'icônes SVG natifs** : Utiliser les composants Templ du fichier `icons.templ` (`@IconHelp`, `@IconSettings`, `@IconRefresh`, `@IconPlay`, etc.) pour des visuels soignés sans dépendance npm.
     * **Keyframes et styles sur mesure sans conflit Prettier sous Windows** : Utiliser le composant Go `views.CustomCSS(css)` du fichier `styles.go` plutôt qu'une balise `<style>` brute dans un `.templ`.
     * **Effets sensoriels légers** : Web Audio API pour les retours sonores discrets, animations CSS fluides avec dégradés et ombres portées.

---

## 3. Remplacer la Décoration Visuelle par la Tangibilité Physique (Physical Invariants)

> **Tout objet ou plateau interactif doit être conçu selon ses contraintes mécaniques réelles.**

Les assistants IA ont tendance à plaquer des formes géométriques plates en SVG ou CSS sans épaisseur physique (ex. de simples ronds posés sur un rectangle bleu). Cette approche brise l'immersion :

1. **Sandwich de couches z-index réelles :**
   Tout dispositif physique (ex. plateau de jeu manufacturé, châssis, tiroir, panneau de commande) s'organise en couches successives :
   * `z-0` : **Socle arrière / Fond de cavité** (surface de fond, ombres intérieures).
   * `z-10` : **Coulisse interne / Rail de guidage** (gouttières dans lesquelles les pièces glissent).
   * `z-20` : **Pièces en mouvement** (jetons, cartes, curseurs physiques).
   * `z-30` : **Façade ajourée / Châssis avant** (montants avec perforations circulaires créant l'effet de profondeur et masquant les pièces derrière les parois).
   * `z-40` : **Zone de frappe / Contrôles d'insertion** (flèches de largage, boutons de commande au premier plan).
   * `z-50` : **Mécanisme inférieur de libération** (trappe ou loquet de décharge avec animation d'évacuation par gravité).

2. **Cinématique physique réelle vs simple transition de coordonnées :**
   * Les pièces ne se téléportent pas et ne glissent pas à vitesse uniforme : elles tombent avec accélération gravitationnelle (`cubic-bezier(0.5, 0, 0.75, 0)`), disparaissent derrière les montants du châssis, subissent un **rebond terminal réaliste** à l'impact et émettent un retour haptique/sonore discret.
   * La libération d'un plateau simule l'ouverture d'une trappe inférieure avec vidage simultané de toutes les colonnes vers le bas.

---

## 4. Le Protocole en 6 Phases d'Ingénierie UI

Toute conception d'écran ou de produit suit obligatoirement les 5 phases suivantes :

```
┌─────────────────┐     ┌───────────────────┐     ┌─────────────────┐     ┌───────────────────┐     ┌─────────────────┐
│ 1. RECHERCHE UI │ ──> │ 2. PROTOTYPAGE    │ ──> │ 3. TOKENS       │ ──> │ 4. SQUELETTE      │ ──> │ 5. AUDIT VISUEL │
│    & BENCHMARK  │     │    STITCH MCP     │     │    DÉDIÉS       │     │    PRODUIT        │     │    & A11Y       │
└─────────────────┘     └───────────────────┘     └─────────────────┘     └───────────────────┘     └─────────────────┘
```

---

### Phase 1 : Recherche UI & Benchmark de Composants (UI Discovery)

Avant d'écrire le moindre code de vue, l'agent explore activement l'état de l'art du domaine applicatif :

1. **Recherche de références de composants modernes** :
   * Consulter les implémentations open-source reconnues adaptables en Tailwind CSS v4 / React / Templ (ex. : primitives Radix, shadcn/ui, Tailwind UI, Lucide Icons, Aceternity UI, composants interactifs canvas/HTML5 pour les jeux).
   * Identifier les conventions ergonomiques standard du secteur (ex. : plateau physique tactile pour un jeu de société, volets rétractables pour un éditeur, tableaux denses filtrables pour un outil de gestion).
2. **Identification des points de contact tactiles et sensoriels** :
   * Définir le retour d'état attendu par l'utilisateur (effet de pression physique `active:translate-y-0.5`, feedback sonore ou visuel au dépôt d'une pièce, micro-animations d'insertion fluides).
3. **Vérité Terrain & Inspection Outillée Obligatoire (Chrome DevTools MCP / curl) :**
   * Dès qu'une URL ou une référence de produit est fournie (ex. un jeu spécifique, un service en ligne) : interdiction formelle de concevoir de mémoire.
   * L'agent lance immédiatement Chrome DevTools MCP ou curl pour naviguer sur la cible, inspecter le code source, extraire les sprites et assets réels, analyser les requêtes réseau et capturer le comportement cinématique authentique.

---

### Phase 2 : Prototypage Visuel & Variantes via Stitch MCP

Pour éviter d'enfermer l'utilisateur dans une vision unique, l'agent utilise **Stitch MCP** pour explorer et soumettre plusieurs directions artistiques :

1. **Génération d'écrans (`generate_screen_from_text`)** :
   * Décrire la scène centrale, l'en-tête et les périphériques fonctionnels avec un prompt riche et contextuel sans mentionner de jargon technique.
2. **Exploration de variantes (`generate_variants`)** :
   * Générer **2 à 3 variantes esthétiques et ergonomiques contrastées**, par exemple :
     * *Direction 1 (Ex. Expressive & Tactile) :* Surfaces contrastées, relief physique prononcé, bordures affirmées, typographie ronde et chaleureuse.
     * *Direction 2 (Ex. Minimaliste & Épurée) :* Espaces aérés, géométrie pure, micro-surfaces subtiles, tons doux et naturels.
     * *Direction 3 (Ex. Dynamique & Contrastée) :* Typographie affirmée, accents vifs, micro-interactions accentuées.
3. **Extraction du Design System (`create_design_system_from_design_md` ou `apply_design_system`)** :
   * Figer les tokens harmonisés (palette de couleurs, typographie, espacements) issus de la variante retenue.

---

### Phase 3 : Définition des Tokens Contextuels (Tailwind CSS v4)

Une fois la direction artistique choisie, les tokens sont déclarés selon les capacités modernes de Tailwind CSS v4 :

1. **Espaces colorimétriques modernes (OKLCH) & Thématisation 5 Variables** :
   * Privilégier les teintes perçues de manière uniforme avec OKLCH pour garantir des contrastes parfaits.
   * **Thématisation rapide :** Définir la marque via les 5 variables clés dans `index.css` sous `@theme` (`--color-brand-primary`, `--color-brand-hover`, `--color-brand-surface`, `--color-brand-border`, `--color-brand-text`).
   * La palette émane du produit :
     * *Jeu de plateau (ex. Puissance 4) :* Bleu cobalt profond pour le châssis, rouge carmin et jaune ambre pour les pions, fond de table chaleureux.
     * *Outil de productivité / SaaS :* Fond clair respirant (`bg-slate-50`), bordures fines (`border-slate-200`), accent unique d'action (`indigo-600` ou `emerald-600`).
2. **Bibliothèque de Composants Prêts à l'Emploi (Modèle shadcn/ui)** :
   * Exploiter les primitives locales dans `web-app/src/components/` : `Badge`, `Button`, `Card`, `DataTable`, `Dialog`, `EmptyState`, `Input`, `ToastContainer`.
   * Les composants sont copiables et éditables directement sans dépendance opaque externe.
3. **La Règle des 300ms pour les Skeletons (Zéro Clignotement)** :
   * Ne jamais afficher de skeleton loader si la réponse API arrive en moins de 300ms.
   * Géré nativement par le hook `useQuery({ skeletonDelayMs: 300 })` pour éliminer les micro-sauts visuels sur les requêtes instantanées.
4. **Conteneurs réactifs & Typographie fluide** :
   * Utiliser les requêtes de conteneurs (`@container`) pour que les composants s'adaptent à leur espace parent plutôt qu'uniquement à la largeur de l'écran global.
   * Utiliser des fonctions `clamp()` ou les classes d'échelle typographique adaptative pour un rendu optimal de l'écran mobile au 4K.

---

### Phase 4 : Le Squelette Produit Complet (Wireframing First)

L'agent ne livre **jamais** un composant isolé au milieu d'une page blanche. Tout écran structure obligatoirement les 3 zones d'une application complète :

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. BARRE SUPÉRIEURE PRODUIT (Header Contextuel)                        │
│    [Logo / Identité]   [Contexte / Statut]   [Mode ▾]  [⚙] [? Règles] │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│ 2. SCÈNE CENTRALE (The Stage)                                          │
│    Espace immersif principal dimensionné pour s'intégrer dans l'écran  │
│    sans aucun scroll parasite (min-h-[calc(100vh-...)]).               │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│ 3. PÉRIPHÉRIQUES FONCTIONNELS                                          │
│    [Action Primaire]     [Actions Secondaires]     [Modales d'état]    │
└────────────────────────────────────────────────────────────────────────┘
```

#### 1. Barre Supérieure Produit
* **Identité visuelle** : Nom du produit, symbole représentatif.
* **Contexte en temps réel** : Statut actuel (ex. : « Manche 2/3 », « Tour : Rouge », « Prêt »).
* **Contrôles secondaires d'application** :
  * Sélecteur de mode (ex. : « Solo vs IA ▾ », « 2 Joueurs Local », « En ligne »).
  * Bouton d'aide / règles (`? Règles`) ouvrant une modale accessible.
  * Bouton de réglages (`⚙ Paramètres`).

#### 2. Scène Centrale (The Stage)
* Centrée verticalement et horizontalement, valorisée par un conteneur dédié.
* **Interaction directe** : Toute manipulation s'effectue sur l'objet lui-même (cliquer sur la colonne d'un plateau, glisser une carte, dessiner sur un canvas). Interdiction stricte des formulaires textes de sélection artificielle (ex. : champ texte demandant d'écrire « 4 » pour la colonne 4).
* **Prévisualisation au survol** : Retour visuel immédiat (ex. : pion semi-transparent au-dessus de la colonne survolée).

#### 3. Périphériques & Scène Non-Bloquante (Inviolabilité du Sujet d'Intérêt)
* **Positionnement inviolable des modales globales** :
  * Les modales partagées d'aide (`<dialog id="rules-modal">`, modales de confirmation destructive, conteneurs OOB) doivent être **placées dans `layout.templ` sous `<body>` et hors de `<main>`**.
  * Si une modale est placée dans la scène échangée par HTMX (`hx-swap`), chaque interaction dynamique supprime ou ferme intempestivement la modale.
* **Scène non-bloquante lors de l'achèvement d'état (Zero Obstructive Modals on State Completion)** :
  * L'état d'arrêt ou d'achèvement d'un processus (victoire de jeu, validation de commande, confirmation de paiement) ne doit **jamais recouvrir l'élément focal par une modale opaque**.
  * L'utilisateur souhaite observer, analyser et savourer l'artéfact principal (ex. la grille victorieuse avec les pièces alignées).
  * La confirmation s'intègre en **périphérie directe** (bannière haute, volet latéral, pulsation lumineuse sur les éléments clés, barre d'action secondaire) tout en laissant l'artéfact principal 100% visible et manipulable.

---

### Phase 5 : Hiérarchie d'Action Directe (Direct Manipulation vs Settings Clutter)

Chaque écran formalise une hiérarchie d'actions visuelle sans ambiguïté :

1. **Contrôle direct à la source :**
   * Tout indicateur contextuel affiché à l'écran (compte à rebours, compteur de points, statut audio, commutateur de manche) doit être **lui-même le commutateur de son propre état** (clic direct pour basculer actif/inactif, pause/reprise, sourdine/actif).
   * Reléguer une option de manipulation fréquente au fond d'un sous-menu de configuration oblige l'utilisateur à naviguer inutilement et constitue une faille ergonomique.
   * Les modales de réglages ne sont réservées qu'aux ajustements structurels rares (clés, langue, paramètres globaux).
2. **Niveaux d'actions formalisés :**
   * **Niveau 1 : Action Primaire** (1 seule par écran/état) : Saillante, contrastée, taille supérieure (`Nouvelle manche`, `Valider`).
   * **Niveau 2 : Actions Secondaires** : Boutons doux, bordures fines (`Consulter l'historique`, `Règles`).
   * **Niveau 3 : Actions Système/Destructives** : Isolées, discrètes, confirmation obligatoire (`Réinitialiser`).
   * **Niveau 4 : Manipulation Directe** : Interaction physique directe sur le composant central.

---

### Phase 6 : Obligation de Revue Visuelle Multi-Résolutions par MCP avant Déclaration de Succès

Aucune tâche d'interface ne peut être déclarée achevée sans **au moins deux captures Chrome DevTools MCP vérifiées** :

1. **Capture format bureau (1200x900)** :
   * Vérification du centrage de la scène sans scroll parasite.
   * Vérification des alignements, marges et contrastes solaires doux.
2. **Capture format mobile (390x844)** :
   * Vérification du repliement responsive des panneaux latéraux et de l'en-tête.
   * Vérification de l'accessibilité tactile (cibles de frappe d'au moins 44x44px).
   * Absence de débordement horizontal (`overflow-x`).
3. **Inspection des interactions et clics** :
   * Vérification de la cinématique des animations et des retours au survol/clic.
4. **Console d'exécution hermétique** :
   * Zéro erreur JavaScript ou ressource manquante dans les logs du navigateur.

---

## 5. Invariants Techniques & Évitement des Pièges Multiplateformes

1. **Isolation des Styles & Keyframes (`styles.go`)** :
   * Ne jamais coder de balise `<style>` brute dans un fichier `.templ` (conflit de formatage Prettier sous Windows lors de `templ fmt`).
   * Utiliser `views.CustomCSS(css)` pour injecter les keyframes gravitationnels, les ombres 3D ou les animations d'impact.
2. **Immunité aux Swaps HTMX** :
   * Les dialogues globaux résident dans `layout.templ`, hors de la cible `hx-target`.
3. **Fins de Lignes Git (`.gitattributes`)** :
   * Toujours vérifier la présence de `* text=auto eol=lf` pour éviter les faux-positifs CRLF avec Biome sous Windows.

---

## 6. Anti-patterns Absolus

- ❌ Imposer un thème sombre « gamer » ou « cyberpunk » par défaut sur un produit grand public au lieu du thème clair satiné.
- ❌ Poser des formes 2D plates sans couches z-index réelles ni cinématique physique pour un objet manufacturé.
- ❌ Recouvrir le plateau ou l'élément focal par une modale opaque lors d'une victoire ou d'une fin de processus.
- ❌ Reléguer des contrôles directs fréquents (chrono, audio, relance) dans des sous-menus de réglages distants.
- ❌ Afficher de la télémétrie décorative, des faux scores d'IA ou des métriques non décisionnelles (No Vanity Metrics).
- ❌ Clôturer une tâche d'interface sans double capture Chrome DevTools MCP (1200x900 bureau et 390x844 mobile).
- ❌ S'interdire le frontend riche React par dogmatisme alors que l'interface exige du temps réel 60 FPS, de la 3D ou un état client complexe.
- ❌ Coder une balise `<style>` brute dans un `.templ` entraînant un échec de `templ fmt` sous Windows.
- ❌ Placer un `<dialog>` global à l'intérieur d'un composant échangé par HTMX.
- ❌ Laisser un composant orphelin flotter au milieu d'une page blanche sans squelette produit.
- ❌ Mentionner la stack technique (`Go`, `HTMX`, `Templ`, `Docker`, etc.) dans une vue métier.
- ❌ Remplacer la manipulation directe d'une grille ou d'un plateau par un champ de texte de saisie.
