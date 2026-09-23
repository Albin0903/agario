// Package memory provides a thread-safe in-memory implementation of the ports.Repository interface.
package memory

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"sync"
	"time"

	"github.com/albin/build/internal/core/domain"
	"github.com/albin/build/internal/ports"
)

// Ensure Repository implements ports.Repository at compile time.
var _ ports.Repository = (*Repository)(nil)

// Repository provides a thread-safe, in-memory store for domain.Item entities.
// Access synchronization is governed by a sync.RWMutex.
type Repository struct {
	mu    sync.RWMutex
	items map[string]domain.Item
}

// New creates an empty, ready-to-use in-memory repository.
func New() *Repository {
	return &Repository{
		items: make(map[string]domain.Item),
	}
}

// NewMemoryRepository provides a constructor alias matching the PROJECT.md architectural specification.
func NewMemoryRepository() *Repository {
	return New()
}

// NewWithSeed creates an in-memory repository pre-populated with authentic seed items.
func NewWithSeed(items ...domain.Item) *Repository {
	repo := New()
	for _, item := range items {
		if item.ID != "" {
			repo.items[item.ID] = item
		}
	}
	return repo
}

// Ping verifies the operational readiness of the in-memory repository.
// It checks context liveness and confirms that internal map structures are allocated.
func (r *Repository) Ping(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return fmt.Errorf("storage ping canceled: %w", err)
	}

	r.mu.RLock()
	defer r.mu.RUnlock()

	if err := ctx.Err(); err != nil {
		return fmt.Errorf("context canceled while acquiring read lock: %w", err)
	}

	if r.items == nil {
		return errors.New("storage uninitialized: items map is nil")
	}

	return nil
}

