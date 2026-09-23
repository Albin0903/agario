package memory

import (
	"context"
	"errors"
	"fmt"
	"math/rand"
	"runtime"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/albin/build/internal/core/domain"
)

// TestAdversarial_HighConcurrencyCollision stresses the memory repository under heavy read/write contention.
// 100 concurrent workers perform 20,000 total operations across Ping, Save, GetByID, List, Update, and Delete.
func TestAdversarial_HighConcurrencyCollision(t *testing.T) {
	t.Parallel()

	repo := New()
	ctx := context.Background()

	// Pre-populate with base items
	const preseedCount = 50
	baseTime := time.Date(2026, 9, 12, 10, 0, 0, 0, time.UTC)
	for i := 0; i < preseedCount; i++ {
		id := fmt.Sprintf("base-item-%03d", i)
		err := repo.Save(ctx, domain.Item{
			ID:          id,
			Name:        fmt.Sprintf("Base Item %d", i),
			Description: "Initial seed for collision stress",
			Status:      domain.StatusActive,
			CreatedAt:   baseTime.Add(time.Duration(i) * time.Minute),
			UpdatedAt:   baseTime.Add(time.Duration(i) * time.Minute),
		})
		if err != nil {
			t.Fatalf("failed to preseed item %s: %v", id, err)
		}
	}

	const workerCount = 100
	const opsPerWorker = 200

	var totalOps atomic.Int64
	var totalCollisions atomic.Int64

	startSignal := make(chan struct{})
	var wg sync.WaitGroup

	for w := 0; w < workerCount; w++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			<-startSignal

			rng := rand.New(rand.NewSource(int64(workerID * 1000)))

			for i := 0; i < opsPerWorker; i++ {
				opType := rng.Intn(6)
				targetIndex := rng.Intn(preseedCount + 20)
				targetID := fmt.Sprintf("base-item-%03d", targetIndex)

				switch opType {
				case 0: // Ping
					if err := repo.Ping(ctx); err != nil {
						t.Errorf("worker %d: Ping failed: %v", workerID, err)
					}
				case 1: // GetByID
					_, err := repo.GetByID(ctx, targetID)
					if err != nil && !errors.Is(err, domain.ErrNotFound) {
						t.Errorf("worker %d: GetByID unexpected error: %v", workerID, err)
					}
				case 2: // List and verify non-nil
					items, err := repo.List(ctx)
					if err != nil {
						t.Errorf("worker %d: List failed: %v", workerID, err)
					}
					if items == nil {
						t.Errorf("worker %d: List returned nil slice", workerID)
					}
				case 3: // Save
					newItemID := fmt.Sprintf("dynamic-%03d-%04d", workerID, i)
					err := repo.Save(ctx, domain.Item{
						ID:          newItemID,
						Name:        fmt.Sprintf("Dynamic Item %d-%d", workerID, i),
						Description: "Concurrent save",
						Status:      domain.StatusPending,
						CreatedAt:   time.Now().UTC(),
						UpdatedAt:   time.Now().UTC(),
					})
					if err != nil && !errors.Is(err, domain.ErrConflict) {
						t.Errorf("worker %d: Save unexpected error: %v", workerID, err)
					}
					if errors.Is(err, domain.ErrConflict) {
						totalCollisions.Add(1)
					}
				case 4: // Update
					err := repo.Update(ctx, domain.Item{
						ID:          targetID,
						Name:        fmt.Sprintf("Updated by %d at %d", workerID, i),
						Description: "Concurrent update",
						Status:      domain.StatusCompleted,
						CreatedAt:   baseTime,
						UpdatedAt:   time.Now().UTC(),
					})
					if err != nil && !errors.Is(err, domain.ErrNotFound) {
						t.Errorf("worker %d: Update unexpected error: %v", workerID, err)
					}
				case 5: // Delete
					dynamicID := fmt.Sprintf("dynamic-%03d-%04d", workerID, rng.Intn(i+1))
					err := repo.Delete(ctx, dynamicID)
					if err != nil && !errors.Is(err, domain.ErrNotFound) {
						t.Errorf("worker %d: Delete unexpected error: %v", workerID, err)
					}
				}
				totalOps.Add(1)
			}
		}(w)
	}

	// Release all workers simultaneously
	close(startSignal)

	// Wait with a hard timeout to detect deadlocks
	done := make(chan struct{})
	go func() {
		wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		// Succeeded within bound
	case <-time.After(15 * time.Second):
		t.Fatal("DEADLOCK DETECTED: High concurrency collision test did not finish within 15 seconds")
	}

	finalList, err := repo.List(ctx)
	if err != nil {
		t.Fatalf("List() failed after high-concurrency collision test: %v", err)
	}

	t.Logf("Completed %d ops (%d collisions) under 100 workers. Surviving items: %d",
		totalOps.Load(), totalCollisions.Load(), len(finalList))
}

