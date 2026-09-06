from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "data" / "manifests" / "datasets.json"


def md5sum(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract(archive: Path, destination: Path, prefixes: list[str] | None = None) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    resolved_destination = destination.resolve()
    with zipfile.ZipFile(archive) as handle:
        members = [
            member
            for member in handle.infolist()
            if not prefixes or any(member.filename.startswith(prefix) for prefix in prefixes)
        ]
        if not members:
            raise ValueError(f"No archive members matched prefixes: {prefixes}")
        for member in members:
            target = (destination / member.filename).resolve()
            if resolved_destination not in target.parents and target != resolved_destination:
                raise ValueError(f"Unsafe archive member: {member.filename}")
        handle.extractall(destination, members=members)


def download(url: str, target: Path, expected_size: int, expected_md5: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size == expected_size and md5sum(target) == expected_md5:
        print(f"[verified] {target.name}", flush=True)
        return
    partial = target.with_suffix(target.suffix + ".part")
    start = partial.stat().st_size if partial.exists() else 0
    request = urllib.request.Request(url, headers={"Range": f"bytes={start}-"} if start else {})
    print(f"[download] {target.name} from byte {start:,}", flush=True)
    with urllib.request.urlopen(request, timeout=120) as response:
        range_supported = response.status == 206
        mode = "ab" if start and range_supported else "wb"
        transferred = start if mode == "ab" else 0
        if start and not range_supported:
            print("  server ignored Range; restarting this partial file", flush=True)
        with partial.open(mode) as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                transferred += len(chunk)
                if transferred % (25 * 1024 * 1024) < len(chunk):
                    print(f"  {transferred / 1024**2:.1f} MB", flush=True)
    if partial.stat().st_size != expected_size:
        raise RuntimeError(f"Size mismatch for {target.name}: {partial.stat().st_size} != {expected_size}")
    checksum = md5sum(partial)
    if checksum != expected_md5:
        raise RuntimeError(f"MD5 mismatch for {target.name}: {checksum} != {expected_md5}")
    shutil.move(str(partial), str(target))
    print(f"[verified] {target.name}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and verify public NeuroChip datasets")
    parser.add_argument("--dataset", choices=["forebrain_spikes", "diazepam_response", "all"], default="all")
    parser.add_argument("--no-extract", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    selected = manifest["datasets"].keys() if args.dataset == "all" else [args.dataset]
    for dataset_name in selected:
        dataset = manifest["datasets"][dataset_name]
        raw_dir = PROJECT_ROOT / "data" / "raw" / f"zenodo_{dataset['record_id']}"
        print(f"\n== {dataset_name}: {dataset['doi']} ==", flush=True)
        for item in dataset["files"]:
            target = raw_dir / item["name"]
            download(item["url"], target, int(item["size_bytes"]), item["md5"])
            if not args.no_extract and item.get("extract_to"):
                destination = PROJECT_ROOT / item["extract_to"]
                marker = destination / f".{target.name}.extracted"
                if not marker.exists():
                    print(f"[extract] {target.name}", flush=True)
                    safe_extract(target, destination, item.get("extract_prefixes"))
                    marker.touch()
    return 0


if __name__ == "__main__":
    sys.exit(main())
