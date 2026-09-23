"""Unit tests for SeedHandler authentic domain entities generation."""

from worker_python.handlers.seed import SeedHandler


def test_generate_items_ecommerce_domain() -> None:
    """Verify generation of realistic e-commerce products with prices and categories."""
    items = SeedHandler.generate_items(domain="ecommerce", count=3)
    assert len(items) == 3
    for item in items:
        assert "name" in item
        assert "price" in item
        assert item["price"] > 0
        assert "category" in item
        assert "lorem ipsum" not in item["description"].lower()


def test_generate_items_saas_domain() -> None:
    """Verify generation of realistic SaaS engineering projects."""
    items = SeedHandler.generate_items(domain="saas", count=4)
    assert len(items) == 4
    for item in items:
        assert "name" in item
        assert "status" in item
        assert item["status"] in ("active", "pending", "archived")
        assert len(item["description"]) > 10


def test_generate_users_pool() -> None:
    """Verify generation of authentic user profiles with valid emails and business roles."""
    users = SeedHandler.generate_users(count=5)
    assert len(users) == 5
    for user in users:
        assert "@" in user["email"]
        assert "name" in user
        assert "role" in user