// TestAdversarial_IdenticalKeyRace tests race conditions when many goroutines attempt to insert or delete the exact same key.
func TestAdversarial_IdenticalKeyRace(t *testing.T) {
	t.Parallel()

	repo := New()
	ctx := context.Background()

	const identicalKey = "contested-singleton-item"
	const racerCount = 50

	// Race 1: 50 goroutines race to Save the exact same ID
	var saveSuccessCount atomic.Int64
	var saveConflictCount atomic.Int64
	startSave := make(chan struct{})
	var wgSave sync.WaitGroup

	for i := 0; i < racerCount; i++ {
		wgSave.Add(1)
		go func(id int) {
			defer wgSave.Done()
			<-startSave

			err := repo.Save(ctx, domain.Item{
				ID:        identicalKey,
				Name:      fmt.Sprintf("Racer %d", id),
				Status:    domain.StatusActive,
				CreatedAt: time.Now().UTC(),
			})
			switch {
			case err == nil:
				saveSuccessCount.Add(1)
			case errors.Is(err, domain.ErrConflict):
				saveConflictCount.Add(1)
			default:
				t.Errorf("racer %d: unexpected save error: %v", id, err)
			}
		}(i)
	}

	close(startSave)
	wgSave.Wait()

	if saveSuccessCount.Load() != 1 {
		t.Fatalf("IDENTICAL KEY RACE VIOLATION: expected exactly 1 Save to succeed, got %d", saveSuccessCount.Load())
	}
	if saveConflictCount.Load() != int64(racerCount-1) {
		t.Fatalf("IDENTICAL KEY RACE VIOLATION: expected %d ErrConflict, got %d", racerCount-1, saveConflictCount.Load())
	}

	// Race 2: 50 goroutines race to Delete the exact same ID
	var deleteSuccessCount atomic.Int64
	var deleteNotFoundCount atomic.Int64
	startDelete := make(chan struct{})
	var wgDelete sync.WaitGroup

	for i := 0; i < racerCount; i++ {
		wgDelete.Add(1)
		go func(id int) {
			defer wgDelete.Done()
			<-startDelete

			err := repo.Delete(ctx, identicalKey)
			switch {
			case err == nil:
				deleteSuccessCount.Add(1)
			case errors.Is(err, domain.ErrNotFound):
				deleteNotFoundCount.Add(1)
			default:
				t.Errorf("racer %d: unexpected delete error: %v", id, err)
			}
		}(i)
	}

	close(startDelete)
	wgDelete.Wait()

	if deleteSuccessCount.Load() != 1 {
		t.Fatalf("IDENTICAL KEY RACE VIOLATION: expected exactly 1 Delete to succeed, got %d", deleteSuccessCount.Load())
	}
	if deleteNotFoundCount.Load() != int64(racerCount-1) {
		t.Fatalf("IDENTICAL KEY RACE VIOLATION: expected %d ErrNotFound, got %d", racerCount-1, deleteNotFoundCount.Load())
	}
}

