# 07 — Bibliothèque de Composants & Design Tokens

Ce document formalise la bibliothèque de composants réutilisables (`web-app/src/components/`) et le système de design tokens (`web-app/src/index.css`, `web-app/src/theme/tokens.ts`) du socle Build.

Inspiré du modèle architectural de **shadcn/ui**, les composants sont embarqués directement dans le code source de l'application plutôt que dissimulés dans une dépendance `node_modules` figée. Cela permet aux agents d'ingénierie et aux développeurs d'inspecter, personnaliser et étendre chaque composant avec une liberté totale.

---

## 1. Principes Fondamentaux de la Bibliothèque

1. **Zéro Décalage de Mise en Page (Zero CLS) :** Tout composant disposant d'un état de chargement asynchrone est accompagné de son skeleton reproduisant strictement l'empreinte géométrique (`w-*`, `h-*`, `aspect-ratio`).
2. **La Règle des 300ms :** Aucun skeleton ne doit clignoter pour les requêtes réseau résolues en moins de 300ms (implémentée nativement dans le hook `useQuery`).
3. **Thématisation Rapide par 5 Variables :** L'identité visuelle de l'application s'adapte en modifiant exclusivement 5 variables CSS déclarées dans `@theme` (`--color-brand-primary`, `--color-brand-hover`, `--color-brand-surface`, `--color-brand-border`, `--color-brand-text`).
4. **Scène Non-Bloquante (Rule 9) :** L'achèvement d'un processus ne recouvre jamais le sujet d'intérêt par une modale opaque ; les rétroactions s'opèrent par notification périphérique (`ToastContainer`) ou bandeau dédié.
5. **Accessibilité & Invariants WCAG 2.2 / EAA 2025 :** Éléments sémantiques natifs (`<dialog>`, `<output>`), cibles tactiles minimales de 44x44px sur mobile, anneaux de focus contrastés (`focus-visible:ring-2`), et contrastes conformes aux paliers APCA.

---

## 2. Inventaire des Composants

### `Badge` (`components/Badge.tsx`)

Pastille sémantique d'état pour les entités métier.

