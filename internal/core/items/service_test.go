package items_test

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/albin/build/internal/core/domain"
	"github.com/albin/build/internal/core/items"
	"github.com/albin/build/internal/ports"
)

type mockRepository struct {
	pingFn    func(ctx context.Context) error
	saveFn    func(ctx context.Context, item domain.Item) error
	getByIDFn func(ctx context.Context, id string) (domain.Item, error)
	listFn    func(ctx context.Context) ([]domain.Item, error)
	updateFn  func(ctx context.Context, item domain.Item) error
	deleteFn  func(ctx context.Context, id string) error
}

var _ ports.Repository = (*mockRepository)(nil)

func (m *mockRepository) Ping(ctx context.Context) error {
	if m.pingFn != nil {
		return m.pingFn(ctx)
	}
	return nil
}

func (m *mockRepository) Save(ctx context.Context, item domain.Item) error {
	if m.saveFn != nil {
		return m.saveFn(ctx, item)
	}
	return nil
}

func (m *mockRepository) GetByID(ctx context.Context, id string) (domain.Item, error) {
	if m.getByIDFn != nil {
		return m.getByIDFn(ctx, id)
	}
	return domain.Item{}, domain.ErrNotFound
}

func (m *mockRepository) List(ctx context.Context) ([]domain.Item, error) {
	if m.listFn != nil {
		return m.listFn(ctx)
	}
	return []domain.Item{}, nil
}

func (m *mockRepository) Update(ctx context.Context, item domain.Item) error {
	if m.updateFn != nil {
		return m.updateFn(ctx, item)
	}
	return nil
}

func (m *mockRepository) Delete(ctx context.Context, id string) error {
	if m.deleteFn != nil {
		return m.deleteFn(ctx, id)
	}
	return nil
}

func TestService_Create(t *testing.T) {
	t.Parallel()

	tests := map[string]struct {
		name        string
		description string
		status      domain.ItemStatus
		ctxFn       func() (context.Context, context.CancelFunc)
		mockRepo    *mockRepository
		wantErr     bool
		errTarget   error
	}{
		"successful creation with default status": {
			name:        "Hexagonal Port",
			description: "Implement port contracts",
			status:      "",
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			mockRepo: &mockRepository{
				saveFn: func(_ context.Context, item domain.Item) error {
					if item.Status != domain.StatusPending {
						t.Errorf("item.Status = %v, want %v", item.Status, domain.StatusPending)
					}
					return nil
				},
			},
			wantErr: false,
		},
		"empty name returns validation error": {
			name:        "   ",
			description: "Some desc",
			status:      domain.StatusActive,
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			mockRepo:  &mockRepository{},
			wantErr:   true,
			errTarget: domain.ErrValidation,
		},
		"repository conflict error propagated": {
			name:        "Conflict Item",
			description: "Triggers duplicate",
			status:      domain.StatusPending,
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			mockRepo: &mockRepository{
				saveFn: func(_ context.Context, _ domain.Item) error {
					return domain.ErrConflict
				},
			},
			wantErr:   true,
			errTarget: domain.ErrConflict,
		},
		"canceled context returns error": {
			name:        "Canceled Item",
			description: "Context is canceled",
			status:      domain.StatusPending,
			ctxFn: func() (context.Context, context.CancelFunc) {
				ctx, cancel := context.WithCancel(context.Background())
				cancel()
				return ctx, cancel
			},
			mockRepo: &mockRepository{},
			wantErr:  true,
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			ctx, cancel := tt.ctxFn()
			defer cancel()

			svc := items.NewService(tt.mockRepo)
			created, err := svc.Create(ctx, tt.name, tt.description, tt.status)

			if tt.wantErr {
				if err == nil {
					t.Fatalf("Create() expected error, got nil")
				}
				if tt.errTarget != nil && !errors.Is(err, tt.errTarget) {
					t.Errorf("Create() error = %v, want target %v", err, tt.errTarget)
				}
				return
			}

			if err != nil {
				t.Fatalf("Create() unexpected error = %v", err)
			}

			if created.ID == "" {
				t.Error("Create() item ID should not be empty")
			}
			if created.Name != tt.name {
				t.Errorf("created.Name = %q, want %q", created.Name, tt.name)
			}
		})
	}
}

