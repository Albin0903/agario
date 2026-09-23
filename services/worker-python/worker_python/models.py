from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskRequest(BaseModel):
    """Generic task request dispatched to the Python worker engine."""

    model_config = ConfigDict(frozen=True)

    action: str = Field(..., min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    task_id: str = Field(default="", max_length=64)


class TaskResponse(BaseModel):
    """Structured response returned by a task processor."""

    model_config = ConfigDict(frozen=True)

    success: bool
    action: str
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_ms: float = Field(default=0.0, ge=0.0)
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ColorSpec(BaseModel):
    """Color representation supporting hex, RGB, and perceptual luminance calculations."""

    model_config = ConfigDict(frozen=True)

    r: int = Field(..., ge=0, le=255)
    g: int = Field(..., ge=0, le=255)
    b: int = Field(..., ge=0, le=255)

    @classmethod
    def from_hex(cls, hex_code: str) -> "ColorSpec":
        """Parse 3 or 6 digit hex code into ColorSpec."""
        clean = hex_code.strip().lstrip("#")
        if len(clean) == 3:
            clean = "".join(c * 2 for c in clean)
        if len(clean) != 6:
            raise ValueError(f"Invalid hex color: {hex_code}")
        try:
            r = int(clean[0:2], 16)
            g = int(clean[2:4], 16)
            b = int(clean[4:6], 16)
        except ValueError as err:
            raise ValueError(f"Invalid hex color: {hex_code}") from err
        return cls(r=r, g=g, b=b)

    def to_hex(self) -> str:
        """Convert ColorSpec to lowercase 6-digit hex string."""
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

    def relative_luminance(self) -> float:
        """Calculate relative luminance according to sRGB / WCAG specification."""

        def channel_lum(channel: int) -> float:
            c = channel / 255.0
            if c <= 0.04045:
                return float(c / 12.92)
            return float(((c + 0.055) / 1.055) ** 2.4)

        lum_r = 0.2126 * channel_lum(self.r)
        lum_g = 0.7152 * channel_lum(self.g)
        lum_b = 0.0722 * channel_lum(self.b)
        return lum_r + lum_g + lum_b


class DatasetSummary(BaseModel):
    """Statistical summary of a numeric dataset."""

    model_config = ConfigDict(frozen=True)

    count: int = Field(..., ge=0)
    mean: float
    std_dev: float = Field(..., ge=0.0)
    min_value: float
    max_value: float
    median: float