// TestAdversarial_DeterministicSortingUnderConcurrentMutations exercises sorting invariants under rapid mutations.
func TestAdversarial_DeterministicSortingUnderConcurrentMutations(t *testing.T) {
	t.Parallel()

	repo := New()
	ctx := context.Background()

	// Populate with items having overlapping and distinct timestamps
	baseTime := time.Date(2026, 9, 12, 12, 0, 0, 0, time.UTC)
	for i := 0; i < 30; i++ {
		_ = repo.Save(ctx, domain.Item{
			ID:        fmt.Sprintf("seed-%02d", i),
			Name:      fmt.Sprintf("Seed %d", i),
			Status:    domain.StatusActive,
			CreatedAt: baseTime.Add(time.Duration(i%5) * time.Second), // duplicate timestamps
			UpdatedAt: baseTime,
		})
	}

	stopChan := make(chan struct{})
	var wg sync.WaitGroup

	// Mutator goroutines: rapidly insert, update, and delete
	for m := 0; m < 10; m++ {
		wg.Add(1)
		go func(mutatorID int) {
			defer wg.Done()
			rng := rand.New(rand.NewSource(int64(mutatorID * 777)))
			counter := 0

			for {
				select {
				case <-stopChan:
					return
				default:
					id := fmt.Sprintf("mut-%02d-%04d", mutatorID, counter)
					ts := baseTime.Add(time.Duration(rng.Intn(10)-5) * time.Second)

					_ = repo.Save(ctx, domain.Item{
						ID:        id,
						Name:      "Mutation Item",
						Status:    domain.StatusPending,
						CreatedAt: ts,
						UpdatedAt: ts,
					})

					if counter%2 == 0 {
						_ = repo.Delete(ctx, id)
					}
					counter++
				}
			}
		}(m)
	}

	// Observer goroutines: continuously call List and enforce strict sorting invariants
	var violations atomic.Int64
	for o := 0; o < 10; o++ {
		wg.Add(1)
		go func(observerID int) {
			defer wg.Done()
			for iter := 0; iter < 100; iter++ {
				items, err := repo.List(ctx)
				if err != nil {
					t.Errorf("observer %d: List error: %v", observerID, err)
					return
				}

				// Check invariant: CreatedAt descending, tie-breaker ID ascending
				for k := 0; k < len(items)-1; k++ {
					curr := items[k]
					next := items[k+1]

					if curr.CreatedAt.Before(next.CreatedAt) {
						violations.Add(1)
						t.Errorf("SORT VIOLATION: index %d (%s, %v) is before index %d (%s, %v)",
							k, curr.ID, curr.CreatedAt, k+1, next.ID, next.CreatedAt)
					} else if curr.CreatedAt.Equal(next.CreatedAt) {
						if curr.ID >= next.ID {
							violations.Add(1)
							t.Errorf("TIE-BREAKER VIOLATION: index %d (%s) >= index %d (%s) with identical timestamp %v",
								k, curr.ID, k+1, next.ID, curr.CreatedAt)
						}
					}
				}
			}
		}(o)
	}

	time.Sleep(100 * time.Millisecond)
	close(stopChan)
	wg.Wait()

	if v := violations.Load(); v > 0 {
		t.Fatalf("Detected %d sorting determinism violations under concurrent mutation", v)
	}
}

