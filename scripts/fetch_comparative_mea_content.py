from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = PROJECT_ROOT / "tools" / "gin-cli" / "runtime"
GIN_EXE = RUNTIME / "bin" / "gin.exe"
GIT_EXE = RUNTIME / "git" / "bin" / "git.exe"
GIN_HOME = PROJECT_ROOT / "tools" / "gin-cli" / "home"
CLONE_PARENT = PROJECT_ROOT / "data" / "x" / "annex_https"
REPOSITORY = CLONE_PARENT / "Comparative_MEA_dataset"
CHECKPOINT_DIR = PROJECT_ROOT / "data" / "processed" / "checkpoints" / "gin_annex"

CONTENT_FILES = (
    {
        "path": "Data/hPSC_MEA3_Pharmacology/hPSC_MEA3Baseline_DIV29/"
        "hPSC_MEA3Baseline_DIV29_spikes_noise_explogs/hPSC_120618_MEA3Baseline_DIV29_spikes.csv",
        "size_bytes": 55828307,
        "md5": "7799f10e0737fa3f034c1b55d7268927",
    },
    {
        "path": "Data/hPSC_MEA3_Pharmacology/hPSC_MEA3Pharma_DIV29/"
        "hPSC_MEA3Pharma_DIV29_spikes_noise_explogs/hPSC_120618_MEA3Pharma_DIV29_spikes.csv",
        "size_bytes": 39336289,
        "md5": "0d3afb102f6f759f0cd01cfc47f0636f",
    },
    {
        "path": "Data/Rat_MEA2_Pharmacology/Rat_MEA2Baseline_DIV22/"
        "Rat_MEA2Baseline_DIV22_spikes_noise_explogs/Rat_50618_MEA2Baseline_DIV22_spikes.csv",
        "size_bytes": 60309223,
        "md5": "4f752f5703b2cf2d1df8a77f9209d9c1",
    },
    {
        "path": "Data/Rat_MEA2_Pharmacology/Rat_MEA2Pharma_DIV22/"
        "Rat_MEA2Pharma_DIV22_spikes_noise_explogs/Rat_50618_MEA2Pharma_DIV22_spikes.csv",
        "size_bytes": 25422767,
        "md5": "b19fd38b57cd49e973b940016dfc1a16",
    },
)


def md5sum(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def gin_environment() -> dict[str, str]:
    GIN_HOME.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(GIN_HOME),
            "USERPROFILE": str(GIN_HOME),
            "APPDATA": str(GIN_HOME / "AppData" / "Roaming"),
            "LOCALAPPDATA": str(GIN_HOME / "AppData" / "Local"),
            "PATH": os.pathsep.join(
                [
                    str(RUNTIME / "bin"),
                    str(RUNTIME / "git" / "usr" / "bin"),
                    str(RUNTIME / "git" / "bin"),
                    env.get("PATH", ""),
                ]
            ),
        }
    )
    return env


def run_gin(arguments: list[str], cwd: Path) -> None:
    print(f"[gin] {' '.join(arguments)}", flush=True)
    completed = subprocess.run([str(GIN_EXE), *arguments], cwd=cwd, env=gin_environment(), check=False)
    if completed.returncode:
        raise RuntimeError(f"GIN command failed with exit code {completed.returncode}: {' '.join(arguments)}")


def run_git(arguments: list[str], cwd: Path, check: bool = True) -> int:
    print(f"[git] {' '.join(arguments)}", flush=True)
    completed = subprocess.run([str(GIT_EXE), *arguments], cwd=cwd, env=gin_environment(), check=False)
    if check and completed.returncode:
        raise RuntimeError(f"Git command failed with exit code {completed.returncode}: {' '.join(arguments)}")
    return completed.returncode


def clone_public_repository(max_retries: int = 10) -> None:
    REPOSITORY.mkdir(parents=True, exist_ok=True)
    if not (REPOSITORY / ".git").exists():
        run_git(["init"], REPOSITORY)
        run_git(["config", "core.longpaths", "true"], REPOSITORY)
        run_git(
            ["remote", "add", "origin", "https://gin.g-node.org/NeuroGroup_TUNI/Comparative_MEA_dataset"],
            REPOSITORY,
        )
    for attempt in range(1, max_retries + 1):
        if run_git(["fetch", "--depth", "1", "origin", "master"], REPOSITORY, check=False) == 0:
            break
        if attempt == max_retries:
            raise RuntimeError("Public HTTPS fetch failed after repeated attempts; rerun with --resume")
        print(f"[git] reconnect {attempt}/{max_retries}", flush=True)
        time.sleep(min(attempt * 2, 10))
    run_git(["checkout", "--detach", "FETCH_HEAD"], REPOSITORY)


