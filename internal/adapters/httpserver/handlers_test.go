package httpserver_test

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/albin/build/internal/adapters/httpserver"
	"github.com/albin/build/internal/core/domain"
	"github.com/albin/build/internal/core/health"
)

type mockItemService struct {
	createFn  func(ctx context.Context, name, description string, status domain.ItemStatus) (domain.Item, error)
	getByIDFn func(ctx context.Context, id string) (domain.Item, error)
	listFn    func(ctx context.Context) ([]domain.Item, error)
	updateFn  func(ctx context.Context, id, name, description string, status domain.ItemStatus) (domain.Item, error)
	deleteFn  func(ctx context.Context, id string) error
}

func (m *mockItemService) Create(ctx context.Context, name, description string, status domain.ItemStatus) (domain.Item, error) {
	if m.createFn != nil {
		return m.createFn(ctx, name, description, status)
	}
	return domain.Item{}, errors.New("unimplemented")
}

func (m *mockItemService) GetByID(ctx context.Context, id string) (domain.Item, error) {
	if m.getByIDFn != nil {
		return m.getByIDFn(ctx, id)
	}
	return domain.Item{}, errors.New("unimplemented")
}

func (m *mockItemService) List(ctx context.Context) ([]domain.Item, error) {
	if m.listFn != nil {
		return m.listFn(ctx)
	}
	return nil, errors.New("unimplemented")
}

func (m *mockItemService) Update(ctx context.Context, id, name, description string, status domain.ItemStatus) (domain.Item, error) {
	if m.updateFn != nil {
		return m.updateFn(ctx, id, name, description, status)
	}
	return domain.Item{}, errors.New("unimplemented")
}

func (m *mockItemService) Delete(ctx context.Context, id string) error {
	if m.deleteFn != nil {
		return m.deleteFn(ctx, id)
	}
	return errors.New("unimplemented")
}

func TestHealthHandler_HandleHealth(t *testing.T) {
	t.Parallel()

	logger := slog.New(slog.NewJSONHandler(io.Discard, nil))

	tests := map[string]struct {
		wantStatus    int
		wantOK        bool
		wantStatusStr string
	}{
		"returns 200 with healthy status": {
			wantStatus:    http.StatusOK,
			wantOK:        true,
			wantStatusStr: "ok",
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			svc := health.NewService()
			handler := httpserver.NewHealthHandler(svc, logger)

			req := httptest.NewRequest(http.MethodGet, "/api/health", nil)
			rec := httptest.NewRecorder()

			handler.HandleHealth(rec, req)

			if rec.Code != tt.wantStatus {
				t.Errorf("status = %d, want %d", rec.Code, tt.wantStatus)
			}

			var resp httpserver.HealthResponse
			if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
				t.Fatalf("failed to decode response: %v", err)
			}

			if resp.OK != tt.wantOK {
				t.Errorf("resp.OK = %v, want %v", resp.OK, tt.wantOK)
			}
			if resp.Status != tt.wantStatusStr {
				t.Errorf("resp.Status = %q, want %q", resp.Status, tt.wantStatusStr)
			}
			if resp.Version != "1.0.0" {
				t.Errorf("resp.Version = %q, want %q", resp.Version, "1.0.0")
			}
		})
	}
}

func TestPageHandler_HandleIndex(t *testing.T) {
	t.Parallel()

	logger := slog.New(slog.NewJSONHandler(io.Discard, nil))

	tests := map[string]struct {
		wantStatus      int
		wantContentType string
	}{
		"returns 200 with HTML": {
			wantStatus:      http.StatusOK,
			wantContentType: "text/html; charset=utf-8",
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			svc := health.NewService()
			handler := httpserver.NewPageHandler(svc, logger)

			req := httptest.NewRequest(http.MethodGet, "/", nil)
			rec := httptest.NewRecorder()

			handler.HandleIndex(rec, req)

			if rec.Code != tt.wantStatus {
				t.Errorf("status = %d, want %d", rec.Code, tt.wantStatus)
			}

			got := rec.Header().Get("Content-Type")
			if got != tt.wantContentType {
				t.Errorf("Content-Type = %q, want %q", got, tt.wantContentType)
			}
		})
	}
}

