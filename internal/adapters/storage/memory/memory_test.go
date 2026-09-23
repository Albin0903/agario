package memory_test

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"testing"
	"time"

	"github.com/albin/build/internal/adapters/storage/memory"
	"github.com/albin/build/internal/core/domain"
)

func TestRepository_Ping(t *testing.T) {
	t.Parallel()

	tests := map[string]struct {
		ctxFn     func() (context.Context, context.CancelFunc)
		wantErr   bool
		targetErr error
	}{
		"active context returns nil": {
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			wantErr: false,
		},
		"canceled context returns error": {
			ctxFn: func() (context.Context, context.CancelFunc) {
				ctx, cancel := context.WithCancel(context.Background())
				cancel()
				return ctx, cancel
			},
			wantErr:   true,
			targetErr: context.Canceled,
		},
		"deadline exceeded context returns error": {
			ctxFn: func() (context.Context, context.CancelFunc) {
				ctx, cancel := context.WithDeadline(context.Background(), time.Now().Add(-time.Millisecond))
				return ctx, cancel
			},
			wantErr:   true,
			targetErr: context.DeadlineExceeded,
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			ctx, cancel := tt.ctxFn()
			defer cancel()

			repo := memory.New()
			err := repo.Ping(ctx)

			if (err != nil) != tt.wantErr {
				t.Fatalf("Ping() error = %v, wantErr = %v", err, tt.wantErr)
			}

			if tt.targetErr != nil && !errors.Is(err, tt.targetErr) {
				t.Fatalf("expected error wrapping %v, got %v", tt.targetErr, err)
			}
		})
	}
}

func TestRepository_Save(t *testing.T) {
	t.Parallel()

	validItem := domain.Item{
		ID:          "item-01",
		Name:        "Calibrate physics",
		Description: "Tune spring constants",
		Status:      domain.StatusActive,
		CreatedAt:   time.Now().UTC(),
		UpdatedAt:   time.Now().UTC(),
	}

	tests := map[string]struct {
		setupRepo func(ctx context.Context, r *memory.Repository)
		item      domain.Item
		ctxFn     func() (context.Context, context.CancelFunc)
		wantErr   bool
		targetErr error
	}{
		"save new item succeeds": {
			item: validItem,
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			wantErr: false,
		},
		"saving duplicate id returns ErrConflict": {
			setupRepo: func(ctx context.Context, r *memory.Repository) {
				_ = r.Save(ctx, validItem)
			},
			item: validItem,
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			wantErr:   true,
			targetErr: domain.ErrConflict,
		},
		"saving item with empty id returns ErrValidation": {
			item: domain.Item{Name: "Missing ID"},
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			wantErr:   true,
			targetErr: domain.ErrValidation,
		},
		"canceled context returns context error without mutating": {
			item: domain.Item{ID: "canceled-item", Name: "Not saved"},
			ctxFn: func() (context.Context, context.CancelFunc) {
				ctx, cancel := context.WithCancel(context.Background())
				cancel()
				return ctx, cancel
			},
			wantErr:   true,
			targetErr: context.Canceled,
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			ctx, cancel := tt.ctxFn()
			defer cancel()

			repo := memory.New()
			if tt.setupRepo != nil {
				tt.setupRepo(context.Background(), repo)
			}

			err := repo.Save(ctx, tt.item)

			if (err != nil) != tt.wantErr {
				t.Fatalf("Save() error = %v, wantErr = %v", err, tt.wantErr)
			}

			if tt.targetErr != nil && !errors.Is(err, tt.targetErr) {
				t.Fatalf("expected error wrapping %v, got %v", tt.targetErr, err)
			}
		})
	}
}

func TestRepository_GetByID(t *testing.T) {
	t.Parallel()

	existingItem := domain.Item{
		ID:          "item-existing",
		Name:        "Existing Item",
		Description: "Present in repository",
		Status:      domain.StatusCompleted,
		CreatedAt:   time.Now().UTC(),
		UpdatedAt:   time.Now().UTC(),
	}

	tests := map[string]struct {
		setupRepo func(ctx context.Context, r *memory.Repository)
		id        string
		ctxFn     func() (context.Context, context.CancelFunc)
		wantErr   bool
		targetErr error
		wantItem  domain.Item
	}{
		"retrieves existing item": {
			setupRepo: func(ctx context.Context, r *memory.Repository) {
				_ = r.Save(ctx, existingItem)
			},
			id: existingItem.ID,
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			wantErr:  false,
			wantItem: existingItem,
		},
		"non-existent item returns ErrNotFound": {
			id: "unknown-id",
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			wantErr:   true,
			targetErr: domain.ErrNotFound,
		},
		"empty id returns ErrValidation": {
			id: "",
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			wantErr:   true,
			targetErr: domain.ErrValidation,
		},
		"canceled context returns error": {
			id: existingItem.ID,
			ctxFn: func() (context.Context, context.CancelFunc) {
				ctx, cancel := context.WithCancel(context.Background())
				cancel()
				return ctx, cancel
			},
			wantErr:   true,
			targetErr: context.Canceled,
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			ctx, cancel := tt.ctxFn()
			defer cancel()

			repo := memory.New()
			if tt.setupRepo != nil {
				tt.setupRepo(context.Background(), repo)
			}

			got, err := repo.GetByID(ctx, tt.id)

			if (err != nil) != tt.wantErr {
				t.Fatalf("GetByID() error = %v, wantErr = %v", err, tt.wantErr)
			}

			if tt.targetErr != nil && !errors.Is(err, tt.targetErr) {
				t.Fatalf("expected error wrapping %v, got %v", tt.targetErr, err)
			}

			if !tt.wantErr && got.ID != tt.wantItem.ID {
				t.Errorf("GetByID() got ID %q, want %q", got.ID, tt.wantItem.ID)
			}
		})
	}
}

