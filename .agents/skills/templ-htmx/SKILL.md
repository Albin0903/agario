---
name: templ-htmx
description: >
  Génère des templates Templ typés et des fragments HTMX.
  Utiliser dès qu'une tâche touche au rendu HTML côté serveur,
  aux composants Templ, ou aux interactions HTMX.
allowed-tools: Bash, Read, Write
---

# Templ + HTMX — Conventions

## Emplacement

Tous les fichiers `.templ` résident dans `internal/adapters/http/views/`.

## Structure d'un composant Templ

```templ
// internal/adapters/http/views/layout.templ
package views

templ Layout(title string) {
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
        <title>{ title }</title>
        <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    </head>
    <body>
        { children... }
    </body>
    </html>
}
```

## Données typées

Chaque template reçoit un struct Go typé — jamais de `map[string]any` :

```templ
package views

type UserCardProps struct {
    Name  string
    Email string
    Role  string
}

templ UserCard(props UserCardProps) {
    <div class="user-card">
        <h3>{ props.Name }</h3>
        <p>{ props.Email }</p>
        <span>{ props.Role }</span>
    </div>
}
```

## Fragments HTMX

Les fragments HTMX retournent du HTML partiel (pas de page complète) :

```templ
templ UserList(users []UserCardProps) {
    for _, user := range users {
        @UserCard(user)
    }
}
```

Côté handler Go :

```go
func (h *Handler) HandleUserList(w http.ResponseWriter, r *http.Request) {
    users := h.service.ListUsers(r.Context())
    props := toUserCardProps(users)
    views.UserList(props).Render(r.Context(), w)
}
```

## Attributs HTMX standards

| Attribut | Usage |
|---|---|
| `hx-get` | Requête GET vers un endpoint |
| `hx-post` | Requête POST |
| `hx-target` | Élément cible du remplacement |
| `hx-swap` | Mode de remplacement (`innerHTML`, `outerHTML`, `beforeend`) |
| `hx-trigger` | Événement déclencheur |
| `hx-indicator` | Indicateur de chargement |

## Règles strictes

1. **Zéro JavaScript inline** : Toute interaction passe par les attributs HTMX.
2. **Après modification** : Exécuter `task generate` puis `task check`.
3. **Pas de `map[string]any`** : Utiliser exclusivement des structs typés.
4. **Pas de logique métier** : Les templates ne font que de l'affichage.
5. **Styles et Keyframes (`styles.go`)** : Ne jamais coder de balise `<style>` brute dans un fichier `.templ` sous peine d'échec de `templ fmt` (conflit Prettier sous Windows). Utiliser le composant Go `views.CustomCSS(css)` de `styles.go`.
6. **Composants d'icônes modernes (`icons.templ`)** : Utiliser les composants SVG natifs (@IconHelp, @IconSettings, @IconRefresh, @IconPlay, @IconClose) pour des visuels soignés et légers sans dépendance npm.
7. **Modales globales pérennes** : Les `<dialog>` globaux (aide, paramètres) doivent résider dans `layout.templ` hors de la balise `<main>` pour ne pas être détruits ou fermés lors des swaps HTMX.
