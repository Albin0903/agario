package domain_test

import (
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/albin/build/internal/core/domain"
)

func TestNewItem(t *testing.T) {
	t.Parallel()

	tests := map[string]struct {
		id          string
		name        string
		description string
		status      domain.ItemStatus
		wantErr     bool
		errTarget   error
	}{
		"valid item pending": {
			id:          "item-01",
			name:        "Hexagonal Port Contracts",
			description: "Implement context-aware persistence contracts.",
			status:      domain.StatusPending,
			wantErr:     false,
		},
		"valid item active": {
			id:          "item-02",
			name:        "UI Skeleton Primitives",
			description: "Ensure CLS=0 layouts with proportional geometry.",
			status:      domain.StatusActive,
			wantErr:     false,
		},
		"empty id returns validation error": {
			id:          "",
			name:        "Valid Name",
			description: "Valid Description",
			status:      domain.StatusPending,
			wantErr:     true,
			errTarget:   domain.ErrValidation,
		},
		"whitespace id returns validation error": {
			id:          "   \t  ",
			name:        "Valid Name",
			description: "Valid Description",
			status:      domain.StatusPending,
			wantErr:     true,
			errTarget:   domain.ErrValidation,
		},
		"id exceeding 64 chars returns validation error": {
			id:          strings.Repeat("a", 65),
			name:        "Valid Name",
			description: "Valid Description",
			status:      domain.StatusPending,
			wantErr:     true,
			errTarget:   domain.ErrValidation,
		},
		"empty name returns validation error": {
			id:          "item-03",
			name:        "",
			description: "Valid Description",
			status:      domain.StatusPending,
			wantErr:     true,
			errTarget:   domain.ErrValidation,
		},
		"whitespace name returns validation error": {
			id:          "item-04",
			name:        "   \n\t  ",
			description: "Valid Description",
			status:      domain.StatusPending,
			wantErr:     true,
			errTarget:   domain.ErrValidation,
		},
		"name exceeding max length returns validation error": {
			id:          "item-05",
			name:        strings.Repeat("n", domain.MaxNameLength+1),
			description: "Valid Description",
			status:      domain.StatusPending,
			wantErr:     true,
			errTarget:   domain.ErrValidation,
		},
		"description exceeding max length returns validation error": {
			id:          "item-06",
			name:        "Valid Name",
			description: strings.Repeat("d", domain.MaxDescriptionLength+1),
			status:      domain.StatusPending,
			wantErr:     true,
			errTarget:   domain.ErrValidation,
		},
		"empty description is permitted": {
			id:          "item-07",
			name:        "Valid Name",
			description: "",
			status:      domain.StatusPending,
			wantErr:     false,
		},
		"invalid status returns validation error": {
			id:          "item-08",
			name:        "Valid Name",
			description: "Valid Description",
			status:      domain.ItemStatus("unknown_status"),
			wantErr:     true,
			errTarget:   domain.ErrValidation,
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			item, err := domain.NewItem(tt.id, tt.name, tt.description, tt.status)
			if tt.wantErr {
				if err == nil {
					t.Fatalf("NewItem() expected error, got nil")
				}
				if tt.errTarget != nil && !errors.Is(err, tt.errTarget) {
					t.Errorf("NewItem() error = %v, want target %v", err, tt.errTarget)
				}
				return
			}

			if err != nil {
				t.Fatalf("NewItem() unexpected error = %v", err)
			}

			if item.ID != strings.TrimSpace(tt.id) {
				t.Errorf("item.ID = %q, want %q", item.ID, strings.TrimSpace(tt.id))
			}
			if item.Name != strings.TrimSpace(tt.name) {
				t.Errorf("item.Name = %q, want %q", item.Name, strings.TrimSpace(tt.name))
			}
			if item.Description != strings.TrimSpace(tt.description) {
				t.Errorf("item.Description = %q, want %q", item.Description, strings.TrimSpace(tt.description))
			}
			if item.Status != tt.status {
				t.Errorf("item.Status = %q, want %q", item.Status, tt.status)
			}
			if item.CreatedAt.IsZero() {
				t.Error("item.CreatedAt should not be zero")
			}
			if item.UpdatedAt.IsZero() {
				t.Error("item.UpdatedAt should not be zero")
			}
		})
	}
}

