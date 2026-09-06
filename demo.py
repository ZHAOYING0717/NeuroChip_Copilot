from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def build_command(address: str, port: int, headless: bool) -> list[str]:
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(PROJECT_ROOT / "app.py"),
        "--server.address",
        address,
        "--server.port",
        str(port),
        "--server.headless",
        str(headless).lower(),
        "--browser.gatherUsageStats",
        "false",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch the NeuroChip Copilot competition demo")
    parser.add_argument("--address", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument(
        "--demo-only",
        action="store_true",
        help="Use only the lightweight public examples bundled with the repository",
    )
    args = parser.parse_args()
    environment = os.environ.copy()
    if args.demo_only:
        environment["NEUROCHIP_DEMO_ONLY"] = "1"
    return subprocess.call(build_command(args.address, args.port, args.headless), cwd=PROJECT_ROOT, env=environment)


if __name__ == "__main__":
    raise SystemExit(main())
