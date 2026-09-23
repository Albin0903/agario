---
name: htmx-ui-patterns
description: >
  Implémente des patterns d'interface avancés avec HTMX et Templ (recherche en direct,
  pagination infinie, modales accessibles, validation temps réel, notifications toast,
  swaps out-of-band). Utiliser pour concevoir des interactions dynamiques côté serveur.
allowed-tools: Bash, Read, Write
---

# HTMX UI Patterns — Interactions Serveur Avancées

## 1. Recherche en direct (Active Search avec Debounce)

Permet de filtrer une liste de résultats à chaque frappe clavier sans bloquer le thread principal :

```templ
templ SearchInput() {
    <div class="relative">
        <input
            type="search"
            name="q"
            placeholder="Rechercher un service..."
            hx-get="/api/services/search"
            hx-trigger="input changed delay:300ms, search"
            hx-target="#search-results"
            hx-indicator="#search-spinner"
            class="w-full rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none shadow-xs"
        />
        <div id="search-spinner" class="htmx-indicator absolute right-3 top-2.5 text-indigo-600">
            <span class="animate-spin inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full"></span>
        </div>
    </div>
    <div id="search-results" class="mt-4 space-y-2">
        <!-- Rendu dynamique par le serveur -->
    </div>
}
```

---

## 2. Validation de formulaire en temps réel (Inline Validation)

Chaque champ est validé côté serveur à la perte de focus (`blur`) :

```templ
templ UsernameField(value string, errorMessage string) {
    <div class="space-y-1">
        <label for="username" class="block text-xs font-mono uppercase text-slate-600">Nom d'utilisateur</label>
        <input
            id="username"
            name="username"
            type="text"
            value={ value }
            hx-post="/api/validate/username"
            hx-trigger="blur"
            hx-target="closest div"
            hx-swap="outerHTML"
            class="w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-900 shadow-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none"
        />
        if errorMessage != "" {
            <p class="text-xs text-rose-600 font-medium">{ errorMessage }</p>
        }
    </div>
}
```

---

## 3. Notification Toast via Swaps Out-of-Band (`hx-swap-oob`)

Permet de mettre à jour le contenu principal tout en injectant une alerte dans le conteneur global de toasts :

```templ
// Le handler retourne le fragment principal + le fragment OOB
templ SaveItemResponse(item Item) {
    <tr id={ "item-" + item.ID }>
        <td>{ item.Name }</td>
        <td>{ item.Status }</td>
    </tr>
    <!-- Toast injecté hors du target principal -->
    <div id="toast-container" hx-swap-oob="beforeend">
        <div class="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-emerald-800 text-xs shadow-md animate-fade-in flex items-center justify-between">
            <span>Élément enregistré avec succès !</span>
        </div>
    </div>
}
```

---

## 4. Modale de confirmation accessible

```templ
templ DeleteConfirmModal(itemID string) {
    <div id="modal-backdrop" class="fixed inset-0 bg-slate-900/30 backdrop-blur-xs z-50 flex items-center justify-center p-4">
        <div class="rounded-2xl border border-slate-200 bg-white p-6 max-w-md w-full shadow-xl space-y-4">
            <h3 class="text-lg font-bold text-slate-900">Confirmer la suppression</h3>
            <p class="text-sm text-slate-600">Cette opération est irréversible. Voulez-vous continuer ?</p>
            <div class="flex items-center justify-end gap-3 pt-2">
                <button
                    onclick="document.getElementById('modal-backdrop').remove()"
                    class="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
                >
                    Annuler
                </button>
                <button
                    hx-delete={ "/api/items/" + itemID }
                    hx-target={ "#item-" + itemID }
                    hx-swap="outerHTML"
                    hx-on::after-request="document.getElementById('modal-backdrop').remove()"
                    class="px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-600 hover:bg-rose-700 text-white shadow-xs transition-colors"
                >
                    Supprimer définitivement
                </button>
            </div>
        </div>
    </div>
}
```

---

## 5. Règle d'or de performance HTMX

1. Toujours privilégier `hx-target` explicite pour éviter les re-rendus intempestifs de nœuds parents.
2. Utiliser `hx-push-url="true"` pour les transitions d'écran majeures afin de conserver l'historique du navigateur.
3. Toujours associer `hx-indicator` aux requêtes réseau pour un retour d'état immédiat.
