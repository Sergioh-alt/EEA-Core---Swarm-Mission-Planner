#!/usr/bin/env python3
"""
ORIÓN development/demonstration launcher.

Implements the documented startup protocol:

    Environment check -> Start Backend -> Backend health check
    -> Backend READY -> Start Next.js UI -> ORION READY

Deliberately minimal: it starts the two existing processes, waits on the
backend readiness endpoint, and forwards their output. It contains no
orchestration, supervision, or restart logic, and no application behavior.

Usage:
    python scripts/start_orion.py            # backend + Mission Control UI
    python scripts/start_orion.py backend    # backend only
    python scripts/start_orion.py frontend   # Mission Control UI only
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI_DIR = ROOT / "orion-ui"

BACKEND_HOST = os.environ.get("TWIN_API_HOST", "127.0.0.1")
BACKEND_PORT = os.environ.get("TWIN_API_PORT", "8000")
HEALTH_URL = f"http://{'127.0.0.1' if BACKEND_HOST == '0.0.0.0' else BACKEND_HOST}:{BACKEND_PORT}/health"
BACKEND_URL = f"http://localhost:{BACKEND_PORT}"
READY_TIMEOUT_S = 60.0


def check_environment(need_ui: bool) -> None:
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError as exc:
        sys.exit(f"Missing backend dependency ({exc}). Run: pip install -r requirements.txt")
    if need_ui:
        if shutil.which("npm") is None:
            sys.exit("npm not found on PATH — required to run the Mission Control UI.")
        if not (UI_DIR / "node_modules").is_dir():
            sys.exit(f"UI dependencies missing. Run: cd {UI_DIR} && npm install")


def start_backend() -> subprocess.Popen[bytes]:
    print(f"[orion] starting backend on {BACKEND_URL}")
    return subprocess.Popen([sys.executable, "-m", "backend.run"], cwd=ROOT)


def wait_for_backend(proc: subprocess.Popen[bytes] | None) -> None:
    deadline = time.monotonic() + READY_TIMEOUT_S
    while time.monotonic() < deadline:
        if proc is not None and proc.poll() is not None:
            sys.exit(f"[orion] backend exited early with code {proc.returncode}")
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=2) as resp:
                if resp.status == 200:
                    print(f"[orion] backend READY ({HEALTH_URL})")
                    return
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)
    sys.exit(f"[orion] backend did not become ready within {READY_TIMEOUT_S:.0f}s")


def start_frontend() -> subprocess.Popen[bytes]:
    env = dict(os.environ)
    env.setdefault("NEXT_PUBLIC_TWIN_API_URL", BACKEND_URL)
    print(f"[orion] starting Mission Control UI (API {env['NEXT_PUBLIC_TWIN_API_URL']})")
    return subprocess.Popen(["npm", "run", "dev"], cwd=UI_DIR, env=env)


def main() -> None:
    parser = argparse.ArgumentParser(description="Start ORIÓN.")
    parser.add_argument(
        "target",
        nargs="?",
        default="all",
        choices=["all", "backend", "frontend"],
        help="Which part of the stack to start (default: all).",
    )
    args = parser.parse_args()

    check_environment(need_ui=args.target in ("all", "frontend"))

    procs: list[subprocess.Popen[bytes]] = []
    try:
        if args.target in ("all", "backend"):
            backend = start_backend()
            procs.append(backend)
            wait_for_backend(backend)
        if args.target == "frontend":
            wait_for_backend(None)
        if args.target in ("all", "frontend"):
            procs.append(start_frontend())
            print("[orion] ORION READY — Mission Control: http://localhost:3000")
        while procs:
            for proc in procs:
                if proc.poll() is not None:
                    return
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