func TestPageHandler_HandleHealthFragment(t *testing.T) {
	t.Parallel()

	logger := slog.New(slog.NewJSONHandler(io.Discard, nil))

	tests := map[string]struct {
		wantStatus      int
		wantContentType string
	}{
		"returns 200 with HTML fragment": {
			wantStatus:      http.StatusOK,
			wantContentType: "text/html; charset=utf-8",
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			svc := health.NewService()
			handler := httpserver.NewPageHandler(svc, logger)

			req := httptest.NewRequest(http.MethodGet, "/api/health/fragment", nil)
			rec := httptest.NewRecorder()

			handler.HandleHealthFragment(rec, req)

			if rec.Code != tt.wantStatus {
				t.Errorf("status = %d, want %d", rec.Code, tt.wantStatus)
			}

			got := rec.Header().Get("Content-Type")
			if got != tt.wantContentType {
				t.Errorf("Content-Type = %q, want %q", got, tt.wantContentType)
			}
		})
	}
}

func TestItemHandler_HandleList(t *testing.T) {
	t.Parallel()

	logger := slog.New(slog.NewJSONHandler(io.Discard, nil))

	tests := map[string]struct {
		mockSvc    *mockItemService
		wantStatus int
		wantCount  int
		wantRaw    string
	}{
		"returns empty JSON array on empty store": {
			mockSvc: &mockItemService{
				listFn: func(_ context.Context) ([]domain.Item, error) {
					return []domain.Item{}, nil
				},
			},
			wantStatus: http.StatusOK,
			wantCount:  0,
			wantRaw:    "[]\n",
		},
		"returns list of items": {
			mockSvc: &mockItemService{
				listFn: func(_ context.Context) ([]domain.Item, error) {
					return []domain.Item{
						{ID: "i1", Name: "Item 1", Status: domain.StatusActive},
						{ID: "i2", Name: "Item 2", Status: domain.StatusPending},
					}, nil
				},
			},
			wantStatus: http.StatusOK,
			wantCount:  2,
		},
		"internal service error returns 500 JSON": {
			mockSvc: &mockItemService{
				listFn: func(_ context.Context) ([]domain.Item, error) {
					return nil, errors.New("db error")
				},
			},
			wantStatus: http.StatusInternalServerError,
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			handler := httpserver.NewItemHandler(tt.mockSvc, logger)
			req := httptest.NewRequest(http.MethodGet, "/api/items", nil)
			rec := httptest.NewRecorder()

			handler.HandleList(rec, req)

			if rec.Code != tt.wantStatus {
				t.Errorf("status = %d, want %d", rec.Code, tt.wantStatus)
			}

			if tt.wantRaw != "" && rec.Body.String() != tt.wantRaw {
				t.Errorf("body = %q, want %q", rec.Body.String(), tt.wantRaw)
			}

			if tt.wantStatus == http.StatusOK {
				var items []httpserver.ItemResponse
				if err := json.NewDecoder(rec.Body).Decode(&items); err != nil {
					t.Fatalf("failed to decode response: %v", err)
				}
				if len(items) != tt.wantCount {
					t.Errorf("count = %d, want %d", len(items), tt.wantCount)
				}
			}
		})
	}
}

