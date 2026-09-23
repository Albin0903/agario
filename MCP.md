# Intégration MCP (Model Context Protocol)

Ce référentiel intègre la spécification ouverte **Model Context Protocol (MCP)** pour connecter les agents d'assistance (Claude Code, Cursor, Windsurf, Antigravity) aux outils du projet.

---

## 1. Serveurs MCP configurés (`.mcp/servers.json`)

| Nom | Commande | Rôle |
| --- | --- | --- |
| **`gopls`** | `gopls -mode=stdio` | Serveur LSP Go officiel : types stricts, autocomplétion, diagnostics et refactorisations sans parser de texte brut. |
| **`Stitch`** | `StitchMCP` | Génération et exploration UI : wireframing texte-vers-UI, variantes de design contrastées, extraction de design systems. |
| **`chrome-devtools`** | `@modelcontextprotocol/server-puppeteer` | Inspection visuelle, audits de performance (Lighthouse), captures d'écran et validation des rendus HTMX/SPA. |
| **`fetch`** | `@modelcontextprotocol/server-fetch` | Extraction déterministe de documentations en ligne (Go docs, Tailwind v4, TanStack Router). |

---

## 2. Activation selon votre environnement

### VS Code / Cursor / Windsurf

Ajoutez ou liez la configuration dans `.vscode/mcp.json` ou dans les paramètres globaux de l'éditeur :

```json
{
  "mcpServers": {
    "gopls": {
      "command": "gopls",
      "args": ["-mode=stdio"]
    }
  }
}
```

### Claude Desktop / Claude Code

Copiez la section `mcpServers` dans votre fichier de configuration `claude_desktop_config.json` :

- **Windows** : `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS** : `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux** : `~/.config/Claude/claude_desktop_config.json`

### Google Antigravity / Gemini CLI

Les outils MCP sont automatiquement scannés dans votre répertoire `~/.gemini/antigravity/mcp/`.

---

## 3. Bonnes pratiques d'usage pour agents autonomes

1. **Vérification LSP avant compilation** : Utilisez `gopls` pour valider les signatures de fonctions plutôt que d'itérer à l'aveugle avec des builds successifs.
2. **Contrôle visuel du frontend** : Après toute modification de composant Templ ou React, utilisez l'outil de capture d'écran du navigateur pour attester du rendu.
3. **Zéro hallucination d'API** : En cas de doute sur une méthode tierce, déléguez la recherche au serveur `fetch` ou aux skills spécialisées.
4. **Exploration de design avec Stitch** : Avant d'implémenter une nouvelle interface, utilisez `StitchMCP` pour générer et soumettre 2 ou 3 variantes visuelles contrastées adaptées au domaine de l'application.
