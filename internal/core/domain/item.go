// Package domain defines core business entities, value objects, and sentinel errors.
package domain

import (
	"crypto/rand"
	"fmt"
	"strings"
	"time"
)

// ItemStatus represents the lifecycle state of an Item entity.
type ItemStatus string

// Supported lifecycle statuses for Item entities.
const (
	StatusPending   ItemStatus = "pending"
	StatusActive    ItemStatus = "active"
	StatusCompleted ItemStatus = "completed"
	StatusArchived  ItemStatus = "archived"
)

// MaxNameLength defines the maximum allowable rune count for an Item name to prevent uncontrolled memory allocation.
const MaxNameLength = 100

// MaxDescriptionLength defines the maximum allowable rune count for an Item description.
const MaxDescriptionLength = 1000

// IsValid checks whether the status matches one of the allowable domain states.
func (s ItemStatus) IsValid() bool {
	switch s {
	case StatusPending, StatusActive, StatusCompleted, StatusArchived:
		return true
	default:
		return false
	}
}

// Item represents a canonical business entity within the application domain.
type Item struct {
	ID          string     `json:"id"`
	Name        string     `json:"name"`
	Description string     `json:"description"`
	Status      ItemStatus `json:"status"`
	CreatedAt   time.Time  `json:"created_at"`
	UpdatedAt   time.Time  `json:"updated_at"`
}

// NewItem instantiates an Item entity enforcing business invariants and setting UTC timestamps.
func NewItem(id, name, description string, status ItemStatus) (Item, error) {
	now := time.Now().UTC()
	return ReconstituteItem(id, name, description, status, now, now)
}

// ReconstituteItem restores an Item entity from persistence while verifying that all invariants hold.
func ReconstituteItem(id, name, description string, status ItemStatus, createdAt, updatedAt time.Time) (Item, error) {
	trimmedID := strings.TrimSpace(id)
	if trimmedID == "" {
		return Item{}, fmt.Errorf("%w: item id cannot be empty", ErrValidation)
	}
	if len(trimmedID) > 64 {
		return Item{}, fmt.Errorf("%w: item id exceeds 64 characters limit", ErrValidation)
	}

	trimmedName := strings.TrimSpace(name)
	if trimmedName == "" {
		return Item{}, fmt.Errorf("%w: item name cannot be empty", ErrValidation)
	}
	if len([]rune(trimmedName)) > MaxNameLength {
		return Item{}, fmt.Errorf("%w: item name exceeds %d characters limit", ErrValidation, MaxNameLength)
	}

	trimmedDesc := strings.TrimSpace(description)
	if len([]rune(trimmedDesc)) > MaxDescriptionLength {
		return Item{}, fmt.Errorf("%w: item description exceeds %d characters limit", ErrValidation, MaxDescriptionLength)
	}

	if !status.IsValid() {
		return Item{}, fmt.Errorf("%w: invalid item status %q", ErrValidation, status)
	}

	if createdAt.IsZero() {
		createdAt = time.Now().UTC()
	}
	if updatedAt.IsZero() {
		updatedAt = createdAt
	}

	return Item{
		ID:          trimmedID,
		Name:        trimmedName,
		Description: trimmedDesc,
		Status:      status,
		CreatedAt:   createdAt.UTC(),
		UpdatedAt:   updatedAt.UTC(),
	}, nil
}

// Update modifies the mutable textual attributes of an existing item.
// Mutations are forbidden on archived items to preserve historical audit invariants.
func (i *Item) Update(name, description string) error {
	if i.Status == StatusArchived {
		return fmt.Errorf("%w: cannot update an archived item", ErrValidation)
	}

	trimmedName := strings.TrimSpace(name)
	if trimmedName == "" {
		return fmt.Errorf("%w: item name cannot be empty", ErrValidation)
	}
	if len([]rune(trimmedName)) > MaxNameLength {
		return fmt.Errorf("%w: item name exceeds %d characters limit", ErrValidation, MaxNameLength)
	}

	trimmedDesc := strings.TrimSpace(description)
	if len([]rune(trimmedDesc)) > MaxDescriptionLength {
		return fmt.Errorf("%w: item description exceeds %d characters limit", ErrValidation, MaxDescriptionLength)
	}

	i.Name = trimmedName
	i.Description = trimmedDesc
	i.UpdatedAt = time.Now().UTC()
	return nil
}

// ChangeStatus transitions the item to a new state governed by the domain lifecycle matrix.
func (i *Item) ChangeStatus(newStatus ItemStatus) error {
	if !newStatus.IsValid() {
		return fmt.Errorf("%w: invalid item status %q", ErrValidation, newStatus)
	}

	if i.Status == newStatus {
		return nil
	}

	if i.Status == StatusArchived {
		return fmt.Errorf("%w: cannot transition from archived status", ErrValidation)
	}

	switch i.Status {
	case StatusPending:
		// Pending items must be activated before they can be completed.
		if newStatus != StatusActive && newStatus != StatusArchived {
			return fmt.Errorf("%w: invalid transition from %q to %q", ErrValidation, i.Status, newStatus)
		}
	case StatusActive:
		// Active items can complete, reset to pending, or be archived.
		if newStatus != StatusCompleted && newStatus != StatusArchived && newStatus != StatusPending {
			return fmt.Errorf("%w: invalid transition from %q to %q", ErrValidation, i.Status, newStatus)
		}
	case StatusCompleted:
		// Completed items can reopen to active or be archived; direct reset to pending is rejected.
		if newStatus != StatusActive && newStatus != StatusArchived {
			return fmt.Errorf("%w: invalid transition from %q to %q", ErrValidation, i.Status, newStatus)
		}
	}

	i.Status = newStatus
	i.UpdatedAt = time.Now().UTC()
	return nil
}

// GenerateID produces an RFC 4122 v4 UUID string using the standard library crypto/rand
// to avoid third-party UUID package dependencies.
func GenerateID() (string, error) {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", fmt.Errorf("generating crypto random bytes: %w", err)
	}
	// Set version 4 bits
	b[6] = (b[6] & 0x0f) | 0x40
	// Set variant bits (RFC 4122)
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%08x-%04x-%04x-%04x-%012x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:16]), nil
}