// TestAdversarial_ContextCancellationUnderLockContention tests context timeout behavior when lock is held.
func TestAdversarial_ContextCancellationUnderLockContention(t *testing.T) {
	t.Parallel()

	t.Run("Save cancels when context expires while waiting for write lock", func(t *testing.T) {
		t.Parallel()
		repo := New()

		repo.mu.Lock()

		errChan := make(chan error, 1)
		ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
		defer cancel()

		go func() {
			errChan <- repo.Save(ctx, domain.Item{
				ID:   "blocked-save",
				Name: "Should not be saved",
			})
		}()

		time.Sleep(50 * time.Millisecond)
		repo.mu.Unlock()

		err := <-errChan
		if err == nil {
			t.Fatal("expected error for timed-out Save, got nil")
		}
		if !errors.Is(err, context.DeadlineExceeded) {
			t.Fatalf("expected context.DeadlineExceeded, got: %v", err)
		}

		if _, exists := repo.items["blocked-save"]; exists {
			t.Fatal("blocked item was saved despite context deadline expiration!")
		}
	})

	t.Run("GetByID cancels when context expires while waiting for read lock", func(t *testing.T) {
		t.Parallel()
		repo := New()
		_ = repo.Save(context.Background(), domain.Item{ID: "existing-item", Name: "Exists"})

		repo.mu.Lock()

		errChan := make(chan error, 1)
		ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
		defer cancel()

		go func() {
			_, err := repo.GetByID(ctx, "existing-item")
			errChan <- err
		}()

		time.Sleep(50 * time.Millisecond)
		repo.mu.Unlock()

		err := <-errChan
		if err == nil {
			t.Fatal("expected error for timed-out GetByID, got nil")
		}
		if !errors.Is(err, context.DeadlineExceeded) {
			t.Fatalf("expected context.DeadlineExceeded, got: %v", err)
		}
	})

	t.Run("List cancels when context expires while waiting for read lock", func(t *testing.T) {
		t.Parallel()
		repo := New()

		repo.mu.Lock()

		errChan := make(chan error, 1)
		ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
		defer cancel()

		go func() {
			_, err := repo.List(ctx)
			errChan <- err
		}()

		time.Sleep(50 * time.Millisecond)
		repo.mu.Unlock()

		err := <-errChan
		if err == nil {
			t.Fatal("expected error for timed-out List, got nil")
		}
		if !errors.Is(err, context.DeadlineExceeded) {
			t.Fatalf("expected context.DeadlineExceeded, got: %v", err)
		}
	})

	t.Run("Update cancels when context expires while waiting for write lock", func(t *testing.T) {
		t.Parallel()
		repo := New()
		_ = repo.Save(context.Background(), domain.Item{ID: "update-item", Name: "Original"})

		repo.mu.Lock()

		errChan := make(chan error, 1)
		ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
		defer cancel()

		go func() {
			errChan <- repo.Update(ctx, domain.Item{
				ID:   "update-item",
				Name: "Mutated",
			})
		}()

		time.Sleep(50 * time.Millisecond)
		repo.mu.Unlock()

		err := <-errChan
		if err == nil {
			t.Fatal("expected error for timed-out Update, got nil")
		}
		if !errors.Is(err, context.DeadlineExceeded) {
			t.Fatalf("expected context.DeadlineExceeded, got: %v", err)
		}

		if repo.items["update-item"].Name != "Original" {
			t.Fatalf("item was mutated despite context deadline exceeded: got %q, want 'Original'",
				repo.items["update-item"].Name)
		}
	})

	t.Run("Delete cancels when context expires while waiting for write lock", func(t *testing.T) {
		t.Parallel()
		repo := New()
		_ = repo.Save(context.Background(), domain.Item{ID: "delete-item", Name: "Preserved"})

		repo.mu.Lock()

		errChan := make(chan error, 1)
		ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
		defer cancel()

		go func() {
			errChan <- repo.Delete(ctx, "delete-item")
		}()

		time.Sleep(50 * time.Millisecond)
		repo.mu.Unlock()

		err := <-errChan
		if err == nil {
			t.Fatal("expected error for timed-out Delete, got nil")
		}
		if !errors.Is(err, context.DeadlineExceeded) {
			t.Fatalf("expected context.DeadlineExceeded, got: %v", err)
		}

		if _, exists := repo.items["delete-item"]; !exists {
			t.Fatal("item was deleted despite context deadline exceeded!")
		}
	})

	t.Run("Ping cancels when context expires while waiting for read lock", func(t *testing.T) {
		t.Parallel()
		repo := New()

		repo.mu.Lock()

		errChan := make(chan error, 1)
		ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
		defer cancel()

		go func() {
			errChan <- repo.Ping(ctx)
		}()

		time.Sleep(50 * time.Millisecond)
		repo.mu.Unlock()

		err := <-errChan
		if err == nil {
			t.Fatal("expected error for timed-out Ping, got nil")
		}
		if !errors.Is(err, context.DeadlineExceeded) {
			t.Fatalf("expected context.DeadlineExceeded, got: %v", err)
		}
	})
}

