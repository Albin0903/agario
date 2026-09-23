"""Design engineering handler computing contrast ratios and Radix functional palettes."""

from typing import Any

from worker_python.models import ColorSpec


class DesignHandler:
    """Handler executing design calculations, token evaluations, and palette generations."""

    @staticmethod
    def calculate_contrast(foreground_hex: str, background_hex: str) -> dict[str, Any]:
        """Compute WCAG 2.1 contrast ratio and APCA contrast magnitude estimate."""
        fg = ColorSpec.from_hex(foreground_hex)
        bg = ColorSpec.from_hex(background_hex)

        lum1 = fg.relative_luminance()
        lum2 = bg.relative_luminance()

        lighter = max(lum1, lum2)
        darker = min(lum1, lum2)
        wcag_ratio = (lighter + 0.05) / (darker + 0.05)

        # APCA-like perceptual lightness contrast approximation
        # Lc magnitude ranges from ~0 (invisible) to ~108 (pure black on pure white)
        y_txt = lum1 if lum1 <= lum2 else lum2
        y_bg = lum2 if lum1 <= lum2 else lum1
        apca_estimate = abs((y_bg**0.56 - y_txt**0.56) * 100.0)

        return {
            "foreground": fg.to_hex(),
            "background": bg.to_hex(),
            "wcag_ratio": round(wcag_ratio, 2),
            "wcag_aa_normal_text": wcag_ratio >= 4.5,
            "wcag_aa_large_text": wcag_ratio >= 3.0,
            "wcag_aaa_normal_text": wcag_ratio >= 7.0,
            "apca_estimate_lc": round(apca_estimate, 1),
            "apca_body_text_pass": apca_estimate >= 60.0,
        }

    @staticmethod
    def generate_palette_scale(base_hex: str) -> dict[str, str]:
        """Generate a 12-step functional color scale (Radix UI convention) around a base color."""
        base = ColorSpec.from_hex(base_hex)
        scale: dict[str, str] = {}

        # 12 levels: 1-2 app background/subtle, 3-5 UI element background,
        # 6-8 borders, 9 solid fill, 10 hover, 11-12 high-contrast text
        for step in range(1, 13):
            if step <= 2:
                # Tint towards pure white (90-95% white)
                r = int(base.r * 0.1 + 255 * 0.9)
                g = int(base.g * 0.1 + 255 * 0.9)
                b = int(base.b * 0.1 + 255 * 0.9)
            elif step <= 8:
                # Intermediate tints for component surfaces and borders
                mix = (step - 2) / 7.0
                r = int(base.r * mix + 245 * (1.0 - mix))
                g = int(base.g * mix + 245 * (1.0 - mix))
                b = int(base.b * mix + 245 * (1.0 - mix))
            elif step == 9:
                # The primary solid brand color
                r, g, b = base.r, base.g, base.b
            elif step == 10:
                # Hover state: slightly darker
                r = max(0, int(base.r * 0.88))
                g = max(0, int(base.g * 0.88))
                b = max(0, int(base.b * 0.88))
            else:
                # High contrast text (steps 11 and 12): deep shade
                dark_mix = 0.4 if step == 11 else 0.25
                r = max(0, int(base.r * dark_mix))
                g = max(0, int(base.g * dark_mix))
                b = max(0, int(base.b * dark_mix))

            scale[f"step_{step}"] = ColorSpec(r=r, g=g, b=b).to_hex()

        return scale

    @staticmethod
    def generate_favicon_svg(letter: str, bg_hex: str, text_hex: str = "#ffffff") -> str:
        """Generate a clean, minimal SVG favicon with a rounded rectangle and centered glyph."""
        clean_char = (letter.strip()[:1] or "A").upper()
        bg = ColorSpec.from_hex(bg_hex).to_hex()
        fg = ColorSpec.from_hex(text_hex).to_hex()

        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">\n'
            f'  <rect width="64" height="64" rx="16" fill="{bg}"/>\n'
            f'  <text x="32" y="44" font-family="system-ui, sans-serif" '
            f'font-size="34" font-weight="700" fill="{fg}" text-anchor="middle">\n'
            f"    {clean_char}\n"
            "  </text>\n"
            "</svg>"
        )

    @classmethod
    def audit_token_contrast(cls, tokens: dict[str, str]) -> dict[str, Any]:
        """Audit pairwise contrast for standard UI token combinations."""
        canvas = tokens.get("surface_canvas", "#f8fafc")
        card = tokens.get("surface_card", "#ffffff")
        text_primary = tokens.get("text_primary", "#0f172a")
        text_secondary = tokens.get("text_secondary", "#475569")
        brand = tokens.get("brand_primary", "#4f46e5")

        results = {
            "text_primary_on_canvas": cls.calculate_contrast(text_primary, canvas),
            "text_primary_on_card": cls.calculate_contrast(text_primary, card),
            "text_secondary_on_card": cls.calculate_contrast(text_secondary, card),
            "brand_on_canvas": cls.calculate_contrast(brand, canvas),
            "white_on_brand": cls.calculate_contrast("#ffffff", brand),
        }

        all_passed = all(
            r["wcag_aa_normal_text"]
            for k, r in results.items()
            if k not in ("brand_on_canvas", "text_secondary_on_card")
        )

        return {
            "passed": all_passed,
            "audits": results,
        }
