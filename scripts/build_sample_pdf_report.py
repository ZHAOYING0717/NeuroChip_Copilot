from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from neurochip import assess_event_quality, extract_features, read_recording
from neurochip.modeling import PhenotypeModel
from neurochip.report import build_pdf_report


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the reproducible NeuroChip sample PDF report")
    parser.add_argument(
        "--input",
        type=Path,
        default=PROJECT_ROOT / "data" / "demo" / "fs363-org0_events.csv",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=PROJECT_ROOT / "models" / "phenotype_model.joblib",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "output" / "pdf" / "neurochip_sample_report.pdf",
    )
    args = parser.parse_args()
    recording = read_recording(args.input)
    features = extract_features(recording)
    quality, _ = assess_event_quality(recording)
    model = PhenotypeModel.load(args.model)
    feature_table = pd.DataFrame([features])
    model_result = model.transform(feature_table).iloc[0].to_dict()
    explanation = model.explain(feature_table, n_permutations=128)
    payload = build_pdf_report(
        recording,
        features,
        quality,
        model_result,
        explanation,
        project_name="Drug screening 2026",
        sample_name="Organoid001",
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(f"[complete] {len(payload):,} bytes -> {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
