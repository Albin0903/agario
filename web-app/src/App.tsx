import {
  Link,
  Outlet,
  RouterProvider,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import {
  Activity,
  ArrowUpRight,
  CheckCircle2,
  FolderOpen,
  LayoutDashboard,
  Plus,
  RefreshCw,
  Sliders,
  Sparkles,
  Trash2,
} from "lucide-react";
import type React from "react";
import { useState } from "react";
import {
  Badge,
  Button,
  Card,
  Dialog,
  EmptyState,
  Input,
  InteractiveSwitch,
  SkeletonCard,
  SkeletonRow,
  ToastContainer,
  type ToastItem,
} from "./components";
import { useQuery } from "./hooks/useQuery";
import { api } from "./lib/api";

// External API types
interface HealthStatus {
  ok: boolean;
  status: string;
  uptime: string;
  timestamp: string;
}

interface Item {
  id: string;
  name: string;
  description: string;
  status: "active" | "pending" | "archived";
  created_at: string;
  updated_at: string;
}

// 1. Root Route
const rootRoute = createRootRoute({
  component: RootComponent,
});

function RootComponent(): React.JSX.Element {
  const [systemActive, setSystemActive] = useState<boolean>(true);

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900 font-sans">
      <header className="border-b border-slate-200/80 bg-white/90 backdrop-blur sticky top-0 z-50 shadow-xs">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-sm shadow-md shadow-indigo-500/20">
              A
            </div>
            <div>
              <span className="font-bold text-sm text-slate-900 tracking-tight">
                Console Applicative
              </span>
              <span className="ml-2 text-xs font-mono uppercase bg-indigo-50 text-indigo-700 border border-indigo-200/80 px-1.5 py-0.5 rounded font-medium">
                Interactive
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <InteractiveSwitch
              active={systemActive}
              onToggle={() => setSystemActive((prev) => !prev)}
              activeLabel="Système Actif"
              inactiveLabel="En Pause"
            />

            <nav className="flex items-center gap-2 text-sm">
              <Link
                to="/"
                className="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors [&.active]:bg-indigo-50 [&.active]:text-indigo-700 [&.active]:font-semibold font-medium text-xs flex items-center gap-1.5"
              >
                <LayoutDashboard className="w-3.5 h-3.5" />
                <span>Tableau de bord</span>
              </Link>
              <Link
                to="/workspace"
                className="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors [&.active]:bg-indigo-50 [&.active]:text-indigo-700 [&.active]:font-semibold font-medium text-xs flex items-center gap-1.5"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Espace de travail</span>
              </Link>
              <Link
                to="/settings"
                className="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors [&.active]:bg-indigo-50 [&.active]:text-indigo-700 [&.active]:font-semibold font-medium text-xs flex items-center gap-1.5"
              >
                <Sliders className="w-3.5 h-3.5" />
                <span>Paramètres</span>
              </Link>
              <a
                href="/"
                className="ml-2 px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 text-xs font-medium flex items-center gap-1 border border-slate-200 hover:border-slate-300 bg-white shadow-xs transition-colors"
              >
                <span>Vue Standard</span>
                <ArrowUpRight className="w-3 h-3" />
              </a>
            </nav>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200/80 py-6 text-center text-xs text-slate-500 bg-white/60">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-2">
          <p>Console Applicative — Espace de gestion et d'interaction.</p>
          <p className="text-slate-400">Environnement Client Haute Réactivité</p>
        </div>
      </footer>
    </div>
  );
}

// 2. Index / Dashboard Route
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: DashboardComponent,
});