func TestRepository_List(t *testing.T) {
	t.Parallel()

	now := time.Now().UTC()
	item1 := domain.Item{ID: "item-old", Name: "Old", CreatedAt: now.Add(-10 * time.Minute)}
	item2 := domain.Item{ID: "item-new", Name: "New", CreatedAt: now}

	tests := map[string]struct {
		setupRepo func(ctx context.Context, r *memory.Repository)
		ctxFn     func() (context.Context, context.CancelFunc)
		wantErr   bool
		wantCount int
		verifyFn  func(t *testing.T, items []domain.Item)
	}{
		"empty repository returns non-nil empty slice": {
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			wantErr:   false,
			wantCount: 0,
			verifyFn: func(t *testing.T, items []domain.Item) {
				if items == nil {
					t.Error("expected non-nil empty slice, got nil")
				}
			},
		},
		"returns items sorted by CreatedAt descending": {
			setupRepo: func(ctx context.Context, r *memory.Repository) {
				_ = r.Save(ctx, item1)
				_ = r.Save(ctx, item2)
			},
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			wantErr:   false,
			wantCount: 2,
			verifyFn: func(t *testing.T, items []domain.Item) {
				if items[0].ID != "item-new" || items[1].ID != "item-old" {
					t.Errorf("expected newest first [item-new, item-old], got [%s, %s]", items[0].ID, items[1].ID)
				}
			},
		},
		"canceled context returns error": {
			ctxFn: func() (context.Context, context.CancelFunc) {
				ctx, cancel := context.WithCancel(context.Background())
				cancel()
				return ctx, cancel
			},
			wantErr: true,
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			ctx, cancel := tt.ctxFn()
			defer cancel()

			repo := memory.New()
			if tt.setupRepo != nil {
				tt.setupRepo(context.Background(), repo)
			}

			items, err := repo.List(ctx)

			if (err != nil) != tt.wantErr {
				t.Fatalf("List() error = %v, wantErr = %v", err, tt.wantErr)
			}

			if !tt.wantErr {
				if len(items) != tt.wantCount {
					t.Fatalf("List() count = %d, want %d", len(items), tt.wantCount)
				}
				if tt.verifyFn != nil {
					tt.verifyFn(t, items)
				}
			}
		})
	}
}

func TestRepository_Update(t *testing.T) {
	t.Parallel()

	existingItem := domain.Item{
		ID:     "item-updatable",
		Name:   "Initial Name",
		Status: domain.StatusActive,
	}

	tests := map[string]struct {
		setupRepo func(ctx context.Context, r *memory.Repository)
		item      domain.Item
		ctxFn     func() (context.Context, context.CancelFunc)
		wantErr   bool
		targetErr error
	}{
		"successful update modifies existing item": {
			setupRepo: func(ctx context.Context, r *memory.Repository) {
				_ = r.Save(ctx, existingItem)
			},
			item: domain.Item{
				ID:     existingItem.ID,
				Name:   "Updated Name",
				Status: domain.StatusCompleted,
			},
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			wantErr: false,
		},
		"updating non-existent item returns ErrNotFound": {
			item: domain.Item{ID: "does-not-exist", Name: "Ghost"},
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			wantErr:   true,
			targetErr: domain.ErrNotFound,
		},
		"updating item with empty id returns ErrValidation": {
			item: domain.Item{ID: "", Name: "Blank"},
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			wantErr:   true,
			targetErr: domain.ErrValidation,
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			ctx, cancel := tt.ctxFn()
			defer cancel()

			repo := memory.New()
			if tt.setupRepo != nil {
				tt.setupRepo(context.Background(), repo)
			}

			err := repo.Update(ctx, tt.item)

			if (err != nil) != tt.wantErr {
				t.Fatalf("Update() error = %v, wantErr = %v", err, tt.wantErr)
			}

			if tt.targetErr != nil && !errors.Is(err, tt.targetErr) {
				t.Fatalf("expected error wrapping %v, got %v", tt.targetErr, err)
			}

			if !tt.wantErr {
				updated, getErr := repo.GetByID(context.Background(), tt.item.ID)
				if getErr != nil {
					t.Fatalf("unexpected error fetching updated item: %v", getErr)
				}
				if updated.Name != tt.item.Name || updated.Status != tt.item.Status {
					t.Errorf("item state not updated properly: got %+v, want %+v", updated, tt.item)
				}
			}
		})
	}
}

