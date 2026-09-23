// Package httpserver provides HTTP handlers, middleware, and routing for the application.
package httpserver

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"

	"github.com/albin/build/internal/core/domain"
)

// ErrorResponse defines the canonical JSON error payload returned across all API endpoints.
type ErrorResponse struct {
	Error   string `json:"error"`
	Message string `json:"message"`
}

// respondJSON buffers the JSON payload before committing HTTP headers to ensure atomic
// status delivery and prevent superfluous header warnings if serialization fails.
func respondJSON[T any](w http.ResponseWriter, status int, payload T) error {
	var buf bytes.Buffer
	if err := json.NewEncoder(&buf).Encode(payload); err != nil {
		return fmt.Errorf("encoding json response: %w", err)
	}

	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if _, err := w.Write(buf.Bytes()); err != nil {
		return fmt.Errorf("writing json response: %w", err)
	}
	return nil
}

// writeErrorResponse buffers and writes a canonical JSON error payload without premature header commits.
func writeErrorResponse(ctx context.Context, w http.ResponseWriter, logger *slog.Logger, statusCode int, resp ErrorResponse) {
	var buf bytes.Buffer
	if err := json.NewEncoder(&buf).Encode(resp); err != nil {
		if logger != nil {
			logger.ErrorContext(ctx, "failed to encode error response",
				"error", err,
			)
		}
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		w.WriteHeader(http.StatusInternalServerError)
		if _, writeErr := w.Write([]byte("internal server error\n")); writeErr != nil {
			if logger != nil {
				logger.WarnContext(ctx, "failed to write fallback error response", "error", writeErr)
			}
		}
		return
	}

	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(statusCode)
	if _, err := w.Write(buf.Bytes()); err != nil {
		if logger != nil {
			logger.WarnContext(ctx, "failed to write error response body",
				"error", err,
			)
		}
	}
}

// respondError translates domain sentinels and system errors to standard HTTP status codes
// and unified JSON responses, while logging internal errors with diagnostic context.
func respondError(w http.ResponseWriter, r *http.Request, logger *slog.Logger, err error) {
	if err == nil {
		return
	}

	ctx := r.Context()
	var statusCode int
	var errCode string
	var message string

	var maxBytesErr *http.MaxBytesError

	switch {
	case errors.As(err, &maxBytesErr):
		statusCode = http.StatusRequestEntityTooLarge
		errCode = "payload_too_large"
		message = "request body exceeds maximum allowed size"
		if logger != nil {
			logger.WarnContext(ctx, "payload exceeds max bytes", "path", r.URL.Path, "limit", maxBytesErr.Limit)
		}

	case errors.Is(err, domain.ErrNotFound):
		statusCode = http.StatusNotFound
		errCode = "not_found"
		message = err.Error()

	case errors.Is(err, domain.ErrValidation):
		statusCode = http.StatusBadRequest
		errCode = "validation_error"
		message = err.Error()

	case errors.Is(err, domain.ErrConflict):
		statusCode = http.StatusConflict
		errCode = "conflict"
		message = err.Error()

	case errors.Is(err, domain.ErrUnauthorized):
		statusCode = http.StatusUnauthorized
		errCode = "unauthorized"
		message = "unauthorized access"

	case errors.Is(err, domain.ErrForbidden):
		statusCode = http.StatusForbidden
		errCode = "forbidden"
		message = "forbidden operation"

	case errors.Is(err, context.Canceled):
		// 499 indicates client disconnected before completion.
		statusCode = 499
		errCode = "client_closed"
		message = "client closed request"
		if logger != nil {
			logger.WarnContext(ctx, "client canceled request", "path", r.URL.Path, "method", r.Method)
		}

	case errors.Is(err, context.DeadlineExceeded):
		statusCode = http.StatusGatewayTimeout
		errCode = "gateway_timeout"
		message = "request processing timed out"
		if logger != nil {
			logger.WarnContext(ctx, "request deadline exceeded", "path", r.URL.Path, "method", r.Method)
		}

	case errors.Is(err, io.EOF), errors.Is(err, io.ErrUnexpectedEOF):
		statusCode = http.StatusBadRequest
		errCode = "validation_error"
		message = "request body must not be empty"

	default:
		// Shield internal system errors to prevent information disclosure (CWE-209).
		statusCode = http.StatusInternalServerError
		errCode = "internal_server_error"
		message = "an unexpected error occurred"

		if logger != nil {
			logger.ErrorContext(ctx, "internal server error",
				"error", err,
				"path", r.URL.Path,
				"method", r.Method,
			)
		}
	}

	resp := ErrorResponse{
		Error:   errCode,
		Message: message,
	}

	writeErrorResponse(ctx, w, logger, statusCode, resp)
}
