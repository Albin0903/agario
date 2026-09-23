"""Seed handler generating realistic domain data without dummy or lorem ipsum text."""

from typing import Any

ECOMMERCE_CATALOG: list[dict[str, Any]] = [
    {
        "name": "Clavier Mécanique Ergonomique Pro",
        "category": "Périphériques",
        "description": "Switches tactiles, rétroéclairage blanc chaud et châssis aluminium.",
        "status": "active",
        "price": 149.0,
    },
    {
        "name": "Souris Sans Fil Précision Optique",
        "category": "Périphériques",
        "description": "Capteur 26 000 DPI, molette électromagnétique et autonomie 70h.",
        "status": "active",
        "price": 89.0,
    },
    {
        "name": 'Écran Graphique 27" Calibré Usine',
        "category": "Affichage",
        "description": "Dalle IPS 4K HDR400, couverture 99% DCI-P3 et port USB-C 90W.",
        "status": "active",
        "price": 499.0,
    },
    {
        "name": "Casque Audio Haute Fidélité Fermé",
        "category": "Audio",
        "description": "Transducteurs 45mm néodyme, coussinets mémoire de forme et câble tressé.",
        "status": "pending",
        "price": 189.0,
    },
    {
        "name": "Lampe de Bureau Température Variable",
        "category": "Éclairage",
        "description": "Indice IRC 98, capteur de luminosité ambiante et contrôle tactile graduel.",
        "status": "active",
        "price": 79.0,
    },
]

SAAS_PROJECTS: list[dict[str, Any]] = [
    {
        "name": "Pipeline d'Analyse de Cohortes",
        "category": "Analytics",
        "description": "Agrégation horaire des événements et calcul de rétention à 30 jours.",
        "status": "active",
    },
    {
        "name": "Moteur de Recommandation Hybride",
        "category": "Intelligence Artificielle",
        "description": "Filtrage collaboratif vectoriel avec ré-ordonnancement sub-50ms.",
        "status": "active",
    },
    {
        "name": "Indexation de Documents Vectoriels",
        "category": "Recherche",
        "description": "Génération d'embeddings et partitionnement HNSW pour recherche sémantique.",
        "status": "pending",
    },
    {
        "name": "Orchestrateur de Déploiement Multi-Cloud",
        "category": "Infrastructure",
        "description": "Provisionnement déclaratif Terraform et surveillance des SLAs de service.",
        "status": "active",
    },
    {
        "name": "Passerelle de Télémétrie Sécurisée",
        "category": "Sécurité",
        "description": "Collecte mTLS des métriques d'agents et détection temps réel d'anomalies.",
        "status": "archived",
    },
]

CRM_ACCOUNTS: list[dict[str, Any]] = [
    {
        "name": "Nexora Solutions SARL",
        "category": "Entreprise",
        "description": "Contrat de maintenance et support dédié 24/7 sur cluster Kubernetes.",
        "status": "active",
    },
    {
        "name": "Atelier Digital Méditerranée",
        "category": "PME",
        "description": "Migration d'infrastructure sur site vers architecture conteneurisée.",
        "status": "pending",
    },
    {
        "name": "Laboratoire Biomédical Lumière",
        "category": "Santé",
        "description": "Conformité HDS et audit de sécurité des flux de données de diagnostic.",
        "status": "active",
    },
    {
        "name": "Logistique Urbaine Rapide",
        "category": "Transport",
        "description": "Optimisation algorithmique des tournées de livraison du dernier kilomètre.",
        "status": "active",
    },
]

USERS_POOL: list[dict[str, Any]] = [
    {"name": "Camille Bernard", "email": "c.bernard@example.org", "role": "Architecte Produit"},
    {"name": "Alexandre Mercier", "email": "a.mercier@example.org", "role": "Ingénieur Backend"},
    {"name": "Éléonore Faure", "email": "e.faure@example.org", "role": "Designer UX/UI"},
    {"name": "Thomas Gauthier", "email": "t.gauthier@example.org", "role": "Responsable DevOps"},
    {"name": "Inès Caron", "email": "i.caron@example.org", "role": "Data Scientist"},
]


class SeedHandler:
    """Generates coherent domain entities to avoid lorem ipsum and synthetic artifacts."""

    @staticmethod
    def generate_items(domain: str = "saas", count: int = 5) -> list[dict[str, Any]]:
        """Return a slice of authentic items tailored to the requested domain."""
        norm_domain = domain.strip().lower()
        source: list[dict[str, Any]]
        if norm_domain in ("ecommerce", "e-commerce", "shop", "store"):
            source = ECOMMERCE_CATALOG
        elif norm_domain in ("crm", "sales", "clients"):
            source = CRM_ACCOUNTS
        else:
            source = SAAS_PROJECTS

        results: list[dict[str, Any]] = []
        for i in range(max(1, count)):
            template = source[i % len(source)].copy()
            if i >= len(source):
                template["name"] = f"{template['name']} #{i + 1}"
            results.append(template)

        return results

    @staticmethod
    def generate_users(count: int = 5) -> list[dict[str, Any]]:
        """Return a list of realistic user accounts with genuine names and business roles."""
        results: list[dict[str, Any]] = []
        for i in range(max(1, count)):
            user = USERS_POOL[i % len(USERS_POOL)].copy()
            if i >= len(USERS_POOL):
                user["email"] = f"user_{i + 1}@example.org"
            results.append(user)

        return results
