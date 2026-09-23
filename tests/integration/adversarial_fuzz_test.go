//go:build integration

package integration_test

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/albin/build/internal/adapters/httpserver"
	"github.com/albin/build/internal/core/domain"
	"github.com/albin/build/internal/core/health"
)

// Helper to decode ErrorResponse and assert JSON structure.
func assertErrorResponse(t *testing.T, resp *http.Response, wantStatus int, wantErrCode string) httpserver.ErrorResponse {
	t.Helper()

	if resp.StatusCode != wantStatus {
		body, _ := io.ReadAll(resp.Body)
		t.Fatalf("status = %d, want %d; body: %s", resp.StatusCode, wantStatus, string(body))
	}

	contentType := resp.Header.Get("Content-Type")
	if !strings.HasPrefix(contentType, "application/json") {
		t.Errorf("expected Content-Type application/json, got %q", contentType)
	}

	var errResp httpserver.ErrorResponse
	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatalf("failed to read response body: %v", err)
	}

	if err := json.Unmarshal(bodyBytes, &errResp); err != nil {
		t.Fatalf("response is not valid ErrorResponse JSON: %v; raw body: %s", err, string(bodyBytes))
	}

	if wantErrCode != "" && errResp.Error != wantErrCode {
		t.Errorf("error code = %q, want %q; message: %q", errResp.Error, wantErrCode, errResp.Message)
	}

	if errResp.Message == "" {
		t.Errorf("expected non-empty message in ErrorResponse, got empty string")
	}

	// Verify no Go stack trace or sensitive panic information is leaked
	bodyStr := string(bodyBytes)
	forbiddenSnippets := []string{
		"goroutine ",
		".go:",
		"runtime/debug.Stack",
		"panic:",
	}
	for _, snippet := range forbiddenSnippets {
		if strings.Contains(bodyStr, snippet) {
			t.Errorf("detected leaked diagnostic/stack snippet %q in response: %s", snippet, bodyStr)
		}
	}

	return errResp
}