func TestItemHandler_HandleGetByID(t *testing.T) {
	t.Parallel()

	logger := slog.New(slog.NewJSONHandler(io.Discard, nil))

	tests := map[string]struct {
		id         string
		mockSvc    *mockItemService
		wantStatus int
		wantError  string
	}{
		"existing item returns 200 OK": {
			id: "item-123",
			mockSvc: &mockItemService{
				getByIDFn: func(_ context.Context, _ string) (domain.Item, error) {
					return domain.Item{ID: "item-123", Name: "Found", Status: domain.StatusActive}, nil
				},
			},
			wantStatus: http.StatusOK,
		},
		"empty id returns 400 validation error": {
			id:         "",
			mockSvc:    &mockItemService{},
			wantStatus: http.StatusBadRequest,
			wantError:  "validation_error",
		},
		"non-existent item returns 404 not found": {
			id: "missing-123",
			mockSvc: &mockItemService{
				getByIDFn: func(_ context.Context, _ string) (domain.Item, error) {
					return domain.Item{}, domain.ErrNotFound
				},
			},
			wantStatus: http.StatusNotFound,
			wantError:  "not_found",
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			handler := httpserver.NewItemHandler(tt.mockSvc, logger)
			req := httptest.NewRequest(http.MethodGet, "/api/items/"+tt.id, nil)
			req.SetPathValue("id", tt.id)
			rec := httptest.NewRecorder()

			handler.HandleGetByID(rec, req)

			if rec.Code != tt.wantStatus {
				t.Errorf("status = %d, want %d", rec.Code, tt.wantStatus)
			}

			if tt.wantError != "" {
				var errResp httpserver.ErrorResponse
				if err := json.NewDecoder(rec.Body).Decode(&errResp); err != nil {
					t.Fatalf("failed to decode error response: %v", err)
				}
				if errResp.Error != tt.wantError {
					t.Errorf("error = %q, want %q", errResp.Error, tt.wantError)
				}
			}
		})
	}
}

func TestItemHandler_HandleCreate(t *testing.T) {
	t.Parallel()

	logger := slog.New(slog.NewJSONHandler(io.Discard, nil))

	tests := map[string]struct {
		body       string
		mockSvc    *mockItemService
		wantStatus int
		wantCode   string
	}{
		"valid payload returns 201 created": {
			body: `{"name":"Hexagonal Architecture","description":"Ports and Adapters","status":"active"}`,
			mockSvc: &mockItemService{
				createFn: func(_ context.Context, name, description string, status domain.ItemStatus) (domain.Item, error) {
					return domain.Item{
						ID:          "item-uuid-1",
						Name:        name,
						Description: description,
						Status:      status,
						CreatedAt:   time.Now().UTC(),
						UpdatedAt:   time.Now().UTC(),
					}, nil
				},
			},
			wantStatus: http.StatusCreated,
		},
		"empty body returns 400 validation error": {
			body:       "",
			mockSvc:    &mockItemService{},
			wantStatus: http.StatusBadRequest,
			wantCode:   "validation_error",
		},
		"domain validation failure returns 400 validation error": {
			body: `{"name":"","description":"missing name"}`,
			mockSvc: &mockItemService{
				createFn: func(_ context.Context, _, _ string, _ domain.ItemStatus) (domain.Item, error) {
					return domain.Item{}, fmt.Errorf("%w: name cannot be empty", domain.ErrValidation)
				},
			},
			wantStatus: http.StatusBadRequest,
			wantCode:   "validation_error",
		},
		"duplicate conflict returns 409 conflict": {
			body: `{"name":"Duplicate Name"}`,
			mockSvc: &mockItemService{
				createFn: func(_ context.Context, _, _ string, _ domain.ItemStatus) (domain.Item, error) {
					return domain.Item{}, fmt.Errorf("%w: item already exists", domain.ErrConflict)
				},
			},
			wantStatus: http.StatusConflict,
			wantCode:   "conflict",
		},
		"body exceeding 1 MB returns 413 payload too large": {
			body:       `{"name":"` + strings.Repeat("A", 1024*1024+10) + `"}`,
			mockSvc:    &mockItemService{},
			wantStatus: http.StatusRequestEntityTooLarge,
			wantCode:   "payload_too_large",
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			handler := httpserver.NewItemHandler(tt.mockSvc, logger)
			req := httptest.NewRequest(http.MethodPost, "/api/items", strings.NewReader(tt.body))
			req.Header.Set("Content-Type", "application/json")
			rec := httptest.NewRecorder()

			handler.HandleCreate(rec, req)

			if rec.Code != tt.wantStatus {
				t.Errorf("status = %d, want %d", rec.Code, tt.wantStatus)
			}

			if tt.wantCode != "" {
				var errResp httpserver.ErrorResponse
				if err := json.NewDecoder(rec.Body).Decode(&errResp); err != nil {
					t.Fatalf("failed to decode error response: %v", err)
				}
				if errResp.Error != tt.wantCode {
					t.Errorf("error code = %q, want %q", errResp.Error, tt.wantCode)
				}
			}

			if tt.wantStatus == http.StatusCreated {
				loc := rec.Header().Get("Location")
				if !strings.HasPrefix(loc, "/api/items/") {
					t.Errorf("Location header = %q, want prefix /api/items/", loc)
				}
			}
		})
	}
}