func TestService_GetByID(t *testing.T) {
	t.Parallel()

	existing := domain.Item{
		ID:          "item-get",
		Name:        "Retrieve Me",
		Description: "Target item",
		Status:      domain.StatusActive,
		CreatedAt:   time.Now().UTC(),
		UpdatedAt:   time.Now().UTC(),
	}

	tests := map[string]struct {
		id        string
		ctxFn     func() (context.Context, context.CancelFunc)
		mockRepo  *mockRepository
		wantErr   bool
		errTarget error
	}{
		"successful retrieval": {
			id: "item-get",
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			mockRepo: &mockRepository{
				getByIDFn: func(_ context.Context, _ string) (domain.Item, error) {
					return existing, nil
				},
			},
			wantErr: false,
		},
		"empty id returns validation error": {
			id: "   ",
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			mockRepo:  &mockRepository{},
			wantErr:   true,
			errTarget: domain.ErrValidation,
		},
		"missing item returns not found": {
			id: "missing-id",
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			mockRepo: &mockRepository{
				getByIDFn: func(_ context.Context, _ string) (domain.Item, error) {
					return domain.Item{}, domain.ErrNotFound
				},
			},
			wantErr:   true,
			errTarget: domain.ErrNotFound,
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			ctx, cancel := tt.ctxFn()
			defer cancel()

			svc := items.NewService(tt.mockRepo)
			got, err := svc.GetByID(ctx, tt.id)

			if tt.wantErr {
				if err == nil {
					t.Fatalf("GetByID() expected error, got nil")
				}
				if tt.errTarget != nil && !errors.Is(err, tt.errTarget) {
					t.Errorf("GetByID() error = %v, want target %v", err, tt.errTarget)
				}
				return
			}

			if err != nil {
				t.Fatalf("GetByID() unexpected error = %v", err)
			}

			if got.ID != existing.ID {
				t.Errorf("got ID = %q, want %q", got.ID, existing.ID)
			}
		})
	}
}

func TestService_List(t *testing.T) {
	t.Parallel()

	tests := map[string]struct {
		mockRepo *mockRepository
		wantErr  bool
		wantLen  int
	}{
		"returns items list": {
			mockRepo: &mockRepository{
				listFn: func(_ context.Context) ([]domain.Item, error) {
					return []domain.Item{
						{ID: "i1", Name: "Item 1"},
						{ID: "i2", Name: "Item 2"},
					}, nil
				},
			},
			wantErr: false,
			wantLen: 2,
		},
		"empty store returns non-nil slice": {
			mockRepo: &mockRepository{
				listFn: func(_ context.Context) ([]domain.Item, error) {
					return nil, nil
				},
			},
			wantErr: false,
			wantLen: 0,
		},
		"repository error propagated": {
			mockRepo: &mockRepository{
				listFn: func(_ context.Context) ([]domain.Item, error) {
					return nil, errors.New("storage error")
				},
			},
			wantErr: true,
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			svc := items.NewService(tt.mockRepo)
			res, err := svc.List(context.Background())

			if tt.wantErr {
				if err == nil {
					t.Fatalf("List() expected error, got nil")
				}
				return
			}

			if err != nil {
				t.Fatalf("List() unexpected error = %v", err)
			}

			if res == nil {
				t.Error("List() should return non-nil slice")
			}
			if len(res) != tt.wantLen {
				t.Errorf("List() len = %d, want %d", len(res), tt.wantLen)
			}
		})
	}
}