func TestAdversarial_MalformedPayloads(t *testing.T) {
	srv, _ := setupTestServer()
	defer srv.Close()

	client := srv.Client()

	tests := map[string]struct {
		method      string
		urlPath     string
		body        string
		contentType string
		wantStatus  int
		wantErrCode string
	}{
		"POST malformed JSON truncated": {
			method:      http.MethodPost,
			urlPath:     "/api/items",
			body:        `{"name": "test"`,
			contentType: "application/json",
			wantStatus:  http.StatusBadRequest,
			wantErrCode: "validation_error",
		},
		"POST malformed JSON double commas": {
			method:      http.MethodPost,
			urlPath:     "/api/items",
			body:        `{"name": "test",,}`,
			contentType: "application/json",
			wantStatus:  http.StatusBadRequest,
			wantErrCode: "validation_error",
		},
		"POST plain text non-JSON": {
			method:      http.MethodPost,
			urlPath:     "/api/items",
			body:        `this is not json at all`,
			contentType: "application/json",
			wantStatus:  http.StatusBadRequest,
			wantErrCode: "validation_error",
		},
		"POST inverted brackets": {
			method:      http.MethodPost,
			urlPath:     "/api/items",
			body:        `}{`,
			contentType: "application/json",
			wantStatus:  http.StatusBadRequest,
			wantErrCode: "validation_error",
		},
		"POST XML payload": {
			method:      http.MethodPost,
			urlPath:     "/api/items",
			body:        `<item><name>test</name></item>`,
			contentType: "application/xml",
			wantStatus:  http.StatusBadRequest,
			wantErrCode: "validation_error",
		},
		"POST empty body": {
			method:      http.MethodPost,
			urlPath:     "/api/items",
			body:        "",
			contentType: "application/json",
			wantStatus:  http.StatusBadRequest,
			wantErrCode: "validation_error",
		},
		"POST whitespace only body": {
			method:      http.MethodPost,
			urlPath:     "/api/items",
			body:        "   \n\t\r\n   ",
			contentType: "application/json",
			wantStatus:  http.StatusBadRequest,
			wantErrCode: "validation_error",
		},
		"POST null JSON literal": {
			method:      http.MethodPost,
			urlPath:     "/api/items",
			body:        "null",
			contentType: "application/json",
			wantStatus:  http.StatusBadRequest,
			wantErrCode: "validation_error",
		},
		"POST empty JSON object": {
			method:      http.MethodPost,
			urlPath:     "/api/items",
			body:        "{}",
			contentType: "application/json",
			wantStatus:  http.StatusBadRequest,
			wantErrCode: "validation_error",
		},
		"POST JSON array instead of object": {
			method:      http.MethodPost,
			urlPath:     "/api/items",
			body:        `[{"name":"test"}]`,
			contentType: "application/json",
			wantStatus:  http.StatusBadRequest,
			wantErrCode: "validation_error",
		},
		"POST unexpected type number for name": {
			method:      http.MethodPost,
			urlPath:     "/api/items",
			body:        `{"name": 12345, "description": "desc"}`,
			contentType: "application/json",
			wantStatus:  http.StatusBadRequest,
			wantErrCode: "validation_error",
		},
		"POST unexpected type boolean for name": {
			method:      http.MethodPost,
			urlPath:     "/api/items",
			body:        `{"name": true}`,
			contentType: "application/json",
			wantStatus:  http.StatusBadRequest,
			wantErrCode: "validation_error",
		},
		"POST unexpected type object for name": {
			method:      http.MethodPost,
			urlPath:     "/api/items",
			body:        `{"name": {"first": "bad"}}`,
			contentType: "application/json",
			wantStatus:  http.StatusBadRequest,
			wantErrCode: "validation_error",
		},
		"POST disallowed unknown field injected": {
			method:      http.MethodPost,
			urlPath:     "/api/items",
			body:        `{"name": "Valid", "injected_field": "exploit"}`,
			contentType: "application/json",
			wantStatus:  http.StatusBadRequest,
			wantErrCode: "validation_error",
		},
		"POST disallowed ID field on creation": {
			method:      http.MethodPost,
			urlPath:     "/api/items",
			body:        `{"name": "Valid", "id": "custom-uuid-forbidden"}`,
			contentType: "application/json",
			wantStatus:  http.StatusBadRequest,
			wantErrCode: "validation_error",
		},
		"PUT malformed JSON on existing item": {
			method:      http.MethodPut,
			urlPath:     "/api/items/seed-item-1",
			body:        `{"name": "broken"`,
			contentType: "application/json",
			wantStatus:  http.StatusBadRequest,
			wantErrCode: "validation_error",
		},
		"PUT unexpected unknown field on existing item": {
			method:      http.MethodPut,
			urlPath:     "/api/items/seed-item-1",
			body:        `{"name": "New Name", "extra": "unauthorized"}`,
			contentType: "application/json",
			wantStatus:  http.StatusBadRequest,
			wantErrCode: "validation_error",
		},
	}

	for name, tc := range tests {
		t.Run(name, func(t *testing.T) {
			req, err := http.NewRequest(tc.method, srv.URL+tc.urlPath, strings.NewReader(tc.body))
			if err != nil {
				t.Fatalf("failed to create request: %v", err)
			}
			req.Header.Set("Content-Type", tc.contentType)

			resp, err := client.Do(req)
			if err != nil {
				t.Fatalf("request failed: %v", err)
			}
			defer func() { _ = resp.Body.Close() }()

			assertErrorResponse(t, resp, tc.wantStatus, tc.wantErrCode)
		})
	}
}

func TestAdversarial_PayloadSizeLimitExceeded(t *testing.T) {
	srv, _ := setupTestServer()
	defer srv.Close()

	client := srv.Client()

	tests := map[string]struct {
		method  string
		urlPath string
		size    int
	}{
		"POST 1MB + 10 bytes payload": {
			method:  http.MethodPost,
			urlPath: "/api/items",
			size:    (1 << 20) + 10,
		},
		"POST 2MB payload": {
			method:  http.MethodPost,
			urlPath: "/api/items",
			size:    2 << 20,
		},
		"PUT 1.5MB payload": {
			method:  http.MethodPut,
			urlPath: "/api/items/seed-item-1",
			size:    (3 << 19),
		},
	}

	for name, tc := range tests {
		t.Run(name, func(t *testing.T) {
			largeName := strings.Repeat("A", tc.size)
			largeBody := fmt.Sprintf(`{"name": %q}`, largeName)

			req, err := http.NewRequest(tc.method, srv.URL+tc.urlPath, strings.NewReader(largeBody))
			if err != nil {
				t.Fatalf("failed to build request: %v", err)
			}
			req.Header.Set("Content-Type", "application/json")

			resp, err := client.Do(req)
			if err != nil {
				t.Fatalf("request failed: %v", err)
			}
			defer func() { _ = resp.Body.Close() }()

			assertErrorResponse(t, resp, http.StatusRequestEntityTooLarge, "payload_too_large")
		})
	}
}