function DashboardComponent(): React.JSX.Element {
  const {
    data: health,
    loading,
    showSkeleton,
    error,
    refetch,
  } = useQuery<HealthStatus>("/api/health");

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Tableau de bord</h1>
          <p className="text-sm text-slate-600">
            Vue d'ensemble de l'activité, des sessions et de la disponibilité du service.
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => void refetch()} disabled={loading}>
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Actualiser l'état</span>
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {loading && showSkeleton ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : (
          <>
            <Card>
              <div className="flex items-center justify-between text-slate-500">
                <span className="text-xs uppercase font-medium tracking-wider">
                  État du Service
                </span>
                <Activity className="w-4 h-4 text-emerald-600" />
              </div>
              {error && <p className="text-rose-600 text-xs font-mono mt-2">{error}</p>}
              {health && (
                <div className="mt-3">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                    <span className="text-lg font-bold text-slate-900">{health.status}</span>
                  </div>
                  <p className="text-xs text-slate-500 font-mono mt-1">
                    Actif depuis : {health.uptime}
                  </p>
                </div>
              )}
            </Card>

            <Card>
              <div className="flex items-center justify-between text-slate-500">
                <span className="text-xs uppercase font-medium tracking-wider">
                  Session Utilisateur
                </span>
                <CheckCircle2 className="w-4 h-4 text-indigo-600" />
              </div>
              <div className="mt-3">
                <span className="text-lg font-bold text-slate-900">Session Active</span>
                <p className="text-xs text-slate-500 mt-1">
                  Prêt pour les interactions haute fréquence
                </p>
              </div>
            </Card>

            <Card>
              <div className="flex items-center justify-between text-slate-500">
                <span className="text-xs uppercase font-medium tracking-wider">
                  Disponibilité Globale
                </span>
                <span className="text-xs font-semibold text-emerald-700">100 %</span>
              </div>
              <div className="mt-3">
                <span className="text-lg font-bold text-slate-900">Nominale</span>
                <p className="text-xs text-slate-500 mt-1">Tous les sous-systèmes répondent</p>
              </div>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}

// 3. Workspace Route (The Stage for rich interactions with genuine domain items)
const workspaceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/workspace",
  component: WorkspaceComponent,
});

