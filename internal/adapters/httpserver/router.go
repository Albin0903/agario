package httpserver

import (
	"log/slog"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/albin/build/internal/core/health"
)

// NewRouter creates and configures the HTTP router with all API, SSR, and SPA routes.
// Dependencies are passed explicitly via constructor arguments to preserve decoupling.
func NewRouter(logger *slog.Logger, healthSvc *health.Service, itemSvc ItemService) http.Handler {
	mux := http.NewServeMux()

	healthHandler := NewHealthHandler(healthSvc, logger)
	pageHandler := NewPageHandler(healthSvc, logger)
	itemHandler := NewItemHandler(itemSvc, logger)

	// API Health Routes
	mux.HandleFunc("GET /api/health", healthHandler.HandleHealth)
	mux.HandleFunc("GET /api/health/fragment", pageHandler.HandleHealthFragment)

	// API Items CRUD Routes (Go 1.22+ method + path patterns)
	mux.HandleFunc("GET /api/items", itemHandler.HandleList)
	mux.HandleFunc("GET /api/items/{id}", itemHandler.HandleGetByID)
	mux.HandleFunc("POST /api/items", itemHandler.HandleCreate)
	mux.HandleFunc("PUT /api/items/{id}", itemHandler.HandleUpdate)
	mux.HandleFunc("DELETE /api/items/{id}", itemHandler.HandleDelete)

	// Page routes (Templ SSR)
	mux.HandleFunc("GET /{$}", pageHandler.HandleIndex)

	// Single Page Application (SPA) Static Files & Client-Side Route Fallback
	distDir := os.Getenv("STATIC_DIR")
	if distDir == "" {
		distDir = "web-app/dist"
	}

	spaHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// URLs strictly use forward slashes across all platforms
		cleanPath := strings.TrimPrefix(r.URL.Path, "/app")
		cleanPath = strings.TrimPrefix(cleanPath, "/")

		if cleanPath == "" {
			cleanPath = "index.html"
		}

		target := filepath.Join(distDir, filepath.FromSlash(cleanPath))
		info, err := os.Stat(target)
		if err == nil && !info.IsDir() {
			http.ServeFile(w, r, target)
			return
		}

		// Fallback to index.html for TanStack Router client-side routes
		indexFile := filepath.Join(distDir, "index.html")
		if _, err := os.Stat(indexFile); err == nil {
			http.ServeFile(w, r, indexFile)
			return
		}

		http.NotFound(w, r)
	})

	mux.Handle("GET /app/", spaHandler)
	mux.Handle("GET /static/", http.StripPrefix("/static/", http.FileServer(http.Dir(distDir))))

	// Support native Vite bundles emitted into dist/assets/
	assetsDir := filepath.Join(distDir, "assets")
	mux.Handle("GET /assets/", http.StripPrefix("/assets/", http.FileServer(http.Dir(assetsDir))))

	// Layered middleware stack: Request logging -> Panic recovery
	var handler http.Handler = mux
	handler = recoveryMiddleware(logger, handler)
	handler = requestLoggerMiddleware(logger, handler)

	return handler
}