func TestAdversarial_BoundaryAndInjectionStrings(t *testing.T) {
	srv, _ := setupTestServer()
	defer srv.Close()

	client := srv.Client()

	// 1. Boundary: Exactly 100 runes name -> MUST SUCCEED (201)
	name100 := strings.Repeat("a", 100)
	payload100 := fmt.Sprintf(`{"name": %q, "description": "boundary 100"}`, name100)
	resp, err := client.Post(srv.URL+"/api/items", "application/json", strings.NewReader(payload100))
	if err != nil {
		t.Fatalf("POST failed: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusCreated {
		t.Errorf("100 runes name status = %d, want 201", resp.StatusCode)
	}

	// 2. Boundary: 101 runes name -> MUST FAIL (400 validation_error)
	name101 := strings.Repeat("a", 101)
	payload101 := fmt.Sprintf(`{"name": %q}`, name101)
	resp101, err := client.Post(srv.URL+"/api/items", "application/json", strings.NewReader(payload101))
	if err != nil {
		t.Fatalf("POST failed: %v", err)
	}
	defer func() { _ = resp101.Body.Close() }()
	assertErrorResponse(t, resp101, http.StatusBadRequest, "validation_error")

	// 3. Boundary: Multi-byte unicode: exactly 100 4-byte runes -> MUST SUCCEED (201)
	multiByte100 := strings.Repeat("\U00020000", 100) // 100 runes, 400 bytes
	payloadMultiByte100 := fmt.Sprintf(`{"name": %q, "description": "unicode test"}`, multiByte100)
	respMultiByte, err := client.Post(srv.URL+"/api/items", "application/json", strings.NewReader(payloadMultiByte100))
	if err != nil {
		t.Fatalf("POST failed: %v", err)
	}
	defer func() { _ = respMultiByte.Body.Close() }()
	if respMultiByte.StatusCode != http.StatusCreated {
		t.Errorf("100 multi-byte runes name status = %d, want 201", respMultiByte.StatusCode)
	}

	// 4. Boundary: Multi-byte unicode: 101 runes -> MUST FAIL (400 validation_error)
	multiByte101 := strings.Repeat("\U00020000", 101)
	payloadMultiByte101 := fmt.Sprintf(`{"name": %q}`, multiByte101)
	respMultiByte101, err := client.Post(srv.URL+"/api/items", "application/json", strings.NewReader(payloadMultiByte101))
	if err != nil {
		t.Fatalf("POST failed: %v", err)
	}
	defer func() { _ = respMultiByte101.Body.Close() }()
	assertErrorResponse(t, respMultiByte101, http.StatusBadRequest, "validation_error")

	// 5. Boundary: Exactly 1000 runes description -> MUST SUCCEED (201)
	desc1000 := strings.Repeat("d", 1000)
	payloadDesc1000 := fmt.Sprintf(`{"name": "Valid Name", "description": %q}`, desc1000)
	respDesc, err := client.Post(srv.URL+"/api/items", "application/json", strings.NewReader(payloadDesc1000))
	if err != nil {
		t.Fatalf("POST failed: %v", err)
	}
	defer func() { _ = respDesc.Body.Close() }()
	if respDesc.StatusCode != http.StatusCreated {
		t.Errorf("1000 runes description status = %d, want 201", respDesc.StatusCode)
	}

	// 6. Boundary: 1001 runes description -> MUST FAIL (400 validation_error)
	desc1001 := strings.Repeat("d", 1001)
	payloadDesc1001 := fmt.Sprintf(`{"name": "Valid Name", "description": %q}`, desc1001)
	respDesc101, err := client.Post(srv.URL+"/api/items", "application/json", strings.NewReader(payloadDesc1001))
	if err != nil {
		t.Fatalf("POST failed: %v", err)
	}
	defer func() { _ = respDesc101.Body.Close() }()
	assertErrorResponse(t, respDesc101, http.StatusBadRequest, "validation_error")

	// 7. SQL Injection string safety: accepts safely as string, does not crash or panic
	sqlPayload := `{"name": "' OR 1=1; DROP TABLE items; --", "description": "SQLi attempt"}`
	respSQL, err := client.Post(srv.URL+"/api/items", "application/json", strings.NewReader(sqlPayload))
	if err != nil {
		t.Fatalf("POST failed: %v", err)
	}
	defer func() { _ = respSQL.Body.Close() }()
	if respSQL.StatusCode != http.StatusCreated {
		t.Errorf("SQL string in name status = %d, want 201", respSQL.StatusCode)
	}

	// 8. XSS payload in name: accepts safely as string, does not crash or panic
	xssPayload := `{"name": "<script>alert('xss')</script>", "description": "<img src=x onerror=alert(1)>"}`
	respXSS, err := client.Post(srv.URL+"/api/items", "application/json", strings.NewReader(xssPayload))
	if err != nil {
		t.Fatalf("POST failed: %v", err)
	}
	defer func() { _ = respXSS.Body.Close() }()
	if respXSS.StatusCode != http.StatusCreated {
		t.Errorf("XSS string in name status = %d, want 201", respXSS.StatusCode)
	}
}

func TestAdversarial_InvalidStatusesAndStateTransitions(t *testing.T) {
	srv, _ := setupTestServer()
	defer srv.Close()

	client := srv.Client()

	// 1. Invalid status on Create -> 400 validation_error
	invalidStatuses := []string{
		"unknown",
		"PENDING",
		"ACTIVE",
		"COMPLETED",
		"deleted",
		"draft",
		"123",
	}
	for _, st := range invalidStatuses {
		payload := fmt.Sprintf(`{"name": "Test Item", "status": %q}`, st)
		resp, err := client.Post(srv.URL+"/api/items", "application/json", strings.NewReader(payload))
		if err != nil {
			t.Fatalf("POST failed: %v", err)
		}
		assertErrorResponse(t, resp, http.StatusBadRequest, "validation_error")
		_ = resp.Body.Close()
	}

	// 2. Create item with status "pending"
	createPending := `{"name": "Pending Item", "status": "pending"}`
	resp, err := client.Post(srv.URL+"/api/items", "application/json", strings.NewReader(createPending))
	if err != nil {
		t.Fatalf("POST failed: %v", err)
	}
	var created httpserver.ItemResponse
	_ = json.NewDecoder(resp.Body).Decode(&created)
	_ = resp.Body.Close()

	if created.Status != "pending" {
		t.Fatalf("created.Status = %q, want 'pending'", created.Status)
	}

	// 3. State Transition Violation: pending -> completed directly (ILLEGAL)
	illegalCompleted := `{"name": "Pending Item", "description": "", "status": "completed"}`
	req, _ := http.NewRequest(http.MethodPut, srv.URL+"/api/items/"+created.ID, strings.NewReader(illegalCompleted))
	req.Header.Set("Content-Type", "application/json")
	resp, err = client.Do(req)
	if err != nil {
		t.Fatalf("PUT failed: %v", err)
	}
	assertErrorResponse(t, resp, http.StatusBadRequest, "validation_error")
	_ = resp.Body.Close()

	// 4. Valid Transition: pending -> active (LEGAL)
	activatePayload := `{"name": "Active Item", "description": "", "status": "active"}`
	req, _ = http.NewRequest(http.MethodPut, srv.URL+"/api/items/"+created.ID, strings.NewReader(activatePayload))
	req.Header.Set("Content-Type", "application/json")
	resp, err = client.Do(req)
	if err != nil {
		t.Fatalf("PUT failed: %v", err)
	}
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("activate status = %d, want 200", resp.StatusCode)
	}
	_ = resp.Body.Close()

	// 5. Valid Transition: active -> completed (LEGAL)
	completePayload := `{"name": "Completed Item", "description": "", "status": "completed"}`
	req, _ = http.NewRequest(http.MethodPut, srv.URL+"/api/items/"+created.ID, strings.NewReader(completePayload))
	req.Header.Set("Content-Type", "application/json")
	resp, err = client.Do(req)
	if err != nil {
		t.Fatalf("PUT failed: %v", err)
	}
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("complete status = %d, want 200", resp.StatusCode)
	}
	_ = resp.Body.Close()

	// 6. State Transition Violation: completed -> pending (ILLEGAL)
	illegalReset := `{"name": "Completed Item", "description": "", "status": "pending"}`
	req, _ = http.NewRequest(http.MethodPut, srv.URL+"/api/items/"+created.ID, strings.NewReader(illegalReset))
	req.Header.Set("Content-Type", "application/json")
	resp, err = client.Do(req)
	if err != nil {
		t.Fatalf("PUT failed: %v", err)
	}
	assertErrorResponse(t, resp, http.StatusBadRequest, "validation_error")
	_ = resp.Body.Close()

	// 7. Valid Transition: completed -> archived (LEGAL)
	archivePayload := `{"name": "Archived Item", "description": "", "status": "archived"}`
	req, _ = http.NewRequest(http.MethodPut, srv.URL+"/api/items/"+created.ID, strings.NewReader(archivePayload))
	req.Header.Set("Content-Type", "application/json")
	resp, err = client.Do(req)
	if err != nil {
		t.Fatalf("PUT failed: %v", err)
	}
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("archive status = %d, want 200", resp.StatusCode)
	}
	_ = resp.Body.Close()

	// 8. State Transition Violation: archived -> active (ILLEGAL)
	reopenArchived := `{"name": "Archived Item", "description": "", "status": "active"}`
	req, _ = http.NewRequest(http.MethodPut, srv.URL+"/api/items/"+created.ID, strings.NewReader(reopenArchived))
	req.Header.Set("Content-Type", "application/json")
	resp, err = client.Do(req)
	if err != nil {
		t.Fatalf("PUT failed: %v", err)
	}
	assertErrorResponse(t, resp, http.StatusBadRequest, "validation_error")
	_ = resp.Body.Close()

	// 9. Mutating textual fields on archived item (ILLEGAL)
	modifyArchived := `{"name": "New Name Archived", "description": "Modified", "status": "archived"}`
	req, _ = http.NewRequest(http.MethodPut, srv.URL+"/api/items/"+created.ID, strings.NewReader(modifyArchived))
	req.Header.Set("Content-Type", "application/json")
	resp, err = client.Do(req)
	if err != nil {
		t.Fatalf("PUT failed: %v", err)
	}
	assertErrorResponse(t, resp, http.StatusBadRequest, "validation_error")
	_ = resp.Body.Close()
}