func TestService_Update(t *testing.T) {
	t.Parallel()

	existingActive := domain.Item{
		ID:          "item-update",
		Name:        "Initial Name",
		Description: "Initial Desc",
		Status:      domain.StatusActive,
		CreatedAt:   time.Now().UTC(),
		UpdatedAt:   time.Now().UTC(),
	}

	existingArchived := domain.Item{
		ID:          "item-archived",
		Name:        "Archived Name",
		Description: "Archived Desc",
		Status:      domain.StatusArchived,
		CreatedAt:   time.Now().UTC(),
		UpdatedAt:   time.Now().UTC(),
	}

	tests := map[string]struct {
		id          string
		name        string
		description string
		status      domain.ItemStatus
		mockRepo    *mockRepository
		wantErr     bool
		errTarget   error
	}{
		"successful update and status transition": {
			id:          "item-update",
			name:        "Updated Name",
			description: "Updated Desc",
			status:      domain.StatusCompleted,
			mockRepo: &mockRepository{
				getByIDFn: func(_ context.Context, _ string) (domain.Item, error) {
					return existingActive, nil
				},
				updateFn: func(_ context.Context, item domain.Item) error {
					if item.Name != "Updated Name" || item.Status != domain.StatusCompleted {
						t.Errorf("repo.Update received invalid item: %+v", item)
					}
					return nil
				},
			},
			wantErr: false,
		},
		"empty id returns validation error": {
			id:        "",
			name:      "Valid Name",
			mockRepo:  &mockRepository{},
			wantErr:   true,
			errTarget: domain.ErrValidation,
		},
		"item not found returns ErrNotFound": {
			id:   "non-existent",
			name: "Valid Name",
			mockRepo: &mockRepository{
				getByIDFn: func(_ context.Context, _ string) (domain.Item, error) {
					return domain.Item{}, domain.ErrNotFound
				},
			},
			wantErr:   true,
			errTarget: domain.ErrNotFound,
		},
		"mutation of archived item returns validation error": {
			id:          "item-archived",
			name:        "Attempted Update",
			description: "Cannot modify",
			status:      domain.StatusArchived,
			mockRepo: &mockRepository{
				getByIDFn: func(_ context.Context, _ string) (domain.Item, error) {
					return existingArchived, nil
				},
			},
			wantErr:   true,
			errTarget: domain.ErrValidation,
		},
		"invalid state transition returns validation error": {
			id:          "item-update",
			name:        "Valid Name",
			description: "Valid Desc",
			status:      domain.ItemStatus("corrupted_state"),
			mockRepo: &mockRepository{
				getByIDFn: func(_ context.Context, _ string) (domain.Item, error) {
					return existingActive, nil
				},
			},
			wantErr:   true,
			errTarget: domain.ErrValidation,
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			svc := items.NewService(tt.mockRepo)
			updated, err := svc.Update(context.Background(), tt.id, tt.name, tt.description, tt.status)

			if tt.wantErr {
				if err == nil {
					t.Fatalf("Update() expected error, got nil")
				}
				if tt.errTarget != nil && !errors.Is(err, tt.errTarget) {
					t.Errorf("Update() error = %v, want target %v", err, tt.errTarget)
				}
				return
			}

			if err != nil {
				t.Fatalf("Update() unexpected error = %v", err)
			}

			if updated.Name != tt.name {
				t.Errorf("updated.Name = %q, want %q", updated.Name, tt.name)
			}
			if tt.status != "" && updated.Status != tt.status {
				t.Errorf("updated.Status = %q, want %q", updated.Status, tt.status)
			}
		})
	}
}

func TestService_Delete(t *testing.T) {
	t.Parallel()

	tests := map[string]struct {
		id        string
		mockRepo  *mockRepository
		wantErr   bool
		errTarget error
	}{
		"successful delete": {
			id: "item-delete",
			mockRepo: &mockRepository{
				deleteFn: func(_ context.Context, _ string) error {
					return nil
				},
			},
			wantErr: false,
		},
		"empty id returns validation error": {
			id:        "   ",
			mockRepo:  &mockRepository{},
			wantErr:   true,
			errTarget: domain.ErrValidation,
		},
		"non-existent item returns ErrNotFound": {
			id: "missing-id",
			mockRepo: &mockRepository{
				deleteFn: func(_ context.Context, _ string) error {
					return domain.ErrNotFound
				},
			},
			wantErr:   true,
			errTarget: domain.ErrNotFound,
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			svc := items.NewService(tt.mockRepo)
			err := svc.Delete(context.Background(), tt.id)

			if tt.wantErr {
				if err == nil {
					t.Fatalf("Delete() expected error, got nil")
				}
				if tt.errTarget != nil && !errors.Is(err, tt.errTarget) {
					t.Errorf("Delete() error = %v, want target %v", err, tt.errTarget)
				}
				return
			}

			if err != nil {
				t.Fatalf("Delete() unexpected error = %v", err)
			}
		})
	}
}