function WorkspaceComponent(): React.JSX.Element {
  const { data: fetchedItems, loading, showSkeleton, refetch } = useQuery<Item[]>("/api/items");
  const [localItems, setLocalItems] = useState<Item[] | null>(null);
  const items = localItems ?? fetchedItems ?? [];

  const [newItemName, setNewItemName] = useState<string>("");
  const [newItemDesc, setNewItemDesc] = useState<string>("");
  const [creating, setCreating] = useState<boolean>(false);

  // Modal dialog state for deletion confirmation
  const [deleteTarget, setDeleteTarget] = useState<Item | null>(null);
  const [deleting, setDeleting] = useState<boolean>(false);

  // Toast notification state
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = (type: "success" | "error" | "info", title: string, message?: string): void => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setToasts((prev) => [...prev, { id, type, title, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  };

  const handleDismissToast = (id: string): void => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const handleCreateItem = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    if (!newItemName.trim()) return;

    setCreating(true);
    try {
      const created = await api.post<Item>("/api/items", {
        name: newItemName.trim(),
        description: newItemDesc.trim(),
        status: "active",
      });

      setLocalItems([created, ...items]);
      setNewItemName("");
      setNewItemDesc("");
      addToast("success", "Entité créée", `L'entité "${created.name}" a été enregistrée.`);
    } catch {
      addToast("error", "Échec de création", "Impossible d'enregistrer l'entité.");
    } finally {
      setCreating(false);
    }
  };

  const handleConfirmDelete = async (): Promise<void> => {
    if (!deleteTarget) return;

    setDeleting(true);
    try {
      await api.delete(`/api/items/${deleteTarget.id}`);
      setLocalItems(items.filter((item) => item.id !== deleteTarget.id));
      addToast("info", "Entité supprimée", `L'entité "${deleteTarget.name}" a été retirée.`);
      setDeleteTarget(null);
    } catch {
      addToast("error", "Échec de suppression", "Impossible de supprimer l'élément.");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Peripheral Toast Notifications */}
      <ToastContainer toasts={toasts} onDismiss={handleDismissToast} />

      {/* Confirmation Dialog for deletion */}
      <Dialog
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Confirmer la suppression"
        description="Cette action est irréversible. L'entité sera définitivement retirée du système."
        footer={
          <>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setDeleteTarget(null)}
              disabled={deleting}
            >
              Annuler
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => void handleConfirmDelete()}
              disabled={deleting}
            >
              {deleting ? "Suppression..." : "Supprimer définitivement"}
            </Button>
          </>
        }
      >
        {deleteTarget && (
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-700">
            <span className="font-semibold">{deleteTarget.name}</span>
            {deleteTarget.description && (
              <p className="text-slate-500 mt-1">{deleteTarget.description}</p>
            )}
          </div>
        )}
      </Dialog>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Espace de travail interactif
          </h1>
          <p className="text-sm text-slate-600">
            Scène principale dédiée aux manipulations directes, aux entités métier et aux états
            réactifs.
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => void refetch()}>
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Rafraîchir</span>
        </Button>
      </div>

      <Card stage className="space-y-8">
        {/* Visual focal point: 1 prominent action form */}
        <div className="max-w-xl mx-auto space-y-4 text-center">
          <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-indigo-50 border border-indigo-200/80 text-xs text-indigo-700 font-medium">
            <span className="w-2 h-2 rounded-full bg-indigo-600 animate-pulse" />
            <span>Gestion des Entités Métier</span>
          </div>
          <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
            Création d'Activité
          </h2>
          <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
            Ajoutez et manipulez des données réelles directement connectées à l'architecture
            hexagonale.
          </p>

          <form
            onSubmit={(e) => void handleCreateItem(e)}
            className="flex flex-col sm:flex-row gap-3 pt-2 text-left"
          >
            <div className="flex-1">
              <Input
                label="Nom de l'entité"
                placeholder="Ex: Analyse de cohortes..."
                value={newItemName}
                onChange={(e) => setNewItemName(e.target.value)}
                required
              />
            </div>
            <div className="flex-1">
              <Input
                label="Description"
                placeholder="Optionnelle..."
                value={newItemDesc}
                onChange={(e) => setNewItemDesc(e.target.value)}
              />
            </div>
            <div className="sm:self-end pt-1">
              <Button
                type="submit"
                variant="primary"
                size="md"
                disabled={creating || !newItemName.trim()}
              >
                <Plus className="w-4 h-4 mr-1" />
                <span>{creating ? "Ajout..." : "Créer"}</span>
              </Button>
            </div>
          </form>
        </div>

        {/* Real Domain Entities List with Zero-CLS Skeleton Loading */}
        <div className="max-w-2xl mx-auto space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-500 font-medium px-1">
            <span>Entités enregistrées ({items.length})</span>
            <span>Statut opérationnel</span>
          </div>

          {loading && showSkeleton && items.length === 0 ? (
            <div className="space-y-2">
              <SkeletonRow />
              <SkeletonRow />
              <SkeletonRow />
            </div>
          ) : items.length === 0 ? (
            <EmptyState
              icon={<FolderOpen className="w-6 h-6" />}
              title="Aucune entité pour le moment"
              description="Utilisez le formulaire ci-dessus pour initialiser la première entité du domaine."
            />
          ) : (
            <div className="space-y-2">
              {items.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between p-4 rounded-xl border border-slate-200 bg-white hover:border-slate-300 transition-colors shadow-xs"
                >
                  <div className="space-y-0.5 text-left">
                    <span className="font-semibold text-sm text-slate-900">{item.name}</span>
                    {item.description && (
                      <p className="text-xs text-slate-500">{item.description}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge
                      variant={
                        item.status === "active"
                          ? "active"
                          : item.status === "pending"
                            ? "pending"
                            : "archived"
                      }
                      dot={item.status === "active"}
                    >
                      {item.status}
                    </Badge>
                    <button
                      type="button"
                      onClick={() => setDeleteTarget(item)}
                      className="text-slate-400 hover:text-rose-600 p-1.5 rounded-md transition-colors cursor-pointer"
                      title="Supprimer"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

// 4. Settings Route
const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: SettingsComponent,
});

function SettingsComponent(): React.JSX.Element {
  const [compactMode, setCompactMode] = useState<boolean>(false);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Paramètres</h1>
        <p className="text-sm text-slate-600">
          Ajustements structurels et préférences d'affichage de la console.
        </p>
      </div>

      <Card className="space-y-4">
        <div className="flex items-center justify-between py-2 border-b border-slate-100">
          <div>
            <span className="font-medium text-sm text-slate-900">Actualisation automatique</span>
            <p className="text-xs text-slate-500">
              Rafraîchir les métriques d'état à intervalles réguliers
            </p>
          </div>
          <InteractiveSwitch
            active={autoRefresh}
            onToggle={() => setAutoRefresh((prev) => !prev)}
            activeLabel="Activé"
            inactiveLabel="Manuel"
          />
        </div>

        <div className="flex items-center justify-between py-2">
          <div>
            <span className="font-medium text-sm text-slate-900">Affichage compact</span>
            <p className="text-xs text-slate-500">
              Réduire les marges et la hauteur des cartes pour les vues denses
            </p>
          </div>
          <InteractiveSwitch
            active={compactMode}
            onToggle={() => setCompactMode((prev) => !prev)}
            activeLabel="Compact"
            inactiveLabel="Confort"
          />
        </div>
      </Card>
    </div>
  );
}

// 5. Router instantiation
const routeTree = rootRoute.addChildren([indexRoute, workspaceRoute, settingsRoute]);

const router = createRouter({
  routeTree,
  basepath: "/app",
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

export function App(): React.JSX.Element {
  return <RouterProvider router={router} />;
}

export default App;