def ensure_annex(max_retries: int = 10) -> None:
    annex_checkpoint = CHECKPOINT_DIR / "annex.json"
    if annex_checkpoint.exists():
        status = json.loads(annex_checkpoint.read_text(encoding="utf-8")).get("status")
        if status == "complete":
            return
    annex_checkpoint.write_text(json.dumps({"status": "started"}, indent=2), encoding="utf-8")
    for attempt in range(1, max_retries + 1):
        result = run_git(["fetch", "origin", "git-annex:git-annex"], REPOSITORY, check=False)
        if result == 0:
            break
        if attempt == max_retries:
            raise RuntimeError("git-annex metadata fetch failed; rerun with --resume")
        print(f"[git-annex] reconnect {attempt}/{max_retries}", flush=True)
        time.sleep(min(attempt * 2, 10))
    run_git(["config", "user.name", "NeuroChip Copilot"], REPOSITORY)
    run_git(["config", "user.email", "neurochip-local@example.invalid"], REPOSITORY)
    run_git(["annex", "init", "NeuroChip external validation"], REPOSITORY)
    annex_checkpoint.write_text(json.dumps({"status": "complete"}, indent=2), encoding="utf-8")


def verify(item: dict[str, str | int]) -> dict[str, str | int | bool]:
    path = REPOSITORY / str(item["path"])
    size = path.stat().st_size
    if size != int(item["size_bytes"]):
        raise RuntimeError(f"Size mismatch for {path.name}: {size} != {item['size_bytes']}")
    checksum = md5sum(path)
    if checksum != item["md5"]:
        raise RuntimeError(f"MD5 mismatch for {path.name}: {checksum} != {item['md5']}")
    return {"path": str(item["path"]), "size_bytes": size, "md5": checksum, "verified": True}


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch the four annexed pharmacology spike files from GIN")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if not GIN_EXE.exists():
        raise RuntimeError("GIN CLI is missing; run scripts/setup_gin_cli.py --resume first")
    CLONE_PARENT.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    clone_checkpoint = CHECKPOINT_DIR / "repository.json"
    clone_complete = False
    if clone_checkpoint.exists():
        clone_complete = json.loads(clone_checkpoint.read_text(encoding="utf-8")).get("status") == "complete"
    if not clone_complete:
        if REPOSITORY.exists() and not (REPOSITORY / ".git").exists():
            raise RuntimeError("Incomplete GIN clone exists; preserve it and choose a new clone directory")
        clone_checkpoint.write_text(json.dumps({"status": "started"}, indent=2), encoding="utf-8")
        clone_public_repository()
        clone_checkpoint.write_text(json.dumps({"status": "complete"}, indent=2), encoding="utf-8")
    elif not args.resume:
        raise RuntimeError("GIN repository already exists; rerun with --resume")

    ensure_annex()

    receipts: list[dict[str, str | int | bool]] = []
    for index, item in enumerate(CONTENT_FILES, start=1):
        path = REPOSITORY / str(item["path"])
        checkpoint = CHECKPOINT_DIR / f"{index:02d}_{path.stem}.json"
        if args.resume and path.exists() and path.stat().st_size == int(item["size_bytes"]):
            receipt = verify(item)
            print(f"[{index}/{len(CONTENT_FILES)}] verified {path.name}", flush=True)
        else:
            print(f"[{index}/{len(CONTENT_FILES)}] fetch {path.name}", flush=True)
            run_gin(["get-content", str(item["path"])], REPOSITORY)
            receipt = verify(item)
        checkpoint.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        receipts.append(receipt)
    (CHECKPOINT_DIR / "complete.json").write_text(json.dumps(receipts, indent=2), encoding="utf-8")
    print(f"[complete] {len(receipts)} annexed spike files verified", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
