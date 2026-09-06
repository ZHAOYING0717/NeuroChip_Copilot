from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from download_external_validation import PROJECT_ROOT, download, safe_extract


GIN_CLI_ITEM = {
    "name": "gin-cli-1.12-windows64.zip",
    "size_bytes": 141944637,
    "url": "https://github.com/G-Node/gin-cli/releases/download/v1.12/gin-cli-1.12-windows64.zip",
    "archive": True,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the official GIN CLI in the project tools directory")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    tools_dir = PROJECT_ROOT / "tools" / "gin-cli"
    archive = tools_dir / GIN_CLI_ITEM["name"]
    receipt = download(GIN_CLI_ITEM, archive, args.resume)
    runtime = tools_dir / "runtime"
    marker = runtime / ".installed.json"
    if not marker.exists():
        print(f"[extract] {archive.name}", flush=True)
        safe_extract(archive, runtime)
        marker.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    executables = sorted(runtime.rglob("gin.exe"))
    if not executables:
        raise RuntimeError("GIN CLI archive did not contain gin.exe")
    print(f"[complete] {executables[0]}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