func TestItemHandler_HandleUpdate(t *testing.T) {
	t.Parallel()

	logger := slog.New(slog.NewJSONHandler(io.Discard, nil))

	tests := map[string]struct {
		id         string
		body       string
		mockSvc    *mockItemService
		wantStatus int
		wantCode   string
	}{
		"valid update returns 200 OK": {
			id:   "item-123",
			body: `{"name":"Updated","description":"Updated desc","status":"completed"}`,
			mockSvc: &mockItemService{
				updateFn: func(_ context.Context, id, name, description string, status domain.ItemStatus) (domain.Item, error) {
					return domain.Item{ID: id, Name: name, Description: description, Status: status}, nil
				},
			},
			wantStatus: http.StatusOK,
		},
		"empty id returns 400 validation error": {
			id:         "",
			body:       `{"name":"Valid"}`,
			mockSvc:    &mockItemService{},
			wantStatus: http.StatusBadRequest,
			wantCode:   "validation_error",
		},
		"item not found returns 404": {
			id:   "missing",
			body: `{"name":"Valid","description":"","status":"active"}`,
			mockSvc: &mockItemService{
				updateFn: func(_ context.Context, _, _, _ string, _ domain.ItemStatus) (domain.Item, error) {
					return domain.Item{}, domain.ErrNotFound
				},
			},
			wantStatus: http.StatusNotFound,
			wantCode:   "not_found",
		},
		"validation failure returns 400": {
			id:   "item-123",
			body: `{"name":"","description":"","status":"active"}`,
			mockSvc: &mockItemService{
				updateFn: func(_ context.Context, _, _, _ string, _ domain.ItemStatus) (domain.Item, error) {
					return domain.Item{}, fmt.Errorf("%w: name cannot be empty", domain.ErrValidation)
				},
			},
			wantStatus: http.StatusBadRequest,
			wantCode:   "validation_error",
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			handler := httpserver.NewItemHandler(tt.mockSvc, logger)
			req := httptest.NewRequest(http.MethodPut, "/api/items/"+tt.id, strings.NewReader(tt.body))
			req.SetPathValue("id", tt.id)
			rec := httptest.NewRecorder()

			handler.HandleUpdate(rec, req)

			if rec.Code != tt.wantStatus {
				t.Errorf("status = %d, want %d", rec.Code, tt.wantStatus)
			}

			if tt.wantCode != "" {
				var errResp httpserver.ErrorResponse
				if err := json.NewDecoder(rec.Body).Decode(&errResp); err != nil {
					t.Fatalf("failed to decode error response: %v", err)
				}
				if errResp.Error != tt.wantCode {
					t.Errorf("error code = %q, want %q", errResp.Error, tt.wantCode)
				}
			}
		})
	}
}