func TestAdversarial_RouteEdgeCasesAndNonExistentIDs(t *testing.T) {
	srv, _ := setupTestServer()
	defer srv.Close()

	client := srv.Client()

	// 1. Non-existent ID -> 404 not_found
	nonExistent := "non-existent-id-00000000"
	resp, err := client.Get(srv.URL + "/api/items/" + nonExistent)
	if err != nil {
		t.Fatalf("GET failed: %v", err)
	}
	assertErrorResponse(t, resp, http.StatusNotFound, "not_found")
	_ = resp.Body.Close()

	// PUT to non-existent ID -> 404 not_found
	putPayload := `{"name": "Updated", "description": "", "status": "active"}`
	req, _ := http.NewRequest(http.MethodPut, srv.URL+"/api/items/"+nonExistent, strings.NewReader(putPayload))
	req.Header.Set("Content-Type", "application/json")
	resp, err = client.Do(req)
	if err != nil {
		t.Fatalf("PUT failed: %v", err)
	}
	assertErrorResponse(t, resp, http.StatusNotFound, "not_found")
	_ = resp.Body.Close()

	// DELETE to non-existent ID -> 404 not_found
	delReq, _ := http.NewRequest(http.MethodDelete, srv.URL+"/api/items/"+nonExistent, nil)
	resp, err = client.Do(delReq)
	if err != nil {
		t.Fatalf("DELETE failed: %v", err)
	}
	assertErrorResponse(t, resp, http.StatusNotFound, "not_found")
	_ = resp.Body.Close()

	// 2. ID longer than 64 characters (domain limit)
	longID := strings.Repeat("x", 100)
	resp, err = client.Get(srv.URL + "/api/items/" + longID)
	if err != nil {
		t.Fatalf("GET failed: %v", err)
	}
	if resp.StatusCode != http.StatusBadRequest && resp.StatusCode != http.StatusNotFound {
		t.Errorf("long ID status = %d, want 400 or 404", resp.StatusCode)
	}
	_ = resp.Body.Close()

	// 3. Whitespace ID (escaped)
	resp, err = client.Get(srv.URL + "/api/items/%20%20")
	if err != nil {
		t.Fatalf("GET failed: %v", err)
	}
	assertErrorResponse(t, resp, http.StatusBadRequest, "validation_error")
	_ = resp.Body.Close()
}

