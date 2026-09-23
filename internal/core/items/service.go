// Package items provides business domain orchestration for Item entities.
package items

import (
	"context"
	"fmt"
	"strings"

	"github.com/albin/build/internal/core/domain"
	"github.com/albin/build/internal/ports"
)

// Service coordinates business logic and domain rules for Item entities.
type Service struct {
	repo ports.Repository
}

// NewService instantiates a new items business service.
func NewService(repo ports.Repository) *Service {
	return &Service{repo: repo}
}

// Create generates a unique ID, builds a validated Item entity, and persists it.
func (s *Service) Create(ctx context.Context, name, description string, status domain.ItemStatus) (domain.Item, error) {
	if err := ctx.Err(); err != nil {
		return domain.Item{}, fmt.Errorf("context canceled before item creation: %w", err)
	}

	if status == "" {
		status = domain.StatusPending
	}

	id, err := domain.GenerateID()
	if err != nil {
		return domain.Item{}, fmt.Errorf("generating item id: %w", err)
	}

	item, err := domain.NewItem(id, name, description, status)
	if err != nil {
		return domain.Item{}, fmt.Errorf("validating item: %w", err)
	}

	if err := s.repo.Save(ctx, item); err != nil {
		return domain.Item{}, fmt.Errorf("persisting created item: %w", err)
	}

	return item, nil
}

// GetByID retrieves a single item by ID, validating non-empty ID invariants.
func (s *Service) GetByID(ctx context.Context, id string) (domain.Item, error) {
	if err := ctx.Err(); err != nil {
		return domain.Item{}, fmt.Errorf("context canceled before item retrieval: %w", err)
	}

	trimmedID := strings.TrimSpace(id)
	if trimmedID == "" {
		return domain.Item{}, fmt.Errorf("%w: item id cannot be empty", domain.ErrValidation)
	}

	item, err := s.repo.GetByID(ctx, trimmedID)
	if err != nil {
		return domain.Item{}, fmt.Errorf("fetching item %s: %w", trimmedID, err)
	}

	return item, nil
}

// List returns all persisted items. If no items exist, an allocated empty slice is returned.
func (s *Service) List(ctx context.Context) ([]domain.Item, error) {
	if err := ctx.Err(); err != nil {
		return nil, fmt.Errorf("context canceled before item listing: %w", err)
	}

	items, err := s.repo.List(ctx)
	if err != nil {
		return nil, fmt.Errorf("listing items: %w", err)
	}

	if items == nil {
		return []domain.Item{}, nil
	}

	return items, nil
}

// Update retrieves an existing item, applies domain mutations and state transitions, and persists the changes.
func (s *Service) Update(ctx context.Context, id, name, description string, status domain.ItemStatus) (domain.Item, error) {
	if err := ctx.Err(); err != nil {
		return domain.Item{}, fmt.Errorf("context canceled before item update: %w", err)
	}

	trimmedID := strings.TrimSpace(id)
	if trimmedID == "" {
		return domain.Item{}, fmt.Errorf("%w: item id cannot be empty", domain.ErrValidation)
	}

	existing, err := s.repo.GetByID(ctx, trimmedID)
	if err != nil {
		return domain.Item{}, fmt.Errorf("retrieving item for update: %w", err)
	}

	if err := existing.Update(name, description); err != nil {
		return domain.Item{}, fmt.Errorf("updating item fields: %w", err)
	}

	if status != "" && status != existing.Status {
		if err := existing.ChangeStatus(status); err != nil {
			return domain.Item{}, fmt.Errorf("changing item status: %w", err)
		}
	}

	if err := s.repo.Update(ctx, existing); err != nil {
		return domain.Item{}, fmt.Errorf("persisting updated item: %w", err)
	}

	return existing, nil
}

// Delete removes an item by ID, validating non-empty ID constraints.
func (s *Service) Delete(ctx context.Context, id string) error {
	if err := ctx.Err(); err != nil {
		return fmt.Errorf("context canceled before item deletion: %w", err)
	}

	trimmedID := strings.TrimSpace(id)
	if trimmedID == "" {
		return fmt.Errorf("%w: item id cannot be empty", domain.ErrValidation)
	}

	if err := s.repo.Delete(ctx, trimmedID); err != nil {
		return fmt.Errorf("deleting item %s: %w", trimmedID, err)
	}

	return nil
}
