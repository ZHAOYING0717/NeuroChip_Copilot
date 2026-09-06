from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from neurochip import read_recording, recording_to_event_table


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def copy_file(source: Path, target: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"[copy] {source.relative_to(PROJECT_ROOT)} -> {target.relative_to(PROJECT_ROOT)}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export lightweight, redistributable public Demo assets")
    parser.add_argument(
        "--example",
        type=Path,
        default=PROJECT_ROOT / "data" / "interim" / "zenodo_20286251" / "individual" / "fs363-org0.mat",
    )
    args = parser.parse_args()

    recording = read_recording(args.example)
    rows = recording_to_event_table(recording, source_vendor="publisher_hdf5")
    demo_path = PROJECT_ROOT / "data" / "demo" / "fs363-org0_events.csv"
    demo_path.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(demo_path, index=False)
    print(f"[export] {len(rows)} events -> {demo_path.relative_to(PROJECT_ROOT)}", flush=True)

    copy_file(
        PROJECT_ROOT / "artifacts" / "models" / "phenotype_model.joblib",
        PROJECT_ROOT / "models" / "phenotype_model.joblib",
    )
    copy_file(
        PROJECT_ROOT / "artifacts" / "models" / "drug_response_model.joblib",
        PROJECT_ROOT / "models" / "drug_response_model.joblib",
    )
    drug_demo = PROJECT_ROOT / "data" / "demo" / "drug_response"
    copy_file(PROJECT_ROOT / "data" / "processed" / "diazepam_features.csv", drug_demo / "diazepam_features.csv")
    for name in ("cross_validation_predictions.csv", "ablation.csv", "metrics.json"):
        copy_file(PROJECT_ROOT / "artifacts" / "results" / "drug_response" / name, drug_demo / name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