func TestAdversarial_DualFormatHealth(t *testing.T) {
	srv, _ := setupTestServer()
	defer srv.Close()

	client := srv.Client()

	// 1. GET /api/health returns JSON
	respJSON, err := client.Get(srv.URL + "/api/health")
	if err != nil {
		t.Fatalf("GET /api/health failed: %v", err)
	}
	defer func() { _ = respJSON.Body.Close() }()

	if respJSON.StatusCode != http.StatusOK {
		t.Errorf("GET /api/health status = %d, want 200", respJSON.StatusCode)
	}
	if !strings.HasPrefix(respJSON.Header.Get("Content-Type"), "application/json") {
		t.Errorf("expected Content-Type application/json, got %q", respJSON.Header.Get("Content-Type"))
	}

	var healthResp httpserver.HealthResponse
	if err := json.NewDecoder(respJSON.Body).Decode(&healthResp); err != nil {
		t.Fatalf("failed to decode health JSON: %v", err)
	}
	if !healthResp.OK || healthResp.Status != "ok" || healthResp.Version != "1.0.0" {
		t.Errorf("unexpected health JSON: %+v", healthResp)
	}

	// 2. GET /api/health/fragment returns HTML fragment
	respHTML, err := client.Get(srv.URL + "/api/health/fragment")
	if err != nil {
		t.Fatalf("GET /api/health/fragment failed: %v", err)
	}
	defer func() { _ = respHTML.Body.Close() }()

	if respHTML.StatusCode != http.StatusOK {
		t.Errorf("GET /api/health/fragment status = %d, want 200", respHTML.StatusCode)
	}
	if !strings.HasPrefix(respHTML.Header.Get("Content-Type"), "text/html") {
		t.Errorf("expected Content-Type text/html, got %q", respHTML.Header.Get("Content-Type"))
	}

	htmlBytes, _ := io.ReadAll(respHTML.Body)
	if len(htmlBytes) == 0 {
		t.Errorf("health fragment returned empty body")
	}

	// 3. Health with query params and special characters (injection attempt)
	respParam, err := client.Get(srv.URL + "/api/health?probe=<script>alert(1)</script>&num=123")
	if err != nil {
		t.Fatalf("GET /api/health with params failed: %v", err)
	}
	defer func() { _ = respParam.Body.Close() }()
	if respParam.StatusCode != http.StatusOK {
		t.Errorf("GET /api/health with params status = %d, want 200", respParam.StatusCode)
	}
}

