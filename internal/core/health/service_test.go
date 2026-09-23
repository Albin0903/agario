package health_test

import (
	"testing"

	"github.com/albin/build/internal/core/health"
)

func TestService_Check(t *testing.T) {
	t.Parallel()

	tests := map[string]struct {
		wantOK bool
	}{
		"returns healthy status": {
			wantOK: true,
		},
	}

	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			svc := health.NewService()
			status := svc.Check()

			if status.OK != tt.wantOK {
				t.Errorf("Check().OK = %v, want %v", status.OK, tt.wantOK)
			}

			if status.Timestamp.IsZero() {
				t.Error("Check().Timestamp should not be zero")
			}

			if status.Uptime == "" {
				t.Error("Check().Uptime should not be empty")
			}
		})
	}
}
