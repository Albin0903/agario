//go:build integration

package integration_test

import (
	"bytes"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/albin/build/internal/adapters/httpserver"
	"github.com/albin/build/internal/adapters/storage/memory"
	"github.com/albin/build/internal/core/health"
	"github.com/albin/build/internal/core/items"
)

func setupTestServer() (*httptest.Server, *memory.Repository) {
	logger := slog.New(slog.NewJSONHandler(io.Discard, nil))
	repo := memory.NewWithSeed(memory.DefaultSeedItems()...)
	itemSvc := items.NewService(repo)
	healthSvc := health.NewService()
	router := httpserver.NewRouter(logger, healthSvc, itemSvc)

	return httptest.NewServer(router), repo
}

func TestHealthEndpoint_Integration(t *testing.T) {
	srv, _ := setupTestServer()
	defer srv.Close()

	resp, err := http.Get(srv.URL + "/api/health")
	if err != nil {
		t.Fatalf("request failed: %v", err)
	}
	defer func() {
		_ = resp.Body.Close()
	}()

	if resp.StatusCode != http.StatusOK {
		t.Errorf("status = %d, want %d", resp.StatusCode, http.StatusOK)
	}

	var status httpserver.HealthResponse
	if err := json.NewDecoder(resp.Body).Decode(&status); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if !status.OK {
		t.Error("health status.OK should be true")
	}
	if status.Status != "ok" {
		t.Errorf("health status.Status = %q, want 'ok'", status.Status)
	}
	if status.Version != "1.0.0" {
		t.Errorf("health status.Version = %q, want '1.0.0'", status.Version)
	}
}

func TestItemsCRUD_Integration(t *testing.T) {
	srv, _ := setupTestServer()
	defer srv.Close()

	client := srv.Client()

	// 1. Verify initial seed items exist
	resp, err := client.Get(srv.URL + "/api/items")
	if err != nil {
		t.Fatalf("GET /api/items failed: %v", err)
	}
	defer func() {
		_ = resp.Body.Close()
	}()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("GET /api/items status = %d, want 200", resp.StatusCode)
	}

	var initialItems []httpserver.ItemResponse
	if err := json.NewDecoder(resp.Body).Decode(&initialItems); err != nil {
		t.Fatalf("failed to decode initial items: %v", err)
	}
	if len(initialItems) != 5 {
		t.Errorf("expected 5 default seed items, got %d", len(initialItems))
	}

	// 2. Create a new item
	createPayload := []byte(`{"name":"Integration Test Item","description":"Created during integration test","status":"active"}`)
	postResp, err := client.Post(srv.URL+"/api/items", "application/json", bytes.NewReader(createPayload))
	if err != nil {
		t.Fatalf("POST /api/items failed: %v", err)
	}
	defer func() {
		_ = postResp.Body.Close()
	}()

	if postResp.StatusCode != http.StatusCreated {
		t.Fatalf("POST /api/items status = %d, want 201", postResp.StatusCode)
	}

	var created httpserver.ItemResponse
	if err := json.NewDecoder(postResp.Body).Decode(&created); err != nil {
		t.Fatalf("failed to decode created item: %v", err)
	}
	if created.ID == "" || created.Name != "Integration Test Item" {
		t.Errorf("unexpected created item: %+v", created)
	}

	// 3. Fetch created item by ID
	getResp, err := client.Get(srv.URL + "/api/items/" + created.ID)
	if err != nil {
		t.Fatalf("GET /api/items/{id} failed: %v", err)
	}
	defer func() {
		_ = getResp.Body.Close()
	}()

	if getResp.StatusCode != http.StatusOK {
		t.Fatalf("GET /api/items/{id} status = %d, want 200", getResp.StatusCode)
	}

	var fetched httpserver.ItemResponse
	if err := json.NewDecoder(getResp.Body).Decode(&fetched); err != nil {
		t.Fatalf("failed to decode fetched item: %v", err)
	}
	if fetched.ID != created.ID || fetched.Name != created.Name {
		t.Errorf("fetched item mismatch: got %+v, want %+v", fetched, created)
	}

	// 4. Update the item
	updatePayload := []byte(`{"name":"Updated Integration Item","description":"Updated description","status":"completed"}`)
	req, err := http.NewRequest(http.MethodPut, srv.URL+"/api/items/"+created.ID, bytes.NewReader(updatePayload))
	if err != nil {
		t.Fatalf("failed to build PUT request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	putResp, err := client.Do(req)
	if err != nil {
		t.Fatalf("PUT /api/items/{id} failed: %v", err)
	}
	defer func() {
		_ = putResp.Body.Close()
	}()

	if putResp.StatusCode != http.StatusOK {
		t.Fatalf("PUT /api/items/{id} status = %d, want 200", putResp.StatusCode)
	}

	var updated httpserver.ItemResponse
	if err := json.NewDecoder(putResp.Body).Decode(&updated); err != nil {
		t.Fatalf("failed to decode updated item: %v", err)
	}
	if updated.Name != "Updated Integration Item" || updated.Status != "completed" {
		t.Errorf("updated item mismatch: got %+v", updated)
	}

	// 5. Delete the item
	delReq, err := http.NewRequest(http.MethodDelete, srv.URL+"/api/items/"+created.ID, nil)
	if err != nil {
		t.Fatalf("failed to build DELETE request: %v", err)
	}
	delResp, err := client.Do(delReq)
	if err != nil {
		t.Fatalf("DELETE /api/items/{id} failed: %v", err)
	}
	defer func() {
		_ = delResp.Body.Close()
	}()

	if delResp.StatusCode != http.StatusOK {
		t.Fatalf("DELETE /api/items/{id} status = %d, want 200", delResp.StatusCode)
	}

	// 6. Verify item is deleted (returns 404)
	missingResp, err := client.Get(srv.URL + "/api/items/" + created.ID)
	if err != nil {
		t.Fatalf("GET /api/items/{id} after delete failed: %v", err)
	}
	defer func() {
		_ = missingResp.Body.Close()
	}()

	if missingResp.StatusCode != http.StatusNotFound {
		t.Errorf("GET /api/items/{id} after delete status = %d, want 404", missingResp.StatusCode)
	}
}