// Save persists a new domain.Item into memory.
// It returns domain.ErrConflict if an item with the same ID already exists,
// or domain.ErrValidation if the item ID is empty.
func (r *Repository) Save(ctx context.Context, item domain.Item) error {
	if err := ctx.Err(); err != nil {
		return fmt.Errorf("context canceled before save: %w", err)
	}

	if item.ID == "" {
		return fmt.Errorf("cannot save item with empty id: %w", domain.ErrValidation)
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	if err := ctx.Err(); err != nil {
		return fmt.Errorf("context canceled while acquiring write lock: %w", err)
	}

	if _, exists := r.items[item.ID]; exists {
		return fmt.Errorf("item with id %q already exists: %w", item.ID, domain.ErrConflict)
	}

	r.items[item.ID] = item
	return nil
}

// GetByID retrieves a domain.Item by its unique identifier.
// It returns domain.ErrNotFound if the requested item does not exist,
// or domain.ErrValidation if the requested ID is empty.
func (r *Repository) GetByID(ctx context.Context, id string) (domain.Item, error) {
	if err := ctx.Err(); err != nil {
		return domain.Item{}, fmt.Errorf("context canceled before get: %w", err)
	}

	if id == "" {
		return domain.Item{}, fmt.Errorf("cannot get item with empty id: %w", domain.ErrValidation)
	}

	r.mu.RLock()
	defer r.mu.RUnlock()

	if err := ctx.Err(); err != nil {
		return domain.Item{}, fmt.Errorf("context canceled while acquiring read lock: %w", err)
	}

	item, exists := r.items[id]
	if !exists {
		return domain.Item{}, fmt.Errorf("item with id %q: %w", id, domain.ErrNotFound)
	}

	return item, nil
}

// List returns all persisted domain.Item records, deterministically sorted
// by CreatedAt descending with ID ascending as a secondary tie-breaker.
// If the store is empty, it returns an allocated empty slice to guarantee uniform JSON array serialization.
func (r *Repository) List(ctx context.Context) ([]domain.Item, error) {
	if err := ctx.Err(); err != nil {
		return nil, fmt.Errorf("context canceled before list: %w", err)
	}

	r.mu.RLock()
	defer r.mu.RUnlock()

	if err := ctx.Err(); err != nil {
		return nil, fmt.Errorf("context canceled while acquiring read lock: %w", err)
	}

	result := make([]domain.Item, 0, len(r.items))
	for _, item := range r.items {
		result = append(result, item)
	}

	// Deterministic sorting: newest first, fallback to lexicographical ID.
	sort.Slice(result, func(i, j int) bool {
		if !result[i].CreatedAt.Equal(result[j].CreatedAt) {
			return result[i].CreatedAt.After(result[j].CreatedAt)
		}
		return result[i].ID < result[j].ID
	})

	return result, nil
}

// Update replaces an existing domain.Item record in memory.
// It returns domain.ErrNotFound if the item does not exist,
// or domain.ErrValidation if the item ID is empty.
func (r *Repository) Update(ctx context.Context, item domain.Item) error {
	if err := ctx.Err(); err != nil {
		return fmt.Errorf("context canceled before update: %w", err)
	}

	if item.ID == "" {
		return fmt.Errorf("cannot update item with empty id: %w", domain.ErrValidation)
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	if err := ctx.Err(); err != nil {
		return fmt.Errorf("context canceled while acquiring write lock: %w", err)
	}

	if _, exists := r.items[item.ID]; !exists {
		return fmt.Errorf("item with id %q not found for update: %w", item.ID, domain.ErrNotFound)
	}

	r.items[item.ID] = item
	return nil
}

// Delete removes an item by its unique identifier.
// It returns domain.ErrNotFound if the item does not exist,
// or domain.ErrValidation if the requested ID is empty.
func (r *Repository) Delete(ctx context.Context, id string) error {
	if err := ctx.Err(); err != nil {
		return fmt.Errorf("context canceled before delete: %w", err)
	}

	if id == "" {
		return fmt.Errorf("cannot delete item with empty id: %w", domain.ErrValidation)
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	if err := ctx.Err(); err != nil {
		return fmt.Errorf("context canceled while acquiring write lock: %w", err)
	}

	if _, exists := r.items[id]; !exists {
		return fmt.Errorf("item with id %q not found for delete: %w", id, domain.ErrNotFound)
	}

	delete(r.items, id)
	return nil
}

// Seed atomically populates or resets the repository with the provided items.
func (r *Repository) Seed(ctx context.Context, items ...domain.Item) error {
	if err := ctx.Err(); err != nil {
		return fmt.Errorf("context canceled before seed: %w", err)
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	if err := ctx.Err(); err != nil {
		return fmt.Errorf("context canceled while acquiring write lock: %w", err)
	}

	for _, item := range items {
		if item.ID != "" {
			r.items[item.ID] = item
		}
	}
	return nil
}

// DefaultSeedItems generates an authentic initial dataset of software engineering initiatives.
// This fulfills R3 by eliminating placeholder text.
func DefaultSeedItems() []domain.Item {
	baseTime := time.Date(2026, time.September, 12, 8, 0, 0, 0, time.UTC)
	return []domain.Item{
		{
			ID:          "item-spring-physics",
			Name:        "Calibrate spring physics presets",
			Description: "Tune stiffness (k=400) and damping (c=30) coefficients for tactile button micro-interactions.",
			Status:      domain.StatusActive,
			CreatedAt:   baseTime.Add(-4 * time.Hour),
			UpdatedAt:   baseTime.Add(-3 * time.Hour),
		},
		{
			ID:          "item-apca-contrast",
			Name:        "Audit APCA contrast across theme levels",
			Description: "Verify typography lightness contrast exceeds Lc 75 for body text on Radix level 1-2 surfaces.",
			Status:      domain.StatusCompleted,
			CreatedAt:   baseTime.Add(-3 * time.Hour),
			UpdatedAt:   baseTime.Add(-1 * time.Hour),
		},
		{
			ID:          "item-cls-skeletons",
			Name:        "Implement zero-shift loading skeletons",
			Description: "Match exact bounding boxes and aspect ratios of card elements to prevent layout reflow during initial fetch.",
			Status:      domain.StatusActive,
			CreatedAt:   baseTime.Add(-2 * time.Hour),
			UpdatedAt:   baseTime.Add(-30 * time.Minute),
		},
		{
			ID:          "item-hexagonal-core",
			Name:        "Structure hexagonal core boundary gates",
			Description: "Ensure pure domain isolation and consumer-owned port contracts with strict context propagation.",
			Status:      domain.StatusCompleted,
			CreatedAt:   baseTime.Add(-5 * time.Hour),
			UpdatedAt:   baseTime.Add(-2 * time.Hour),
		},
		{
			ID:          "item-telemetry-cleanup",
			Name:        "Eliminate decorative implementation telemetry",
			Description: "Remove technology stack names and non-actionable vanity counters from user-facing screens.",
			Status:      domain.StatusPending,
			CreatedAt:   baseTime.Add(-1 * time.Hour),
			UpdatedAt:   baseTime.Add(-10 * time.Minute),
		},
	}
}
