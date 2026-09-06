from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
import urllib.request
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "data" / "manifests" / "external_validation.json"
CHECKPOINT_DIR = PROJECT_ROOT / "data" / "processed" / "checkpoints" / "external_downloads"
CHUNK_SIZE = 4 * 1024 * 1024
PROGRESS_INTERVAL = 100 * 1024 * 1024


def file_hash(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(path: Path, item: dict) -> dict[str, str | int | bool]:
    expected_size = int(item["size_bytes"])
    if path.stat().st_size != expected_size:
        raise RuntimeError(f"Size mismatch for {path.name}: {path.stat().st_size} != {expected_size}")
    expected_md5 = item.get("md5")
    md5 = file_hash(path, "md5")
    if expected_md5 and md5 != expected_md5:
        raise RuntimeError(f"MD5 mismatch for {path.name}: {md5} != {expected_md5}")
    if item.get("archive"):
        with zipfile.ZipFile(path) as archive:
            bad_member = archive.testzip()
        if bad_member:
            raise RuntimeError(f"ZIP CRC failed for {path.name}: {bad_member}")
    return {
        "name": path.name,
        "size_bytes": path.stat().st_size,
        "md5": md5,
        "sha256": file_hash(path, "sha256"),
        "verified": True,
    }


def download_without_ranges(
    item: dict, target: Path, max_retries: int
) -> dict[str, str | int | bool]:
    expected_size = int(item["size_bytes"])
    for attempt in range(1, max_retries + 1):
        partial = target.with_suffix(target.suffix + f".full-{attempt:02d}.part")
        if partial.exists():
            if partial.stat().st_size == expected_size:
                receipt = verify_file(partial, item)
                partial.replace(target)
                print(f"[verified] {target.name}", flush=True)
                return receipt
            print(f"  preserve incomplete full attempt {attempt}: {partial.stat().st_size:,} bytes", flush=True)
            continue
        print(f"[download] {target.name} full attempt {attempt}/{max_retries}", flush=True)
        request = urllib.request.Request(
            item["url"],
            headers={"User-Agent": "NeuroChip-Copilot/0.1", "Accept-Encoding": "identity"},
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response, partial.open("wb") as output:
                transferred = 0
                while chunk := response.read(CHUNK_SIZE):
                    output.write(chunk)
                    transferred += len(chunk)
        except (OSError, TimeoutError) as error:
            print(f"  full attempt {attempt} interrupted: {error}", flush=True)
            continue
        if partial.stat().st_size != expected_size:
            print(
                f"  full attempt {attempt} incomplete: {partial.stat().st_size:,}/{expected_size:,} bytes",
                flush=True,
            )
            continue
        receipt = verify_file(partial, item)
        partial.replace(target)
        print(f"[verified] {target.name}", flush=True)
        return receipt
    raise RuntimeError(f"Full-file download failed for {target.name}; completed attempts were preserved")


def download(item: dict, target: Path, resume: bool, max_retries: int = 20) -> dict[str, str | int | bool]:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        receipt = verify_file(target, item)
        print(f"[verified] {target.name}", flush=True)
        return receipt
    if item.get("range_supported") is False:
        return download_without_ranges(item, target, max_retries)

    partial = target.with_suffix(target.suffix + ".part")
    start = partial.stat().st_size if resume and partial.exists() else 0
    if partial.exists() and not resume:
        raise RuntimeError(f"Partial download exists for {target.name}; rerun with --resume")
    if start > int(item["size_bytes"]):
        raise RuntimeError(f"Partial download is larger than expected for {target.name}")

    print(f"[download] {target.name} from byte {start:,}", flush=True)
    started = time.monotonic()
    expected_size = int(item["size_bytes"])
    transferred = start
    next_report = ((start // PROGRESS_INTERVAL) + 1) * PROGRESS_INTERVAL
    attempts = 0
    stalled_attempts = 0
    while transferred < expected_size:
        headers = {"User-Agent": "NeuroChip-Copilot/0.1"}
        if transferred:
            headers["Range"] = f"bytes={transferred}-"
        request = urllib.request.Request(item["url"], headers=headers)
        before_request = transferred
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                if transferred and response.status != 206:
                    raise RuntimeError(
                        f"Server did not honor Range request for {target.name}; partial file was preserved"
                    )
                with partial.open("ab" if transferred else "wb") as output:
                    while chunk := response.read(CHUNK_SIZE):
                        output.write(chunk)
                        transferred += len(chunk)
                        if transferred >= next_report:
                            elapsed = max(time.monotonic() - started, 1e-6)
                            new_bytes = max(transferred - start, 0)
                            speed = new_bytes / elapsed / 1024**2
                            percent = transferred / expected_size * 100
                            print(
                                f"  {transferred / 1024**2:,.1f} MB / {expected_size / 1024**2:,.1f} MB "
                                f"({percent:.1f}%, {speed:.1f} MB/s)",
                                flush=True,
                            )
                            next_report += PROGRESS_INTERVAL
        except (OSError, TimeoutError) as error:
            print(f"  connection interrupted at byte {transferred:,}: {error}", flush=True)
        if transferred >= expected_size:
            break
        attempts += 1
        if transferred == before_request:
            stalled_attempts += 1
        else:
            stalled_attempts = 0
        if stalled_attempts >= max_retries:
            raise RuntimeError(
                f"Download stalled for {target.name} at {transferred:,}/{expected_size:,} bytes; "
                "rerun with --resume"
            )
        print(
            f"  reconnect {attempts} (consecutive stalls {stalled_attempts}/{max_retries}) "
            f"from byte {transferred:,}",
            flush=True,
        )
        time.sleep(min(attempts, 5))
    receipt = verify_file(partial, item)
    partial.replace(target)
    print(f"[verified] {target.name}", flush=True)
    return receipt


def safe_extract(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if target != destination_root and destination_root not in target.parents:
                raise RuntimeError(f"Unsafe archive member: {member.filename}")
        archive.extractall(destination)


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    names = tuple(manifest["datasets"])
    parser = argparse.ArgumentParser(description="Download external validation datasets with checkpoints")
    parser.add_argument("--dataset", choices=(*names, "all"), default="all")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--no-extract", action="store_true")
    args = parser.parse_args()

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    selected = names if args.dataset == "all" else (args.dataset,)
    for dataset_name in selected:
        dataset = manifest["datasets"][dataset_name]
        raw_dir = PROJECT_ROOT / dataset["raw_dir"]
        receipts: list[dict[str, str | int | bool]] = []
        print(f"\n== {dataset_name}: {dataset['data_doi']} ==", flush=True)
        for item in dataset["files"]:
            target = raw_dir / item["name"]
            receipt = download(item, target, args.resume)
            receipts.append(receipt)
            checkpoint = CHECKPOINT_DIR / f"{dataset_name}__{target.name}.json"
            checkpoint.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
            if item.get("archive") and not args.no_extract:
                destination = PROJECT_ROOT / item["extract_to"]
                marker = destination / f".{target.stem}.extracted"
                if not marker.exists():
                    print(f"[extract] {target.name}", flush=True)
                    safe_extract(target, destination)
                    marker.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        dataset_receipt = CHECKPOINT_DIR / f"{dataset_name}.json"
        dataset_receipt.write_text(json.dumps(receipts, indent=2), encoding="utf-8")
        print(f"[complete] {dataset_name}: {len(receipts)} files", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
