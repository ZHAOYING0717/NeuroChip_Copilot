"""Audit local competition deliverables without requiring account-owned public URLs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "submission"
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".toml",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".cff",
    ".ps1",
    ".js",
    ".csv",
    ".tsv",
    ".html",
}
PRIVATE_CONTENT_PATTERN = re.compile(
    r"(?:[A-Za-z]:(?:[\\/]{1,2})(?:Users|codex-workspace)(?:[\\/]{1,2})"
    + r"|/(?:Users|home|codex-workspace)/"
    + "|AK"
    + r"IA[0-9A-Z]{16}"
    + "|gh"
    + r"p_[A-Za-z0-9]{20,}"
    + "|s"
    + r"k-[A-Za-z0-9]{20,})",
    flags=re.IGNORECASE,
)


def contains_private_content(content: str) -> bool:
    """Detect native and JSON-escaped local paths plus common credentials."""

    return bool(PRIVATE_CONTENT_PATTERN.search(content))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-public-links", action="store_true")
    args = parser.parse_args()
    checks: list[dict[str, str]] = []

    def record(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    required = [
        ROOT / "README.md",
        ROOT / "app.py",
        ROOT / "demo.py",
        ROOT / "src" / "neurochip" / "functional_effect.py",
        ROOT / "models" / "phenotype_model.joblib",
        ROOT / "models" / "drug_response_model.joblib",
        ROOT / "output" / "pdf" / "NeuroChip_Copilot_Technical_Report.pdf",
        ROOT / "output" / "video" / "NeuroChip_Copilot_Demo_zh.mp4",
        ROOT / "output" / "video" / "NeuroChip_Copilot_Demo_zh.srt",
        ROOT / "docs" / "kaggle_writeup.md",
        ROOT / "docs" / "kaggle_requirements_matrix.md",
        OUT / "NeuroChip_Copilot_Public_Repository.zip",
        OUT / "NeuroChip_Copilot_Submission_Package.zip",
    ]
    missing = [path.relative_to(ROOT).as_posix() for path in required if not path.exists()]
    record("required local artifacts", "fail" if missing else "pass", ", ".join(missing) if missing else "all present")

    phenotype = json.loads((ROOT / "artifacts/results/phenotype/metrics.json").read_text(encoding="utf-8"))
    drug = json.loads((ROOT / "artifacts/results/drug_response/metrics.json").read_text(encoding="utf-8"))
    external = json.loads((ROOT / "artifacts/results/external_validation/gin_metrics.json").read_text(encoding="utf-8"))
    trujillo = json.loads(
        (ROOT / "artifacts/results/external_validation/trujillo_metrics.json").read_text(encoding="utf-8")
    )
    external_primary = {
        item["comparison"]: item
        for item in external["metrics"]
        if item["window_s"] == 180 and item["dataset_id"] == "pooled"
    }
    metrics_ok = (
        abs(phenotype["roc_auc"] - 0.8579423868312758) < 1e-12
        and abs(drug["response_magnitude_dose_spearman"] - 0.9039688845323001) < 1e-12
        and abs(drug["high_dose_auc"] - 0.9642857142857143) < 1e-12
        and abs(external_primary["pharma_vs_baseline"]["roc_auc"] - 0.9520661157024792) < 1e-12
        and abs(external_primary["ttx_vs_pharma"]["roc_auc"] - 0.95) < 1e-12
        and abs(trujillo["primary_labeled_endpoint"]["roc_auc"] - 0.888888888888889) < 1e-12
        and abs(trujillo["paired_natural_drift_check"]["paired_wilcoxon_active_greater_p"] - 0.015625) < 1e-12
    )
    record(
        "frozen headline metrics",
        "pass" if metrics_ok else "fail",
        "phenotype AUROC, internal dose rho/high-dose AUC, pooled GIN AUCs, and Trujillo AUC/drift test",
    )

    report = ROOT / "output/pdf/NeuroChip_Copilot_Technical_Report.pdf"
    if report.exists():
        reader = PdfReader(report)
        report_ok = not reader.is_encrypted and 15 <= len(reader.pages) <= 20
        record("technical report", "pass" if report_ok else "fail", f"{len(reader.pages)} pages; encrypted={reader.is_encrypted}")

    video = ROOT / "output/video/NeuroChip_Copilot_Demo_zh.mp4"
    metadata_path = ROOT / "output/video/video_metadata.json"
    if video.exists() and metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        video_ok = (
            metadata["duration_s"] <= 300
            and metadata["resolution"] == [1280, 720]
            and metadata["captioned"] is True
            and metadata["sha256"] == sha256(video)
        )
        record(
            "competition video",
            "pass" if video_ok else "fail",
            f"{metadata['duration_s']:.2f} s; {metadata['resolution'][0]}x{metadata['resolution'][1]}; captions={metadata['captioned']}",
        )

    findings: list[str] = []
    repository_archive = OUT / "NeuroChip_Copilot_Public_Repository.zip"
    if repository_archive.exists():
        with zipfile.ZipFile(repository_archive) as archive:
            for name in archive.namelist():
                if Path(name).suffix.lower() not in TEXT_SUFFIXES:
                    continue
                content = archive.read(name).decode("utf-8", errors="ignore")
                if contains_private_content(content):
                    findings.append(name)
    record("private path and credential scan", "fail" if findings else "pass", ", ".join(findings) if findings else "no matches")

    for archive_name in ["NeuroChip_Copilot_Public_Repository.zip", "NeuroChip_Copilot_Submission_Package.zip"]:
        archive_path = OUT / archive_name
        if not archive_path.exists():
            continue
        with zipfile.ZipFile(archive_path) as archive:
            bad_member = archive.testzip()
            unsafe = [name for name in archive.namelist() if name.startswith(("/", "\\")) or ".." in Path(name).parts]
        status = "pass" if bad_member is None and not unsafe else "fail"
        record(f"archive integrity: {archive_name}", status, f"corrupt={bad_member}; unsafe_paths={len(unsafe)}")

    writeup = (ROOT / "docs/kaggle_writeup.md").read_text(encoding="utf-8")
    checklist = (ROOT / "docs/submission_checklist.md").read_text(encoding="utf-8")
    report_source = (ROOT / "docs/technical_report.md").read_text(encoding="utf-8")
    official_tokens = {
        "Submission Category: End-to-End System": "Writeup category declaration",
        "10 October 2026": "official preliminary deadline",
        "Problem Importance and Potential Impact (30%)": "official 30% impact criterion",
        "Technical Approach and Innovation (30%)": "official 30% technical criterion",
        "Results and Validation (20%)": "official 20% validation criterion",
        "Reproducibility and Implementation Quality (10%)": "official 10% reproducibility criterion",
        "Presentation Quality (10%)": "official 10% presentation criterion",
        "docs.google.com/forms/d/e/1FAIpQLSdRAat5jIunRaFNh_NntsVeJUnekEJDrbuokLZ32LFgCwPtiA": "mandatory registration form",
    }
    official_text = "\n".join([writeup, checklist, report_source, (ROOT / "README.md").read_text(encoding="utf-8")])
    missing_official = [label for token, label in official_tokens.items() if token not in official_text]
    record(
        "official competition declarations",
        "fail" if missing_official else "pass",
        ", ".join(missing_official) if missing_official else "category, deadline, registration, and 30/30/20/10/10 criteria recorded",
    )

    placeholder_count = len(re.findall(r"\[PUBLIC_[A-Z_]+\]", writeup))
    link_status = "fail" if args.require_public_links and placeholder_count else ("warn" if placeholder_count else "pass")
    record(
        "account-owned public links",
        link_status,
        f"{placeholder_count} placeholders remain; publication requires the entrant's accounts" if placeholder_count else "all public links filled",
    )

    team_placeholder_count = len(
        re.findall(r"\[(?:TEAM|YES_OR_NO|REGISTRATION)[A-Z_]*\]", writeup + "\n" + report_source)
    )
    team_status = "fail" if args.require_public_links and team_placeholder_count else ("warn" if team_placeholder_count else "pass")
    record(
        "team identity and eligibility declaration",
        team_status,
        f"{team_placeholder_count} placeholders remain; entrant identity cannot be inferred" if team_placeholder_count else "team fields complete",
    )

    freshness_sources = [
        ROOT / "app.py",
        ROOT / "docs/video_script_5min_cn.md",
        ROOT / "scripts/video_narration_zh.json",
        ROOT / "scripts/record_app_demo.js",
        ROOT / "scripts/make_video_slides.py",
        ROOT / "scripts/build_video.py",
    ]
    if video.exists():
        video_stale = video.stat().st_mtime_ns < max(path.stat().st_mtime_ns for path in freshness_sources)
        stale_status = "fail" if args.require_public_links and video_stale else ("warn" if video_stale else "pass")
        record(
            "final video freshness",
            stale_status,
            "video predates the final interface/script and must be rebuilt" if video_stale else "video is newer than interface and script",
        )

    archive_sources = [
        ROOT / "README.md",
        ROOT / "CITATION.cff",
        ROOT / "app.py",
        ROOT / "demo.py",
        ROOT / "docs/kaggle_writeup.md",
        ROOT / "docs/technical_report.md",
        ROOT / "output/pdf/NeuroChip_Copilot_Technical_Report.pdf",
    ]
    archives_stale = any(
        path.exists() and path.stat().st_mtime_ns < max(source.stat().st_mtime_ns for source in archive_sources)
        for path in (OUT / "NeuroChip_Copilot_Public_Repository.zip", OUT / "NeuroChip_Copilot_Submission_Package.zip")
    )
    archive_status = "fail" if args.require_public_links and archives_stale else ("warn" if archives_stale else "pass")
    record(
        "final archive freshness",
        archive_status,
        "one or more archives predate current sources and must be rebuilt" if archives_stale else "archives are current",
    )

    failed = sum(check["status"] == "fail" for check in checks)
    warned = sum(check["status"] == "warn" for check in checks)
    result = {"status": "fail" if failed else "pass_with_external_actions" if warned else "pass", "checks": checks}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "submission_audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = ["# Submission Audit", "", f"Overall: **{result['status']}**", ""]
    markdown.extend(f"- [{check['status'].upper()}] {check['name']}: {check['detail']}" for check in checks)
    (OUT / "submission_audit.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