func TestRepository_Delete(t *testing.T) {
	t.Parallel()

	existingItem := domain.Item{ID: "item-to-delete", Name: "Transient"}

	tests := map[string]struct {
		setupRepo func(ctx context.Context, r *memory.Repository)
		id        string
		ctxFn     func() (context.Context, context.CancelFunc)
		wantErr   bool
		targetErr error
	}{
		"deleting existing item succeeds": {
			setupRepo: func(ctx context.Context, r *memory.Repository) {
				_ = r.Save(ctx, existingItem)
			},
			id: existingItem.ID,
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			wantErr: false,
		},
		"deleting non-existent item returns ErrNotFound": {
			id: "absent-item",
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			wantErr:   true,
			targetErr: domain.ErrNotFound,
		},
		"deleting with empty id returns ErrValidation": {
			id: "",
			ctxFn: func() (context.Context, context.CancelFunc) {
				return context.WithCancel(context.Background())
			},
			wantErr:   true,
			targetErr: domain.ErrValidation,
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			ctx, cancel := tt.ctxFn()
			defer cancel()

			repo := memory.New()
			if tt.setupRepo != nil {
				tt.setupRepo(context.Background(), repo)
			}

			err := repo.Delete(ctx, tt.id)

			if (err != nil) != tt.wantErr {
				t.Fatalf("Delete() error = %v, wantErr = %v", err, tt.wantErr)
			}

			if tt.targetErr != nil && !errors.Is(err, tt.targetErr) {
				t.Fatalf("expected error wrapping %v, got %v", tt.targetErr, err)
			}

			if !tt.wantErr {
				_, getErr := repo.GetByID(context.Background(), tt.id)
				if !errors.Is(getErr, domain.ErrNotFound) {
					t.Errorf("item should be deleted, but GetByID returned %v", getErr)
				}
			}
		})
	}
}

func TestRepository_SeedAndNewWithSeed(t *testing.T) {
	t.Parallel()

	seedItems := memory.DefaultSeedItems()
	if len(seedItems) < 3 {
		t.Fatalf("expected at least 3 authentic seed items, got %d", len(seedItems))
	}

	repo := memory.NewWithSeed(seedItems...)
	ctx := context.Background()

	list, err := repo.List(ctx)
	if err != nil {
		t.Fatalf("List() failed on seeded repository: %v", err)
	}

	if len(list) != len(seedItems) {
		t.Errorf("seeded count = %d, want %d", len(list), len(seedItems))
	}

	for _, expected := range seedItems {
		item, getErr := repo.GetByID(ctx, expected.ID)
		if getErr != nil {
			t.Errorf("failed to retrieve seeded item %q: %v", expected.ID, getErr)
		}
		if item.Name != expected.Name {
			t.Errorf("seeded item %q name mismatch: got %q, want %q", expected.ID, item.Name, expected.Name)
		}
	}
}

func TestRepository_ConcurrencySafety(t *testing.T) {
	t.Parallel()

	repo := memory.New()
	ctx := context.Background()

	// Pre-populate with seed items
	const preseedCount = 20
	for i := 0; i < preseedCount; i++ {
		id := fmt.Sprintf("seed-item-%02d", i)
		_ = repo.Save(ctx, domain.Item{
			ID:          id,
			Name:        fmt.Sprintf("Concurrent Base Item %d", i),
			Description: "Stress testing concurrent access",
			Status:      domain.StatusActive,
			CreatedAt:   time.Now().UTC(),
			UpdatedAt:   time.Now().UTC(),
		})
	}

	const numReaders = 30
	const numWriters = 30
	const opsPerWorker = 50

	var wg sync.WaitGroup

	// Reader workers
	for w := 0; w < numReaders; w++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			for op := 0; op < opsPerWorker; op++ {
				targetID := fmt.Sprintf("seed-item-%02d", (workerID+op)%preseedCount)
				_, _ = repo.GetByID(ctx, targetID)
				_, _ = repo.List(ctx)
				_ = repo.Ping(ctx)
			}
		}(w)
	}

	// Writer workers
	for w := 0; w < numWriters; w++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			for op := 0; op < opsPerWorker; op++ {
				dynamicID := fmt.Sprintf("worker-%02d-item-%03d", workerID, op)
				item := domain.Item{
					ID:          dynamicID,
					Name:        "Stress Item",
					Description: "Dynamically added item",
					Status:      domain.StatusActive,
					CreatedAt:   time.Now().UTC(),
					UpdatedAt:   time.Now().UTC(),
				}

				// Sequence of concurrent writes
				_ = repo.Save(ctx, item)
				item.Status = domain.StatusCompleted
				_ = repo.Update(ctx, item)
				_ = repo.Delete(ctx, dynamicID)
			}
		}(w)
	}

	wg.Wait()

	// Verify internal state integrity after concurrent barrage
	finalItems, err := repo.List(ctx)
	if err != nil {
		t.Fatalf("List() failed after concurrent stress run: %v", err)
	}
	if len(finalItems) < preseedCount {
		t.Errorf("expected at least %d base items preserved, got %d", preseedCount, len(finalItems))
	}
}
