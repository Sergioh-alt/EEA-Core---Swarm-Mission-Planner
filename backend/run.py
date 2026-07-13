"""
Phase 10C.4 — Digital Twin API server entrypoint.

Run:
    python -m backend.run
    # or
    uvicorn backend.twin_server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("TWIN_API_HOST", "0.0.0.0")
    port = int(os.environ.get("TWIN_API_PORT", "8000"))
    uvicorn.run("backend.twin_server:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