func TestItemHandler_HandleDelete(t *testing.T) {
	t.Parallel()

	logger := slog.New(slog.NewJSONHandler(io.Discard, nil))

	tests := map[string]struct {
		id         string
		mockSvc    *mockItemService
		wantStatus int
		wantCode   string
	}{
		"successful delete returns 200 OK": {
			id: "item-del",
			mockSvc: &mockItemService{
				deleteFn: func(_ context.Context, _ string) error {
					return nil
				},
			},
			wantStatus: http.StatusOK,
		},
		"empty id returns 400": {
			id:         "",
			mockSvc:    &mockItemService{},
			wantStatus: http.StatusBadRequest,
			wantCode:   "validation_error",
		},
		"not found returns 404": {
			id: "missing",
			mockSvc: &mockItemService{
				deleteFn: func(_ context.Context, _ string) error {
					return domain.ErrNotFound
				},
			},
			wantStatus: http.StatusNotFound,
			wantCode:   "not_found",
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			handler := httpserver.NewItemHandler(tt.mockSvc, logger)
			req := httptest.NewRequest(http.MethodDelete, "/api/items/"+tt.id, nil)
			req.SetPathValue("id", tt.id)
			rec := httptest.NewRecorder()

			handler.HandleDelete(rec, req)

			if rec.Code != tt.wantStatus {
				t.Errorf("status = %d, want %d", rec.Code, tt.wantStatus)
			}

			if tt.wantCode != "" {
				var errResp httpserver.ErrorResponse
				if err := json.NewDecoder(rec.Body).Decode(&errResp); err != nil {
					t.Fatalf("failed to decode error response: %v", err)
				}
				if errResp.Error != tt.wantCode {
					t.Errorf("error code = %q, want %q", errResp.Error, tt.wantCode)
				}
			} else {
				var delResp httpserver.DeleteResponse
				if err := json.NewDecoder(rec.Body).Decode(&delResp); err != nil {
					t.Fatalf("failed to decode delete response: %v", err)
				}
				if !delResp.Success {
					t.Error("expected delete response success = true")
				}
			}
		})
	}
}

func TestRouter_IntegrationRoutes(t *testing.T) {
	t.Parallel()

	logger := slog.New(slog.NewJSONHandler(io.Discard, nil))
	healthSvc := health.NewService()
	itemSvc := &mockItemService{
		listFn: func(_ context.Context) ([]domain.Item, error) {
			return []domain.Item{
				{ID: "i1", Name: "Routed Item", Status: domain.StatusActive},
			}, nil
		},
	}

	router := httpserver.NewRouter(logger, healthSvc, itemSvc)

	req := httptest.NewRequest(http.MethodGet, "/api/items", nil)
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("GET /api/items returned status %d, want 200", rec.Code)
	}
}

func TestRouter_ViteAssetsRoute(t *testing.T) {
	tempDir := t.TempDir()
	assetsDir := filepath.Join(tempDir, "assets")
	if err := os.MkdirAll(assetsDir, 0o755); err != nil {
		t.Fatalf("failed to create temp assets dir: %v", err)
	}

	testFile := filepath.Join(assetsDir, "bundle.js")
	if err := os.WriteFile(testFile, []byte("console.log('vite-asset');"), 0o644); err != nil {
		t.Fatalf("failed to write temp asset file: %v", err)
	}

	t.Setenv("STATIC_DIR", tempDir)

	logger := slog.New(slog.NewJSONHandler(io.Discard, nil))
	healthSvc := health.NewService()
	itemSvc := &mockItemService{}

	router := httpserver.NewRouter(logger, healthSvc, itemSvc)

	req := httptest.NewRequest(http.MethodGet, "/assets/bundle.js", nil)
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("GET /assets/bundle.js returned status %d, want 200", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), "vite-asset") {
		t.Errorf("body = %q, want containing 'vite-asset'", rec.Body.String())
	}
}