* **Props :**
  * `variant` : `"active"` | `"pending"` | `"archived"` | `"danger"` | `"info"` | `"default"`
  * `size` : `"sm"` | `"md"`
  * `dot` : booléen (indicateur lumineux optionnel, animé en pulsation pour l'état `active`)
* **Exemple d'usage :**

  ```tsx
  <Badge variant="active" dot>Opérationnel</Badge>
  <Badge variant="pending">En attente</Badge>
  ```

---

### `Button` (`components/Button.tsx`)

Bouton interactif animé par des ressorts physiques (`motion/react`, preset `springs.snappy`).

* **Props :**
  * `variant` : `"primary"` | `"secondary"` | `"ghost"` | `"destructive"` | `"link"`
  * `size` : `"xs"` | `"sm"` | `"md"` | `"lg"` | `"icon"`
  * `disabled` : booléen
* **Exemple d'usage :**

  ```tsx
  <Button variant="primary" size="md" onClick={handleSave}>
    <Plus className="w-4 h-4 mr-1.5" />
    <span>Enregistrer</span>
  </Button>
  ```

---

### `Card` (`components/Card.tsx`)

Surface de contenu satinée avec bordure délimitante et élévation solaire.

* **Props :**
  * `stage` : booléen (active le mode scène centrale avec ombres portées profondes)
  * `compact` : booléen (réduit les marges internes pour les tableaux de bord denses)
  * `interactive` : booléen (ajoute un effet tactile au survol et au clic)
  * `highlighted` : booléen (ajoute une lueur d'accentuation de marque)
* **Exemple d'usage :**

  ```tsx
  <Card interactive onClick={() => selectProject(project.id)}>
    <h3 className="font-semibold text-slate-900">{project.name}</h3>
    <p className="text-xs text-slate-500 mt-1">{project.summary}</p>
  </Card>
  ```

---

### `Input` (`components/Input.tsx`)

Champ de formulaire accessible garantissant la visibilité permanente du label (anti-abandon Baymard).

* **Props :**
  * `label` : libellé visible au-dessus du champ
  * `error` : message d'erreur de validation (teinte rose contrastée)
  * `helperText` : texte d'aide contextuel
* **Exemple d'usage :**

  ```tsx
  <Input
    label="Nom du produit"
    placeholder="Ex: Clavier ergonomique"
    value={name}
    onChange={(e) => setName(e.target.value)}
    error={errors.name}
    required
  />
  ```

---

### `Dialog` (`components/Dialog.tsx`)

Modale accessible native construite sur `<motion.dialog>` avec focus trap et rejet Escape.

* **Props :**
  * `open` : booléen d'affichage
  * `onClose` : fonction de fermeture
  * `title` : titre accessible (`aria-labelledby`)
  * `description` : contexte descriptif
  * `footer` : boutons d'action alignés à droite
* **Exemple d'usage :**

  ```tsx
  <Dialog
    open={showConfirm}
    onClose={() => setShowConfirm(false)}
    title="Confirmer l'archivage"
    description="Cette opération retirera le projet de la scène active."
    footer={
      <>
        <Button variant="secondary" onClick={() => setShowConfirm(false)}>Annuler</Button>
        <Button variant="destructive" onClick={handleArchive}>Archiver</Button>
      </>
    }
  >
    <p className="text-xs text-slate-600">Détails complémentaires de l'élément...</p>
  </Dialog>
  ```

---

### `ToastContainer` (`components/Toast.tsx`)

Gestionnaire de notifications périphériques non bloquantes (style Linear.app).

* **Types supportés :** `"success"` | `"error"` | `"info"`
* **Sémantique :** Conteneur `<output>` accessible avec `aria-live="polite"`.
* **Exemple d'usage :**

  ```tsx
  <ToastContainer toasts={toasts} onDismiss={(id) => removeToast(id)} />
  ```

---

### `DataTable` (`components/DataTable.tsx`)

Tableau de données générique typé (`<T>`) avec tri par colonne et skeletons intégrés.

* **Props :**
  * `columns` : tableau d'objets `Column<T>` (`key`, `header`, `sortable`, `render`)
  * `data` : tableau des enregistrements typés
  * `loading` : active les lignes de skeleton géométriques
  * `keyExtractor` : fonction extrayant l'identifiant unique
* **Exemple d'usage :**

  ```tsx
  <DataTable<Item>
    columns={[
      { key: "name", header: "Nom", sortable: true },
      { key: "status", header: "Statut", render: (item) => <Badge variant={item.status}>{item.status}</Badge> },
      { key: "updated_at", header: "Mis à jour" },
    ]}
    data={items}
    loading={loading}
    keyExtractor={(item) => item.id}
  />
  ```

---

### `EmptyState` (`components/EmptyState.tsx`)

État vide explicatif évitant le rendu de pages blanches orphelines.

* **Props :**
  * `icon` : icône vectorielle illustrative
  * `title` : titre clair du statut
  * `description` : indication de l'action à mener
  * `action` : bouton CTA optionnel

---

## 3. Data Fetching Typé & Le Hook `useQuery`

Le socle fournit un client API typé (`lib/api.ts`) et un hook React sans dépendance tierce (`hooks/useQuery.ts`) :

```tsx
import { useQuery } from "./hooks/useQuery";
import { api } from "./lib/api";

function MetricsView() {
  // Respecte automatiquement la règle des 300ms et dispose d'un AbortController
  const { data, loading, showSkeleton, error, refetch } = useQuery<Metrics>("/api/metrics");

  const handleUpdate = async () => {
    await api.post("/api/metrics/refresh", { force: true });
    await refetch();
  };

  // ...
}
```

---

## 4. Personnalisation de Thème (Thématisation en 5 Variables)

Pour modifier entièrement la direction artistique d'un nouveau projet sans altérer la mécanique fonctionnelle :

Dans `web-app/src/index.css` sous `@theme` :

```css
@theme {
  /* 1. Couleur primaire de marque (boutons, focus, accents) */
  --color-brand-primary: var(--color-emerald-600);
  /* 2. Couleur de survol tactile */
  --color-brand-hover: var(--color-emerald-700);
  /* 3. Surface douce des pastilles et alertes */
  --color-brand-surface: var(--color-emerald-50);
  /* 4. Bordure délimitante subtile */
  --color-brand-border: var(--color-emerald-200);
  /* 5. Texte contrasté pour labels de marque */
  --color-brand-text: var(--color-emerald-800);
}
```

Toutes les surfaces, badges, ombres et contrastes s'alignent immédiatement sur la nouvelle identité visuelle.