type panicMockItemService struct{}

func (p *panicMockItemService) Create(_ context.Context, _, _ string, _ domain.ItemStatus) (domain.Item, error) {
	panic("adversarial simulated crash in Create")
}

func (p *panicMockItemService) GetByID(_ context.Context, _ string) (domain.Item, error) {
	panic("adversarial simulated crash in GetByID")
}

func (p *panicMockItemService) List(_ context.Context) ([]domain.Item, error) {
	panic("adversarial simulated crash in List")
}

func (p *panicMockItemService) Update(_ context.Context, _, _, _ string, _ domain.ItemStatus) (domain.Item, error) {
	panic("adversarial simulated crash in Update")
}

func (p *panicMockItemService) Delete(_ context.Context, _ string) error {
	panic("adversarial simulated crash in Delete")
}

func TestAdversarial_PanicRecoveryNoLeak(t *testing.T) {
	logger := slog.New(slog.NewJSONHandler(io.Discard, nil))
	healthSvc := health.NewService()
	panicSvc := &panicMockItemService{}

	router := httpserver.NewRouter(logger, healthSvc, panicSvc)
	srv := httptest.NewServer(router)
	defer srv.Close()

	client := srv.Client()

	tests := []struct {
		method  string
		urlPath string
		body    string
	}{
		{method: http.MethodGet, urlPath: "/api/items", body: ""},
		{method: http.MethodGet, urlPath: "/api/items/some-id", body: ""},
		{method: http.MethodPost, urlPath: "/api/items", body: `{"name":"test"}`},
		{method: http.MethodPut, urlPath: "/api/items/some-id", body: `{"name":"test"}`},
		{method: http.MethodDelete, urlPath: "/api/items/some-id", body: ""},
	}

	for _, tc := range tests {
		t.Run(fmt.Sprintf("%s %s panic recovery", tc.method, tc.urlPath), func(t *testing.T) {
			var bodyReader io.Reader
			if tc.body != "" {
				bodyReader = strings.NewReader(tc.body)
			}
			req, err := http.NewRequest(tc.method, srv.URL+tc.urlPath, bodyReader)
			if err != nil {
				t.Fatalf("failed to create request: %v", err)
			}
			if tc.body != "" {
				req.Header.Set("Content-Type", "application/json")
			}

			resp, err := client.Do(req)
			if err != nil {
				t.Fatalf("request failed (server may have crashed instead of recovering): %v", err)
			}
			defer func() { _ = resp.Body.Close() }()

			errResp := assertErrorResponse(t, resp, http.StatusInternalServerError, "internal_server_error")
			if errResp.Message != "an unexpected error occurred" {
				t.Errorf("message = %q, want 'an unexpected error occurred'", errResp.Message)
			}
		})
	}
}

