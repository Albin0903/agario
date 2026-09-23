// Package domain defines core business entities, value objects, and sentinel errors.
package domain

import "errors"

// Sentinel errors for the domain layer.
var (
	ErrNotFound     = errors.New("resource not found")
	ErrConflict     = errors.New("resource already exists")
	ErrUnauthorized = errors.New("unauthorized")
	ErrForbidden    = errors.New("forbidden")
	ErrValidation   = errors.New("validation error")
)
