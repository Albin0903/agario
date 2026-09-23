// Package httpserver provides HTTP handlers, middleware, and routing for the application.
package httpserver

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/albin/build/internal/adapters/http/views"
	"github.com/albin/build/internal/core/domain"
	"github.com/albin/build/internal/core/health"
)

// ItemResponse is the external JSON representation of a domain.Item entity.
type ItemResponse struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description"`
	Status      string `json:"status"`
	CreatedAt   string `json:"created_at"`
	UpdatedAt   string `json:"updated_at"`
}

// CreateItemRequest defines the payload for creating an item.
type CreateItemRequest struct {
	Name        string `json:"name"`
	Description string `json:"description"`
	Status      string `json:"status,omitempty"`
}

// UpdateItemRequest defines the payload for updating an item.
type UpdateItemRequest struct {
	Name        string `json:"name"`
	Description string `json:"description"`
	Status      string `json:"status"`
}

// DeleteResponse defines the standard JSON payload returned on successful deletion.
type DeleteResponse struct {
	Success bool `json:"success"`
}

// HealthResponse represents the health payload conforming to both App.tsx and PROJECT.md.
type HealthResponse struct {
	OK        bool      `json:"ok"`
	Status    string    `json:"status"`
	Version   string    `json:"version"`
	Uptime    string    `json:"uptime"`
	Timestamp time.Time `json:"timestamp"`
}

// ItemService defines the contract consumed by ItemHandler to manipulate business aggregates.
type ItemService interface {
	Create(ctx context.Context, name, description string, status domain.ItemStatus) (domain.Item, error)
	GetByID(ctx context.Context, id string) (domain.Item, error)
	List(ctx context.Context) ([]domain.Item, error)
	Update(ctx context.Context, id, name, description string, status domain.ItemStatus) (domain.Item, error)
	Delete(ctx context.Context, id string) error
}

func toItemResponse(item domain.Item) ItemResponse {
	return ItemResponse{
		ID:          item.ID,
		Name:        item.Name,
		Description: item.Description,
		Status:      string(item.Status),
		CreatedAt:   item.CreatedAt.UTC().Format(time.RFC3339),
		UpdatedAt:   item.UpdatedAt.UTC().Format(time.RFC3339),
	}
}

func toItemResponseList(items []domain.Item) []ItemResponse {
	if len(items) == 0 {
		return []ItemResponse{}
	}
	res := make([]ItemResponse, len(items))
	for i, it := range items {
		res[i] = toItemResponse(it)
	}
	return res
}

// HealthHandler handles health check endpoints.
type HealthHandler struct {
	service *health.Service
	logger  *slog.Logger
}

// NewHealthHandler creates a new HealthHandler.
func NewHealthHandler(svc *health.Service, logger *slog.Logger) *HealthHandler {
	return &HealthHandler{
		service: svc,
		logger:  logger,
	}
}

// HandleHealth responds with the application health status as JSON.
func (h *HealthHandler) HandleHealth(w http.ResponseWriter, r *http.Request) {
	status := h.service.Check()

	resp := HealthResponse{
		OK:        status.OK,
		Status:    "ok",
		Version:   "1.0.0",
		Uptime:    status.Uptime,
		Timestamp: status.Timestamp,
	}

	if err := respondJSON(w, http.StatusOK, resp); err != nil {
		respondError(w, r, h.logger, err)
	}
}

// PageHandler handles server-rendered page endpoints using Templ.
type PageHandler struct {
	healthService *health.Service
	logger        *slog.Logger
}

// NewPageHandler creates a new PageHandler.
func NewPageHandler(healthSvc *health.Service, logger *slog.Logger) *PageHandler {
	return &PageHandler{
		healthService: healthSvc,
		logger:        logger,
	}
}

// HandleIndex serves the SSR index page compiled via Templ.
func (h *PageHandler) HandleIndex(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}

	st := h.healthService.Check()

	props := views.HomeProps{
		Title:       "Application",
		Description: "Socle de développement prêt pour vos fonctionnalités métier.",
		Health: views.HealthCardProps{
			OK:        st.OK,
			Uptime:    st.Uptime,
			Timestamp: st.Timestamp.Format("2006-01-02 15:04:05 UTC"),
		},
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	//nolint:contextcheck // Templ components accept context during Render, not instantiation.
	if err := views.Home(props).Render(r.Context(), w); err != nil {
		respondError(w, r, h.logger, fmt.Errorf("rendering home view: %w", err))
		return
	}
}

