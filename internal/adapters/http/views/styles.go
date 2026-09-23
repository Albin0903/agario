// Package views provides compiled Templ HTML templates, layout structures, and view components.
package views

import (
	"context"
	"io"

	"github.com/a-h/templ"
)

// CustomCSS injects arbitrary CSS rules, keyframes, or custom theme properties
// directly into the HTML stream via a <style> block.
//
// By rendering styles through templ.ComponentFunc rather than an inline <style> block
// inside a .templ file, it completely prevents `templ fmt` from invoking external
// Prettier binaries on Windows and Unix environments, guaranteeing hermetic formatting.
func CustomCSS(css string) templ.Component {
	return templ.ComponentFunc(func(_ context.Context, w io.Writer) error {
		if css == "" {
			return nil
		}
		_, err := io.WriteString(w, "<style>"+css+"</style>")
		return err
	})
}
