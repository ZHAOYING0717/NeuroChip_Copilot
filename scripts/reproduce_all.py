from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)


def run_stage(name: str, arguments: list[str], timings: list[dict[str, float | str]]) -> None:
    started = time.perf_counter()
    print(f"\n== {name} ==", flush=True)
    subprocess.run([str(PYTHON), *arguments], cwd=PROJECT_ROOT, check=True)
    elapsed = time.perf_counter() - started
    timings.append({"stage": name, "elapsed_s": round(elapsed, 3)})
    print(f"[stage complete] {name}: {elapsed:.1f} s", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reproduce the complete NeuroChip Copilot evidence package")
    parser.add_argument("--skip-download", action="store_true", help="Use already downloaded public data")
    parser.add_argument("--resume", action="store_true", help="Reuse per-recording feature checkpoints")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument(
        "--with-local-external-validation",
        action="store_true",
        help="Evaluate the frozen response model using GIN files already present locally; never downloads them",
    )
    args = parser.parse_args()

    timings: list[dict[str, float | str]] = []
    if not args.skip_download:
        run_stage("download and checksum public data", ["scripts/download_data.py", "--dataset", "all"], timings)
    resume = ["--resume"] if args.resume else []
    stages = [
        ("build reference features", ["scripts/build_features.py", *resume]),
        ("reproduce publisher source values", ["scripts/validate_source_data.py"]),
        ("train and validate phenotype model", ["scripts/train_phenotype.py", *resume]),
        ("build diazepam features", ["scripts/build_drug_features.py", *resume]),
        ("train and validate drug response", ["scripts/train_drug_response.py"]),
    ]
    if args.with_local_external_validation:
        stages.extend(
            [
                ("build external GIN features at 180 s", ["scripts/build_external_gin_features.py", "--window-s", "180", *resume]),
                ("build external GIN features at 600 s", ["scripts/build_external_gin_features.py", "--window-s", "600", *resume]),
                ("evaluate frozen model on external GIN data", ["scripts/evaluate_external_validation.py"]),
            ]
        )
    stages.extend(
        [
            ("export report figures", ["scripts/make_figures.py"]),
            ("export lightweight public assets", ["scripts/export_public_assets.py"]),
            ("build sample PDF report", ["scripts/build_sample_pdf_report.py"]),
            ("build technical report", ["scripts/build_technical_report.py"]),
        ]
    )
    if not args.skip_tests:
        stages.append(("run automated tests", ["-m", "pytest", "-q"]))
    for name, arguments in stages:
        run_stage(name, arguments, timings)

    result = {
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "stages": timings,
        "total_elapsed_s": round(sum(float(item["elapsed_s"]) for item in timings), 3),
    }
    output = PROJECT_ROOT / "artifacts" / "results" / "reproduction_run.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\n[complete] reproduction record -> {output}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
