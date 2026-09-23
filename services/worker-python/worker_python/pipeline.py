"""Task dispatching pipeline registering and executing domain handlers."""

import time
from collections.abc import Callable
from typing import Any

from worker_python.handlers.data import DataHandler
from worker_python.handlers.design import DesignHandler
from worker_python.handlers.seed import SeedHandler
from worker_python.models import TaskRequest, TaskResponse

HandlerFunc = Callable[[dict[str, Any]], dict[str, Any]]


class TaskPipeline:
    """Central registry and execution pipeline for all Python worker tasks."""

    def __init__(self) -> None:
        self._handlers: dict[str, HandlerFunc] = {}
        self._register_default_handlers()

    def register(self, action: str, handler: HandlerFunc) -> None:
        """Register a new action handler in the pipeline."""
        if not action.strip():
            raise ValueError("Action name cannot be empty")
        self._handlers[action.strip()] = handler

    def execute(self, request: TaskRequest) -> TaskResponse:
        """Execute a TaskRequest against the registered action handler with timing."""
        start_time = time.perf_counter()
        action = request.action.strip()

        if action not in self._handlers:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return TaskResponse(
                success=False,
                action=action,
                data={},
                error=f"Unrecognized action '{action}'. Available: {list(self._handlers.keys())}",
                duration_ms=round(elapsed, 2),
            )

        try:
            handler = self._handlers[action]
            result_data = handler(request.payload)
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return TaskResponse(
                success=True,
                action=action,
                data=result_data,
                error=None,
                duration_ms=round(elapsed, 2),
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return TaskResponse(
                success=False,
                action=action,
                data={},
                error=f"Handler execution failed: {exc}",
                duration_ms=round(elapsed, 2),
            )

    def _register_default_handlers(self) -> None:
        """Register core design and data transformation handlers."""

        def design_contrast(payload: dict[str, Any]) -> dict[str, Any]:
            fg = str(payload.get("foreground", "#0f172a"))
            bg = str(payload.get("background", "#ffffff"))
            return DesignHandler.calculate_contrast(fg, bg)

        def design_palette(payload: dict[str, Any]) -> dict[str, Any]:
            base = str(payload.get("base", "#4f46e5"))
            scale = DesignHandler.generate_palette_scale(base)
            return {"base": base, "scale": scale}

        def data_summarize(payload: dict[str, Any]) -> dict[str, Any]:
            raw_vals = payload.get("values", [])
            values = [float(x) for x in raw_vals]
            summary = DataHandler.summarize(values)
            return summary.model_dump()

        def data_normalize(payload: dict[str, Any]) -> dict[str, Any]:
            raw_vals = payload.get("values", [])
            values = [float(x) for x in raw_vals]
            normalized = DataHandler.normalize_minmax(values)
            return {"normalized": normalized}

        def design_favicon(payload: dict[str, Any]) -> dict[str, Any]:
            letter = str(payload.get("letter", "A"))
            bg = str(payload.get("background", "#4f46e5"))
            fg = str(payload.get("foreground", "#ffffff"))
            svg = DesignHandler.generate_favicon_svg(letter, bg, fg)
            return {"svg": svg}

        def design_audit(payload: dict[str, Any]) -> dict[str, Any]:
            tokens = {str(k): str(v) for k, v in payload.get("tokens", {}).items()}
            return DesignHandler.audit_token_contrast(tokens)

        def seed_items(payload: dict[str, Any]) -> dict[str, Any]:
            domain = str(payload.get("domain", "saas"))
            count = int(payload.get("count", 5))
            items = SeedHandler.generate_items(domain, count)
            return {"domain": domain, "items": items}

        def seed_users(payload: dict[str, Any]) -> dict[str, Any]:
            count = int(payload.get("count", 5))
            users = SeedHandler.generate_users(count)
            return {"users": users}

        self.register("design.contrast", design_contrast)
        self.register("design.palette", design_palette)
        self.register("design.favicon", design_favicon)
        self.register("design.audit", design_audit)
        self.register("data.summarize", data_summarize)
        self.register("data.normalize", data_normalize)
        self.register("seed.items", seed_items)
        self.register("seed.users", seed_users)
