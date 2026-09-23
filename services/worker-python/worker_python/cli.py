"""CLI and IPC entrypoint executing task requests from Go or shell."""

import json
import sys

from worker_python.models import TaskRequest
from worker_python.pipeline import TaskPipeline


def run_cli() -> int:
    """Execute a task request received via CLI argument or stdin and write JSON response."""
    pipeline = TaskPipeline()

    raw_input: str = ""
    if len(sys.argv) > 1:
        raw_input = sys.argv[1]
    else:
        raw_input = sys.stdin.read()

    raw_input = raw_input.strip()
    if not raw_input:
        response_dict = {
            "success": False,
            "action": "unknown",
            "data": {},
            "error": "No JSON task request payload provided via argument or stdin",
            "duration_ms": 0.0,
        }
        sys.stdout.write(json.dumps(response_dict) + "\n")
        return 1

    try:
        parsed = json.loads(raw_input)
        request = TaskRequest.model_validate(parsed)
        response = pipeline.execute(request)
        sys.stdout.write(response.model_dump_json() + "\n")
        return 0 if response.success else 1
    except Exception as exc:  # noqa: BLE001
        response_dict = {
            "success": False,
            "action": "unknown",
            "data": {},
            "error": f"Failed to parse or validate request: {exc}",
            "duration_ms": 0.0,
        }
        sys.stdout.write(json.dumps(response_dict) + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(run_cli())