func TestAdversarial_ConcurrentStress(t *testing.T) {
	srv, _ := setupTestServer()
	defer srv.Close()

	client := srv.Client()

	// Seed item to target
	targetID := "seed-item-1"

	const concurrency = 50
	errCh := make(chan error, concurrency*2)

	// Concurrently attempt to read and update the item
	for i := 0; i < concurrency; i++ {
		go func(idx int) {
			// Read
			resp, err := client.Get(srv.URL + "/api/items/" + targetID)
			if err != nil {
				errCh <- fmt.Errorf("read failed: %w", err)
				return
			}
			_ = resp.Body.Close()
			if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNotFound {
				errCh <- fmt.Errorf("unexpected read status: %d", resp.StatusCode)
				return
			}

			// Update
			body := fmt.Sprintf(`{"name":"Concurrent %d","description":"Stress","status":"active"}`, idx)
			req, err := http.NewRequest(http.MethodPut, srv.URL+"/api/items/"+targetID, strings.NewReader(body))
			if err != nil {
				errCh <- fmt.Errorf("new put request failed: %w", err)
				return
			}
			req.Header.Set("Content-Type", "application/json")
			putResp, err := client.Do(req)
			if err != nil {
				errCh <- fmt.Errorf("put failed: %w", err)
				return
			}
			_ = putResp.Body.Close()
			if putResp.StatusCode != http.StatusOK && putResp.StatusCode != http.StatusNotFound {
				errCh <- fmt.Errorf("unexpected put status: %d", putResp.StatusCode)
				return
			}

			errCh <- nil
		}(i)
	}

	for i := 0; i < concurrency; i++ {
		if err := <-errCh; err != nil {
			t.Errorf("concurrency error: %v", err)
		}
	}
}

