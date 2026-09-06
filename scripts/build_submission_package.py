"""Build integrity-checked public-repository and competition-delivery archives."""

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "submission"
REPOSITORY_ZIP = OUT / "NeuroChip_Copilot_Public_Repository.zip"
SUBMISSION_ZIP = OUT / "NeuroChip_Copilot_Submission_Package.zip"

ROOT_FILES = [
    ".dockerignore",
    ".gitignore",
    "CITATION.cff",
    "Dockerfile",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
    "app.py",
    "demo.py",
    "pyproject.toml",
    "requirements-report.txt",
    "requirements-video.txt",
    "requirements.txt",
    "start_dashboard.cmd",
]

DIRECTORIES = {
    ".streamlit": {".toml"},
    "src": {".py"},
    "scripts": {".py", ".ps1", ".js", ".json"},
    "tests": {".py"},
    "docs": {".md", ".png", ".svg", ".pdf"},
    "data/manifests": {".json"},
    "data/demo": {".md", ".csv", ".json"},
    "models": {".joblib", ".md"},
    "artifacts/results": {".json", ".csv"},
    "output/pdf": {".pdf"},
}

DELIVERABLES = {
    "deliverables/NeuroChip_Copilot_Technical_Report.pdf": ROOT
    / "output"
    / "pdf"
    / "NeuroChip_Copilot_Technical_Report.pdf",
    "deliverables/NeuroChip_Copilot_Demo_zh.mp4": ROOT
    / "output"
    / "video"
    / "NeuroChip_Copilot_Demo_zh.mp4",
    "deliverables/NeuroChip_Copilot_Demo_zh.srt": ROOT
    / "output"
    / "video"
    / "NeuroChip_Copilot_Demo_zh.srt",
    "deliverables/Kaggle_Writeup.md": ROOT / "docs" / "kaggle_writeup.md",
    "deliverables/Submission_Checklist.md": ROOT / "docs" / "submission_checklist.md",
    "deliverables/Submission_Handoff_CN.md": ROOT / "docs" / "submission_handoff_cn.md",
    "deliverables/figures/figure0_architecture.png": ROOT / "docs" / "assets" / "figure0_architecture.png",
    "deliverables/figures/figure1_validation.png": ROOT / "docs" / "assets" / "figure1_validation.png",
    "deliverables/figures/figure2_drug_response.png": ROOT / "docs" / "assets" / "figure2_drug_response.png",
    "deliverables/figures/figure3_external_validation.png": ROOT / "docs" / "assets" / "figure3_external_validation.png",
    "deliverables/NeuroChip_Sample_Report.pdf": ROOT / "output" / "pdf" / "neurochip_sample_report.pdf",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def repository_files() -> list[Path]:
    selected = [ROOT / name for name in ROOT_FILES]
    for directory, suffixes in DIRECTORIES.items():
        base = ROOT / directory
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in suffixes:
                continue
            relative = path.relative_to(ROOT)
            if "__pycache__" in relative.parts or "archive" in relative.parts:
                continue
            if path.suffix.lower() == ".tiff":
                continue
            selected.append(path)
    unique = sorted(set(selected), key=lambda path: path.relative_to(ROOT).as_posix())
    missing = [path for path in unique if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing repository files: " + ", ".join(map(str, missing)))
    return unique


def repository_manifest(paths: list[Path]) -> dict[str, object]:
    entries = []
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith("/") or ".." in Path(relative).parts:
            raise ValueError(f"Unsafe archive path: {relative}")
        entries.append({"path": relative, "size_bytes": path.stat().st_size, "sha256": sha256(path)})
    return {
        "project": "NeuroChip Copilot",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "file_count": len(entries),
        "files": entries,
    }


def write_repository_zip(paths: list[Path], manifest: dict[str, object]) -> None:
    with zipfile.ZipFile(REPOSITORY_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in paths:
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.writestr("REPOSITORY_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    with zipfile.ZipFile(REPOSITORY_ZIP) as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise RuntimeError(f"Corrupt repository archive member: {corrupt}")


def write_submission_zip(repo_manifest: dict[str, object]) -> dict[str, object]:
    required = {"repository/NeuroChip_Copilot_Public_Repository.zip": REPOSITORY_ZIP, **DELIVERABLES}
    missing = [path for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing deliverables: " + ", ".join(map(str, missing)))

    files = [
        {"path": archive_name, "size_bytes": path.stat().st_size, "sha256": sha256(path)}
        for archive_name, path in required.items()
    ]
    manifest: dict[str, object] = {
        "project": "NeuroChip Copilot",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Local competition submission handoff; public URLs and team identity remain account-owner actions.",
        "repository_manifest_sha256": hashlib.sha256(
            json.dumps(repo_manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "files": files,
    }
    checksum_text = "".join(f"{entry['sha256']}  {entry['path']}\n" for entry in files)

    with zipfile.ZipFile(SUBMISSION_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for archive_name, path in required.items():
            archive.write(path, archive_name)
        archive.writestr("PACKAGE_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        archive.writestr("SHA256SUMS.txt", checksum_text)
    with zipfile.ZipFile(SUBMISSION_ZIP) as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise RuntimeError(f"Corrupt submission archive member: {corrupt}")
    return manifest


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    paths = repository_files()
    repo_manifest = repository_manifest(paths)
    write_repository_zip(paths, repo_manifest)
    package_manifest = write_submission_zip(repo_manifest)

    summary = {
        "repository_zip": {
            "path": REPOSITORY_ZIP.relative_to(ROOT).as_posix(),
            "size_bytes": REPOSITORY_ZIP.stat().st_size,
            "sha256": sha256(REPOSITORY_ZIP),
            "file_count": repo_manifest["file_count"],
        },
        "submission_zip": {
            "path": SUBMISSION_ZIP.relative_to(ROOT).as_posix(),
            "size_bytes": SUBMISSION_ZIP.stat().st_size,
            "sha256": sha256(SUBMISSION_ZIP),
            "deliverable_count": len(package_manifest["files"]),
        },
    }
    summary_path = OUT / "package_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