// HandleHealthFragment serves the dynamic HTMX partial fragment for the health card.
func (h *PageHandler) HandleHealthFragment(w http.ResponseWriter, r *http.Request) {
	st := h.healthService.Check()

	props := views.HealthCardProps{
		OK:        st.OK,
		Uptime:    st.Uptime,
		Timestamp: st.Timestamp.Format("2006-01-02 15:04:05 UTC"),
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	//nolint:contextcheck // Templ components accept context during Render, not instantiation.
	if err := views.HealthCard(props).Render(r.Context(), w); err != nil {
		respondError(w, r, h.logger, fmt.Errorf("rendering health card fragment: %w", err))
		return
	}
}

// ItemHandler handles HTTP CRUD operations for Item entities.
type ItemHandler struct {
	service ItemService
	logger  *slog.Logger
}

// NewItemHandler creates a new ItemHandler with injected dependencies.
func NewItemHandler(service ItemService, logger *slog.Logger) *ItemHandler {
	return &ItemHandler{
		service: service,
		logger:  logger,
	}
}

// HandleList handles GET /api/items.
func (h *ItemHandler) HandleList(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	items, err := h.service.List(ctx)
	if err != nil {
		respondError(w, r, h.logger, err)
		return
	}

	resp := toItemResponseList(items)
	if err := respondJSON(w, http.StatusOK, resp); err != nil {
		respondError(w, r, h.logger, err)
	}
}

// HandleGetByID handles GET /api/items/{id}.
func (h *ItemHandler) HandleGetByID(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	id := strings.TrimSpace(r.PathValue("id"))
	if id == "" {
		respondError(w, r, h.logger, fmt.Errorf("%w: item id is required", domain.ErrValidation))
		return
	}

	item, err := h.service.GetByID(ctx, id)
	if err != nil {
		respondError(w, r, h.logger, err)
		return
	}

	resp := toItemResponse(item)
	if err := respondJSON(w, http.StatusOK, resp); err != nil {
		respondError(w, r, h.logger, err)
	}
}

// HandleCreate handles POST /api/items.
func (h *ItemHandler) HandleCreate(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	// Limit body size to 1 MB to prevent denial of service from unbounded memory reads.
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)

	var req CreateItemRequest
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&req); err != nil {
		var maxBytesErr *http.MaxBytesError
		if errors.As(err, &maxBytesErr) {
			respondError(w, r, h.logger, err)
			return
		}
		if errors.Is(err, io.EOF) {
			respondError(w, r, h.logger, fmt.Errorf("%w: request body must not be empty", domain.ErrValidation))
			return
		}
		respondError(w, r, h.logger, fmt.Errorf("%w: invalid request json: %v", domain.ErrValidation, err))
		return
	}

	status := domain.ItemStatus(strings.TrimSpace(req.Status))
	if status == "" {
		status = domain.StatusPending
	}

	item, err := h.service.Create(ctx, req.Name, req.Description, status)
	if err != nil {
		respondError(w, r, h.logger, err)
		return
	}

	resp := toItemResponse(item)
	w.Header().Set("Location", fmt.Sprintf("/api/items/%s", item.ID))
	if err := respondJSON(w, http.StatusCreated, resp); err != nil {
		respondError(w, r, h.logger, err)
	}
}

// HandleUpdate handles PUT /api/items/{id}.
func (h *ItemHandler) HandleUpdate(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	id := strings.TrimSpace(r.PathValue("id"))
	if id == "" {
		respondError(w, r, h.logger, fmt.Errorf("%w: item id is required", domain.ErrValidation))
		return
	}

	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)

	var req UpdateItemRequest
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&req); err != nil {
		var maxBytesErr *http.MaxBytesError
		if errors.As(err, &maxBytesErr) {
			respondError(w, r, h.logger, err)
			return
		}
		if errors.Is(err, io.EOF) {
			respondError(w, r, h.logger, fmt.Errorf("%w: request body must not be empty", domain.ErrValidation))
			return
		}
		respondError(w, r, h.logger, fmt.Errorf("%w: invalid request json: %v", domain.ErrValidation, err))
		return
	}

	status := domain.ItemStatus(strings.TrimSpace(req.Status))
	item, err := h.service.Update(ctx, id, req.Name, req.Description, status)
	if err != nil {
		respondError(w, r, h.logger, err)
		return
	}

	resp := toItemResponse(item)
	if err := respondJSON(w, http.StatusOK, resp); err != nil {
		respondError(w, r, h.logger, err)
	}
}

// HandleDelete handles DELETE /api/items/{id}.
func (h *ItemHandler) HandleDelete(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	id := strings.TrimSpace(r.PathValue("id"))
	if id == "" {
		respondError(w, r, h.logger, fmt.Errorf("%w: item id is required", domain.ErrValidation))
		return
	}

	if err := h.service.Delete(ctx, id); err != nil {
		respondError(w, r, h.logger, err)
		return
	}

	resp := DeleteResponse{Success: true}
	if err := respondJSON(w, http.StatusOK, resp); err != nil {
		respondError(w, r, h.logger, err)
	}
}