func TestAdversarial_InvalidUTF8AndDeepNesting(t *testing.T) {
	srv, _ := setupTestServer()
	defer srv.Close()

	client := srv.Client()

	// 1a. Invalid JSON token byte (not valid JSON syntax)
	invalidSyntaxBytes := []byte{'{', 0xFF, '}'}
	reqSyntax, _ := http.NewRequest(http.MethodPost, srv.URL+"/api/items", bytes.NewReader(invalidSyntaxBytes))
	reqSyntax.Header.Set("Content-Type", "application/json")
	respSyntax, err := client.Do(reqSyntax)
	if err != nil {
		t.Fatalf("request with invalid syntax bytes failed: %v", err)
	}
	defer func() { _ = respSyntax.Body.Close() }()
	assertErrorResponse(t, respSyntax, http.StatusBadRequest, "validation_error")

	// 1b. Non-UTF8 byte inside JSON string value: Go stdlib json replaces with \uFFFD and accepts without panic
	invalidUTF8String := []byte{'{', '"', 'n', 'a', 'm', 'e', '"', ':', ' ', '"', 0xFF, 0xFE, 0xFD, '"', '}'}
	reqStr, _ := http.NewRequest(http.MethodPost, srv.URL+"/api/items", bytes.NewReader(invalidUTF8String))
	reqStr.Header.Set("Content-Type", "application/json")
	respStr, err := client.Do(reqStr)
	if err != nil {
		t.Fatalf("request with non-UTF8 in string failed: %v", err)
	}
	defer func() { _ = respStr.Body.Close() }()
	if respStr.StatusCode != http.StatusCreated && respStr.StatusCode != http.StatusBadRequest {
		t.Errorf("expected 201 or 400, got %d", respStr.StatusCode)
	}

	// 2. Deeply nested JSON object
	var b strings.Builder
	for i := 0; i < 150; i++ {
		b.WriteString(`{"a":`)
	}
	b.WriteString(`"bottom"`)
	for i := 0; i < 150; i++ {
		b.WriteString(`}`)
	}
	reqDeep, _ := http.NewRequest(http.MethodPost, srv.URL+"/api/items", strings.NewReader(b.String()))
	reqDeep.Header.Set("Content-Type", "application/json")
	respDeep, err := client.Do(reqDeep)
	if err != nil {
		t.Fatalf("request with deeply nested JSON failed: %v", err)
	}
	defer func() { _ = respDeep.Body.Close() }()
	assertErrorResponse(t, respDeep, http.StatusBadRequest, "validation_error")

	// 3. Huge whitespace prefix before valid JSON (50KB of spaces)
	whitespacePrefix := strings.Repeat(" ", 50*1024) + `{"name":"Whitespace Prefix","status":"pending"}`
	reqWS, _ := http.NewRequest(http.MethodPost, srv.URL+"/api/items", strings.NewReader(whitespacePrefix))
	reqWS.Header.Set("Content-Type", "application/json")
	respWS, err := client.Do(reqWS)
	if err != nil {
		t.Fatalf("request with whitespace prefix failed: %v", err)
	}
	defer func() { _ = respWS.Body.Close() }()
	if respWS.StatusCode != http.StatusCreated {
		t.Errorf("expected 201 Created for valid JSON with whitespace padding, got %d", respWS.StatusCode)
	}
}

func TestAdversarial_PathTraversalAndSpecialChars(t *testing.T) {
	srv, _ := setupTestServer()
	defer srv.Close()

	client := srv.Client()

	cases := []struct {
		path string
	}{
		{path: "/api/items/..%2F..%2Fcmd"},
		{path: "/api/items/%00"},
		{path: "/api/items/%2F%2F"},
		{path: "/api/items/test%0Anewline"},
		{path: "/api/items/\U00020000\U00020000\U00020000"},
	}

	for _, tc := range cases {
		t.Run(tc.path, func(t *testing.T) {
			resp, err := client.Get(srv.URL + tc.path)
			if err != nil {
				t.Fatalf("GET %s failed: %v", tc.path, err)
			}
			defer func() { _ = resp.Body.Close() }()

			// Path traversal / special characters must return 400 or 404 cleanly, never 500 or panic
			if resp.StatusCode != http.StatusBadRequest && resp.StatusCode != http.StatusNotFound {
				t.Errorf("GET %s status = %d, want 400 or 404", tc.path, resp.StatusCode)
			}

			// If JSON error returned, verify structure
			if strings.HasPrefix(resp.Header.Get("Content-Type"), "application/json") {
				var errResp httpserver.ErrorResponse
				if err := json.NewDecoder(resp.Body).Decode(&errResp); err != nil {
					t.Errorf("failed to decode ErrorResponse on %s: %v", tc.path, err)
				}
			}
		})
	}
}

