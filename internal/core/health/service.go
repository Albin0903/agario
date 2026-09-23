// Package health provides health check functionality for the application.
package health

import "time"

// Status represents the health status of the application.
type Status struct {
	OK        bool      `json:"ok"`
	Uptime    string    `json:"uptime"`
	Timestamp time.Time `json:"timestamp"`
}

// Service provides health check functionality.
type Service struct {
	startedAt time.Time
}

// NewService creates a new health service.
func NewService() *Service {
	return &Service{
		startedAt: time.Now(),
	}
}

// Check returns the current health status.
func (s *Service) Check() Status {
	return Status{
		OK:        true,
		Uptime:    time.Since(s.startedAt).Round(time.Second).String(),
		Timestamp: time.Now().UTC(),
	}
}
