"""Unit tests for DesignHandler mathematical contrast and palette generation."""

from worker_python.handlers.design import DesignHandler


def test_calculate_contrast_black_on_white() -> None:
    """Verify maximum contrast between pure black text on pure white surface."""
    result = DesignHandler.calculate_contrast("#000000", "#ffffff")
    assert result["wcag_ratio"] == 21.0
    assert result["wcag_aa_normal_text"] is True
    assert result["wcag_aaa_normal_text"] is True
    assert result["apca_estimate_lc"] >= 100.0
    assert result["apca_body_text_pass"] is True


def test_calculate_contrast_low_contrast_fails_aa() -> None:
    """Verify that light grey on white fails normal text AA compliance."""
    result = DesignHandler.calculate_contrast("#94a3b8", "#ffffff")
    assert result["wcag_ratio"] < 4.5
    assert result["wcag_aa_normal_text"] is False


def test_generate_palette_scale_contains_12_steps() -> None:
    """Verify generation of exactly 12 functional levels conforming to Radix conventions."""
    scale = DesignHandler.generate_palette_scale("#4f46e5")
    assert len(scale) == 12
    for step in range(1, 13):
        assert f"step_{step}" in scale
        assert scale[f"step_{step}"].startswith("#")


def test_generate_favicon_svg() -> None:
    """Verify clean SVG generation with dimensions and letter glyph."""
    svg = DesignHandler.generate_favicon_svg("B", "#4f46e5", "#ffffff")
    assert "<svg" in svg
    assert 'viewBox="0 0 64 64"' in svg
    assert "B" in svg
    assert "</text>" in svg
    assert 'fill="#4f46e5"' in svg


def test_audit_token_contrast_passes_on_satin_theme() -> None:
    """Verify token audit against standard satin light theme tokens."""
    tokens = {
        "surface_canvas": "#f8fafc",
        "surface_card": "#ffffff",
        "text_primary": "#0f172a",
        "text_secondary": "#475569",
        "brand_primary": "#4f46e5",
    }
    audit = DesignHandler.audit_token_contrast(tokens)
    assert audit["passed"] is True
    assert audit["audits"]["text_primary_on_canvas"]["wcag_aa_normal_text"] is True
    assert audit["audits"]["text_primary_on_card"]["wcag_aa_normal_text"] is True
