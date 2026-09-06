from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "data" / "manifests" / "external_validation.json"
STATUS_PATH = PROJECT_ROOT / "artifacts" / "results" / "external_validation" / "trujillo_pipeline_status.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_status(status: str, **details) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"status": status, "updated_at_utc": now_utc(), **details}
    STATUS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[status] {status}: {details}", flush=True)


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def dataset_items() -> tuple[Path, list[dict]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    dataset = manifest["datasets"]["trujillo_organoid_pharmacology"]
    raw_dir = PROJECT_ROOT / dataset["raw_dir"]
    return raw_dir, list(dataset["files"])


def download_progress(raw_dir: Path, items: list[dict]) -> tuple[int, int, bool]:
    complete_bytes = 0
    expected_bytes = sum(int(item["size_bytes"]) for item in items)
    ready = True
    for item in items:
        target = raw_dir / item["name"]
        if target.exists() and target.stat().st_size == int(item["size_bytes"]):
            complete_bytes += target.stat().st_size
        else:
            ready = False
            partial = target.with_suffix(target.suffix + ".part")
            if partial.exists():
                complete_bytes += min(partial.stat().st_size, int(item["size_bytes"]))
    return complete_bytes, expected_bytes, ready


def wait_for_download(poll_seconds: int) -> tuple[Path, list[dict]]:
    raw_dir, items = dataset_items()
    while True:
        downloaded, expected, ready = download_progress(raw_dir, items)
        write_status(
            "waiting_for_download" if not ready else "download_sizes_complete",
            downloaded_bytes=downloaded,
            expected_bytes=expected,
            percent=round(downloaded / expected * 100.0, 3),
        )
        if ready:
            return raw_dir, items
        time.sleep(poll_seconds)


def verify_downloads(raw_dir: Path, items: list[dict]) -> None:
    write_status("verifying_downloads", files=len(items))
    for index, item in enumerate(items, start=1):
        target = raw_dir / item["name"]
        expected_size = int(item["size_bytes"])
        if not target.exists() or target.stat().st_size != expected_size:
            raise RuntimeError(f"Missing or incomplete file: {target}")
        expected_md5 = item.get("md5")
        observed_md5 = file_md5(target)
        if expected_md5 and observed_md5 != expected_md5:
            raise RuntimeError(f"MD5 mismatch for {target.name}: {observed_md5} != {expected_md5}")
        print(f"[verify {index}/{len(items)}] {target.name}", flush=True)
    write_status("downloads_verified", files=len(items))


def run_stage(name: str, command: list[str]) -> None:
    write_status(name, command=command)
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait for Trujillo downloads and automatically validate")
    parser.add_argument("--poll-seconds", type=int, default=300)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.poll_seconds < 10:
        raise ValueError("poll-seconds must be at least 10")
    try:
        raw_dir, items = wait_for_download(args.poll_seconds)
        verify_downloads(raw_dir, items)
        feature_command = [
            sys.executable,
            "-u",
            "scripts/build_external_trujillo_features.py",
            "--windows",
            "90",
            "120",
        ]
        if args.resume:
            feature_command.append("--resume")
        run_stage("extracting_features", feature_command)
        run_stage(
            "evaluating_frozen_model",
            [sys.executable, "-u", "scripts/evaluate_external_trujillo_validation.py"],
        )
        metrics_path = PROJECT_ROOT / "artifacts" / "results" / "external_validation" / "trujillo_metrics.json"
        write_status("complete", metrics_path=metrics_path.resolve().relative_to(PROJECT_ROOT).as_posix())
        return 0
    except Exception as error:
        write_status("failed", error_type=type(error).__name__, error=str(error))
        raise


if __name__ == "__main__":
    sys.exit(main())