// TestAdversarial_ValueSemanticsAndReferenceIsolation tests that callers cannot mutate internal state via returned values.
func TestAdversarial_ValueSemanticsAndReferenceIsolation(t *testing.T) {
	t.Parallel()

	repo := New()
	ctx := context.Background()

	original := domain.Item{
		ID:          "immutable-01",
		Name:        "Original Name",
		Description: "Original Description",
		Status:      domain.StatusActive,
		CreatedAt:   time.Now().UTC(),
		UpdatedAt:   time.Now().UTC(),
	}

	if err := repo.Save(ctx, original); err != nil {
		t.Fatalf("Save failed: %v", err)
	}

	// Retrieve via GetByID and mutate caller copy
	retrieved, err := repo.GetByID(ctx, original.ID)
	if err != nil {
		t.Fatalf("GetByID failed: %v", err)
	}

	retrieved.Name = "HACKED_NAME"
	retrieved.Status = domain.StatusArchived

	// Verify internal state in repo remains pristine
	verifyGet, err := repo.GetByID(ctx, original.ID)
	if err != nil {
		t.Fatalf("second GetByID failed: %v", err)
	}
	if verifyGet.Name != original.Name || verifyGet.Status != original.Status {
		t.Fatalf("REFERENCE LEAK in GetByID: internal state mutated via caller return! got %+v, want %+v",
			verifyGet, original)
	}

	// Retrieve via List and mutate caller slice and elements
	list, err := repo.List(ctx)
	if err != nil {
		t.Fatalf("List failed: %v", err)
	}
	if len(list) != 1 {
		t.Fatalf("List count = %d, want 1", len(list))
	}

	list[0].Name = "HACKED_LIST_NAME"
	list = append(list, domain.Item{ID: "injected-item", Name: "Injected"})
	if len(list) != 2 {
		t.Fatalf("mutated slice length = %d, want 2", len(list))
	}

	verifyList, err := repo.List(ctx)
	if err != nil {
		t.Fatalf("second List failed: %v", err)
	}
	if len(verifyList) != 1 || verifyList[0].Name != original.Name {
		t.Fatalf("REFERENCE LEAK in List: internal state mutated via caller slice! got %+v", verifyList)
	}
}

// TestAdversarial_GoroutineLeakAndDeadlockRecovery ensures goroutines do not leak when canceled.
// Runs serially to accurately measure process-wide runtime.NumGoroutine().
func TestAdversarial_GoroutineLeakAndDeadlockRecovery(t *testing.T) {
	repo := New()
	baseGoroutines := runtime.NumGoroutine()

	const workerCount = 50
	var wg sync.WaitGroup

	for i := 0; i < workerCount; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Millisecond)
			defer cancel()

			for j := 0; j < 20; j++ {
				_ = repo.Save(ctx, domain.Item{
					ID:   fmt.Sprintf("leak-test-%d-%d", id, j),
					Name: "Leak test",
				})
				_, _ = repo.GetByID(ctx, fmt.Sprintf("leak-test-%d-%d", id, j))
				_, _ = repo.List(ctx)
				_ = repo.Ping(ctx)
			}
		}(i)
	}

	wg.Wait()

	// Allow runtime scheduler to clean up terminated goroutines
	for attempt := 0; attempt < 5; attempt++ {
		runtime.Gosched()
		time.Sleep(20 * time.Millisecond)
	}

	finalGoroutines := runtime.NumGoroutine()
	delta := finalGoroutines - baseGoroutines
	if delta > 10 {
		t.Errorf("POTENTIAL GOROUTINE LEAK: base=%d, final=%d (delta=%d, spawned %d workers)",
			baseGoroutines, finalGoroutines, delta, workerCount)
	}
}
