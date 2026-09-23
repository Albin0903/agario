// Package main provides a project initialization script that replaces
// module and package names across the repository for new projects created from this template.
package main

import (
	"bytes"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"strings"
	"unicode"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintf(os.Stderr, "erreur initialisation: %v\n", err)
		os.Exit(1)
	}
}

func run() error {
	if len(os.Args) < 2 || strings.TrimSpace(os.Args[1]) == "" {
		return errors.New("nom de module requis. Usage: go run scripts/init.go <module-path-ou-slug>")
	}

	input := strings.TrimSpace(os.Args[1])
	var newModule string
	var appName string

	if strings.Contains(input, "/") {
		newModule = input
		appName = path.Base(newModule)
	} else {
		// Prise en charge d'un slug court (ex: task init -- power4)
		appName = input
		newModule = "github.com/Albin0903/" + input
	}

	if appName == "." || appName == "/" || appName == "" {
		appName = "app"
	}

	appTitle := formatAppTitle(appName)

	// 1. Extraction du nom de module actuel depuis go.mod
	goModData, err := os.ReadFile("go.mod")
	if err != nil {
		return fmt.Errorf("lecture go.mod: %w", err)
	}

	oldModule, err := extractModuleName(goModData)
	if err != nil {
		return fmt.Errorf("extraction module actuel: %w", err)
	}

	if oldModule == newModule {
		fmt.Printf("Le projet utilise deja le module '%s'. Aucune modification requise.\n", newModule)
		return nil
	}

	fmt.Printf("Initialisation du projet : passage de '%s' vers '%s' (application: %s)\n", oldModule, newModule, appTitle)

	// 2. Mise a jour du module Go dans go.mod
	cmd := exec.Command("go", "mod", "edit", "-module", newModule)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("go mod edit: %w", err)
	}
	fmt.Println("- go.mod mis a jour")

	// 3. Remplacement des imports dans tous les fichiers source Go et Templ
	var modifiedSourceFiles int
	err = filepath.WalkDir(".", func(p string, d fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if d.IsDir() {
			name := d.Name()
			if name == ".git" || name == "node_modules" || name == "tmp" || name == "dist" || name == ".devcontainer" {
				return filepath.SkipDir
			}
			return nil
		}

		if !strings.HasSuffix(d.Name(), ".go") && !strings.HasSuffix(d.Name(), ".templ") {
			return nil
		}

		content, readErr := os.ReadFile(p)
		if readErr != nil {
			return readErr
		}

		if bytes.Contains(content, []byte(oldModule)) {
			replaced := bytes.ReplaceAll(content, []byte(oldModule), []byte(newModule))
			if writeErr := os.WriteFile(p, replaced, 0o600); writeErr != nil {
				return writeErr
			}
			modifiedSourceFiles++
		}
		return nil
	})
	if err != nil {
		return fmt.Errorf("remplacement imports source: %w", err)
	}
	fmt.Printf("- %d fichiers sources (Go/Templ) mis a jour avec les nouveaux imports\n", modifiedSourceFiles)

	// 4. Remplacement de GO_MODULE dans Taskfile.yml
	if err := replaceInFile("Taskfile.yml", "GO_MODULE: "+oldModule, "GO_MODULE: "+newModule); err != nil {
		return fmt.Errorf("mise a jour Taskfile.yml: %w", err)
	}
	fmt.Println("- Taskfile.yml mis a jour (GO_MODULE)")

	// 5. Remplacement du package name dans web-app/package.json et index.html
	oldPkgName := path.Base(oldModule) + "-web-app"
	if oldPkgName == "build-web-app" || oldPkgName == "-web-app" {
		oldPkgName = "build-web-app"
	}
	newPkgName := appName + "-web-app"
	if err := replaceInFile("web-app/package.json", `"name": "`+oldPkgName+`"`, `"name": "`+newPkgName+`"`); err != nil {
		return fmt.Errorf("mise a jour web-app/package.json: %w", err)
	}
	fmt.Printf("- web-app/package.json mis a jour (%s)\n", newPkgName)

	if err := replaceInFile("web-app/index.html", "<title>Build — SPA</title>", "<title>"+appTitle+" — Console</title>"); err != nil {
		fmt.Printf("note: web-app/index.html titre non modifie: %v\n", err)
	}

	if err := replaceInFile("web-app/src/App.tsx", `>Console Applicative<`, `>`+appTitle+` Console<`); err != nil {
		fmt.Printf("note: web-app/src/App.tsx titre non modifie: %v\n", err)
	}

	// 6. Personnalisation du titre dans handlers.go et README.md
	if err := replaceInFile("internal/adapters/httpserver/handlers.go", `Title:       "Application"`, `Title:       "`+appTitle+`"`); err != nil {
		fmt.Printf("note: handlers.go titre non modifie: %v\n", err)
	}
	if err := replaceInFile("README.md", "# [TODO: Nom de votre application]", "# "+appTitle); err != nil {
		fmt.Printf("note: README.md titre non modifie: %v\n", err)
	}
	if err := replaceInFile("README.md", "> [TODO: Description concise en une phrase de la finalité de l'application.]", "> Application "+appTitle+"."); err != nil {
		fmt.Printf("note: README.md description non modifiee: %v\n", err)
	}
	fmt.Printf("- Titre applicatif configure: %s\n", appTitle)

	return nil
}

func formatAppTitle(slug string) string {
	parts := strings.FieldsFunc(slug, func(r rune) bool {
		return r == '-' || r == '_'
	})
	for i, p := range parts {
		if len(p) > 0 {
			runes := []rune(p)
			runes[0] = unicode.ToUpper(runes[0])
			parts[i] = string(runes)
		}
	}
	if len(parts) == 0 {
		return "Application"
	}
	return strings.Join(parts, " ")
}

func extractModuleName(data []byte) (string, error) {
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "module ") {
			fields := strings.Fields(trimmed)
			if len(fields) >= 2 {
				return fields[1], nil
			}
		}
	}
	return "", errors.New("directive 'module' introuvable dans go.mod")
}

func replaceInFile(filePath, target, replacement string) error {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return err
	}
	if !strings.Contains(string(data), target) {
		return nil
	}
	updated := strings.ReplaceAll(string(data), target, replacement)
	return os.WriteFile(filePath, []byte(updated), 0o600)
}
