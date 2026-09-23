// Package ports defines the interfaces (contracts) consumed by the core business logic.
package ports

import (
	"context"

	"github.com/albin/build/internal/core/domain"
)

// Repository defines the contract for data persistence operations on Item entities.
// Implementations must be concurrency-safe and respect context cancellation.
type Repository interface {
	// Ping verifies that the persistence layer is reachable and operational.
	Ping(ctx context.Context) error

	// Save persists a new Item. If an item with the same ID already exists,
	// it returns domain.ErrConflict.
	Save(ctx context.Context, item domain.Item) error

	// GetByID retrieves an Item by its unique ID. If not found,
	// it returns domain.ErrNotFound.
	GetByID(ctx context.Context, id string) (domain.Item, error)

	// List returns all persisted items. If no items exist,
	// it returns an empty non-nil slice ([]domain.Item{}).
	List(ctx context.Context) ([]domain.Item, error)

	// Update updates an existing Item in persistence. If the item does not exist,
	// it returns domain.ErrNotFound.
	Update(ctx context.Context, item domain.Item) error

	// Delete removes an Item by ID. If the item does not exist,
	// it returns domain.ErrNotFound.
	Delete(ctx context.Context, id string) error
}