func TestItem_Update(t *testing.T) {
	t.Parallel()

	tests := map[string]struct {
		initialStatus domain.ItemStatus
		newName       string
		newDesc       string
		wantErr       bool
		errTarget     error
	}{
		"successful update on active item": {
			initialStatus: domain.StatusActive,
			newName:       "Updated Title",
			newDesc:       "Updated description text.",
			wantErr:       false,
		},
		"empty name returns validation error": {
			initialStatus: domain.StatusActive,
			newName:       "   ",
			newDesc:       "Updated description text.",
			wantErr:       true,
			errTarget:     domain.ErrValidation,
		},
		"name exceeding max length returns validation error": {
			initialStatus: domain.StatusActive,
			newName:       strings.Repeat("x", domain.MaxNameLength+1),
			newDesc:       "Updated description text.",
			wantErr:       true,
			errTarget:     domain.ErrValidation,
		},
		"description exceeding max length returns validation error": {
			initialStatus: domain.StatusActive,
			newName:       "Valid Title",
			newDesc:       strings.Repeat("y", domain.MaxDescriptionLength+1),
			wantErr:       true,
			errTarget:     domain.ErrValidation,
		},
		"update rejected on archived item": {
			initialStatus: domain.StatusArchived,
			newName:       "Attempted Update",
			newDesc:       "Should not be allowed.",
			wantErr:       true,
			errTarget:     domain.ErrValidation,
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			item, err := domain.NewItem("item-up", "Initial Title", "Initial Desc", tt.initialStatus)
			if err != nil {
				t.Fatalf("failed to setup initial item: %v", err)
			}

			initialUpdatedAt := item.UpdatedAt
			time.Sleep(1 * time.Millisecond)

			updateErr := item.Update(tt.newName, tt.newDesc)
			if tt.wantErr {
				if updateErr == nil {
					t.Fatalf("Update() expected error, got nil")
				}
				if tt.errTarget != nil && !errors.Is(updateErr, tt.errTarget) {
					t.Errorf("Update() error = %v, want target %v", updateErr, tt.errTarget)
				}
				return
			}

			if updateErr != nil {
				t.Fatalf("Update() unexpected error = %v", updateErr)
			}

			if item.Name != strings.TrimSpace(tt.newName) {
				t.Errorf("item.Name = %q, want %q", item.Name, strings.TrimSpace(tt.newName))
			}
			if item.Description != strings.TrimSpace(tt.newDesc) {
				t.Errorf("item.Description = %q, want %q", item.Description, strings.TrimSpace(tt.newDesc))
			}
			if !item.UpdatedAt.After(initialUpdatedAt) && !item.UpdatedAt.Equal(initialUpdatedAt) {
				t.Error("item.UpdatedAt should be refreshed upon update")
			}
		})
	}
}

func TestItem_ChangeStatus(t *testing.T) {
	t.Parallel()

	tests := map[string]struct {
		initialStatus domain.ItemStatus
		targetStatus  domain.ItemStatus
		wantErr       bool
		errTarget     error
	}{
		"pending to active is valid": {
			initialStatus: domain.StatusPending,
			targetStatus:  domain.StatusActive,
			wantErr:       false,
		},
		"pending to archived is valid": {
			initialStatus: domain.StatusPending,
			targetStatus:  domain.StatusArchived,
			wantErr:       false,
		},
		"pending directly to completed is invalid": {
			initialStatus: domain.StatusPending,
			targetStatus:  domain.StatusCompleted,
			wantErr:       true,
			errTarget:     domain.ErrValidation,
		},
		"active to completed is valid": {
			initialStatus: domain.StatusActive,
			targetStatus:  domain.StatusCompleted,
			wantErr:       false,
		},
		"active to archived is valid": {
			initialStatus: domain.StatusActive,
			targetStatus:  domain.StatusArchived,
			wantErr:       false,
		},
		"active to pending is valid reset": {
			initialStatus: domain.StatusActive,
			targetStatus:  domain.StatusPending,
			wantErr:       false,
		},
		"completed to active is valid reopening": {
			initialStatus: domain.StatusCompleted,
			targetStatus:  domain.StatusActive,
			wantErr:       false,
		},
		"completed to archived is valid": {
			initialStatus: domain.StatusCompleted,
			targetStatus:  domain.StatusArchived,
			wantErr:       false,
		},
		"archived cannot transition to active": {
			initialStatus: domain.StatusArchived,
			targetStatus:  domain.StatusActive,
			wantErr:       true,
			errTarget:     domain.ErrValidation,
		},
		"archived cannot transition to pending": {
			initialStatus: domain.StatusArchived,
			targetStatus:  domain.StatusPending,
			wantErr:       true,
			errTarget:     domain.ErrValidation,
		},
		"same status is a no-op": {
			initialStatus: domain.StatusActive,
			targetStatus:  domain.StatusActive,
			wantErr:       false,
		},
		"transition to invalid status returns validation error": {
			initialStatus: domain.StatusActive,
			targetStatus:  domain.ItemStatus("corrupted"),
			wantErr:       true,
			errTarget:     domain.ErrValidation,
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			item, err := domain.NewItem("item-status", "Item Name", "Item Description", tt.initialStatus)
			if err != nil {
				t.Fatalf("failed to setup initial item: %v", err)
			}

			changeErr := item.ChangeStatus(tt.targetStatus)
			if tt.wantErr {
				if changeErr == nil {
					t.Fatalf("ChangeStatus() expected error, got nil")
				}
				if tt.errTarget != nil && !errors.Is(changeErr, tt.errTarget) {
					t.Errorf("ChangeStatus() error = %v, want target %v", changeErr, tt.errTarget)
				}
				return
			}

			if changeErr != nil {
				t.Fatalf("ChangeStatus() unexpected error = %v", changeErr)
			}

			if item.Status != tt.targetStatus {
				t.Errorf("item.Status = %q, want %q", item.Status, tt.targetStatus)
			}
		})
	}
}

func TestGenerateID(t *testing.T) {
	t.Parallel()

	id1, err1 := domain.GenerateID()
	if err1 != nil {
		t.Fatalf("GenerateID() error = %v", err1)
	}

	id2, err2 := domain.GenerateID()
	if err2 != nil {
		t.Fatalf("GenerateID() error = %v", err2)
	}

	if id1 == "" || id2 == "" {
		t.Error("GenerateID() should not return empty strings")
	}

	if id1 == id2 {
		t.Errorf("GenerateID() collision: %q == %q", id1, id2)
	}

	if len(id1) != 36 {
		t.Errorf("GenerateID() length = %d, want 36", len(id1))
	}
}
