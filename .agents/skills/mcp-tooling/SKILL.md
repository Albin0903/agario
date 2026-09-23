---
name: mcp-tooling
description: >
  Configure, exploite et intègre les serveurs MCP (Model Context Protocol) pour l'assistance
  agentique : Go LSP (gopls), inspection de rendu Chrome DevTools, génération et prototypage UI (Stitch MCP),
  documentation et diagnostic conteneur. Utiliser dès qu'une tâche nécessite de brancher
  ou requêter des outils via le protocole standardisé MCP.
allowed-tools: Bash, Read, Write
---

# Guide & Spécification MCP (Model Context Protocol)

Le **Model Context Protocol (MCP)** standardise la façon dont les agents IA se connectent aux outils locaux et distants. Plutôt que de coder des intégrations propriétaires pour chaque environnement (Cursor, Claude Code, Antigravity, Windsurf, VS Code), MCP fournit un protocole JSON-RPC standardisé sur `stdio` ou `SSE`.

---

## 1. Serveurs MCP pour la stack Build

| Serveur MCP | Rôle | Cas d'usage agent |
|---|---|---|
| **`gopls-mcp-server`** | Analyse statique Go & LSP | Navigation de symboles, complétion de types, renommage sécurisé sans grep manuel. |
| **`StitchMCP`** | Génération UI & Exploration de Design | Création de wireframes, génération d'écrans texte-vers-UI, exploration de variantes graphiques, extraction de design systems. |
| **`chrome-devtools-mcp`** | Rendu & inspection navigateur | Vérification visuelle, audits Lighthouse (a11y/perf), captures d'écran, inspection de logs console. |
| **`fetch-mcp`** | Documentation web sécurisée | Extraction ciblée de documentations officielles (Tailwind CSS v4, TanStack Router, Templ). |
| **`docker-mcp`** | Gestion des conteneurs | Inspection d'images, statut des builds multi-stage scratch, métriques locales. |

---

## 2. Prototypage UI & Variantes avec Stitch MCP

Pour concevoir des interfaces sur mesure adaptées au produit (sans règles hardcodées), l'agent exploite **Stitch MCP** comme banc d'essai visuel avant de générer le code :

### Outils clés de Stitch MCP
* **`create_project`** : Crée un espace de travail visuel dédié au produit.
* **`generate_screen_from_text`** : Génère un écran à partir d'un prompt décrivant l'architecture d'information (en-tête, scène centrale, périphériques).
* **`generate_variants`** : Produit 2 à 3 variantes esthétiques (ex. : néo-tactile physique, minimaliste épurée, contrastée dynamique).
* **`get_screen`** / **`list_screens`** : Récupère les métadonnées et captures de l'écran généré.
* **`create_design_system`** / **`apply_design_system`** : Extrait et applique les tokens visuels (couleurs, polices, élévations).

### Workflow de Conception Agentique
1. **Initialisation** : Créer le projet Stitch pour l'application.
2. **Génération initiale** : Décrire la scène centrale et le squelette produit dans `generate_screen_from_text`.
3. **Exploration de variantes** : Appeler `generate_variants` pour explorer 2 ou 3 pistes graphiques contrastées adaptées au domaine.
4. **Alignement utilisateur** : Présenter les options à l'utilisateur sous forme de maquettes visuelles pour validation.
5. **Implémentation** : Traduire la variante retenue en composants Go/Templ ou React avec Tailwind CSS v4.

---

## 3. Configuration standard du projet (`.mcp/servers.json`)

```json
{
  "mcpServers": {
    "gopls": {
      "command": "gopls",
      "args": ["-mode=stdio"],
      "description": "Go Language Server Protocol MCP"
    },
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
      "description": "Navigateur headless pour inspection DOM et captures"
    },
    "fetch": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-fetch"],
      "description": "Requêteur HTTP pour la documentation officielle"
    }
  }
}
```

---

## 4. Workflow de validation visuelle avec MCP (Obligation Multi-Résolutions)

Lorsqu'une interface ou une modification majeure est achevée :
1. **LSP (gopls)** : Valider les signatures et les types Go avant même de compiler.
2. **Revue visuelle obligatoire (chrome-devtools-mcp)** :
   - Naviguer sur `http://localhost:8080/` (SSR) et/ou `http://localhost:8080/app/` (SPA).
   - **Capture Bureau (1200x900)** : `resize_page(1200, 900)` puis `take_screenshot`. Valider le centrage de la scène, l'absence de scroll parasite, les contrastes doux et la hiérarchie.
   - **Capture Mobile (390x844)** : `resize_page(390, 844)` puis `take_screenshot`. Valider l'adaptation responsive, la taille des cibles tactiles (min 44x44px) et l'absence de débordement horizontal.
   - **Vérification de la console** : Exécuter `list_console_messages` pour garantir l'absence absolue d'erreurs JavaScript ou de ressources manquantes.
3. **Audit de performance & accessibilité** :
   - Vérifier les contrastes WCAG AA (> 4.5:1) et la présence d'anneaux de focus clavier (`focus-visible:ring-2`).
