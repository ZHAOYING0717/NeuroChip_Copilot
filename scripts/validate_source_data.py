from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate extracted features against publisher source data")
    parser.add_argument(
        "--features",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "forebrain_features.csv",
    )
    parser.add_argument(
        "--source-data",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw" / "zenodo_20286251" / "fig_table_source_data.xlsx",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "results" / "source_validation",
    )
    args = parser.parse_args()
    extracted = pd.read_csv(args.features)
    published = pd.read_excel(args.source_data, sheet_name="ST1")
    merged = extracted.merge(published[["organoid", "FR", "STTC"]], left_on="recording_id", right_on="organoid", how="inner")
    merged["fr_abs_error"] = (merged["firing_rate_mean_hz"] - merged["FR"]).abs()
    merged["sttc_abs_error"] = (merged["sttc_mean"] - merged["STTC"]).abs()
    # Public validation tables must not expose the machine-specific source path.
    merged = merged.drop(columns=["source_path"], errors="ignore")
    report = {
        "n_extracted": int(len(extracted)),
        "n_published": int(len(published)),
        "n_matched": int(len(merged)),
        "firing_rate_max_abs_error": float(merged["fr_abs_error"].max()),
        "sttc_max_abs_error": float(merged["sttc_abs_error"].max()),
        "firing_rate_exact_within_1e_10": bool((merged["fr_abs_error"] < 1e-10).all()),
        "sttc_exact_within_1e_10": bool((merged["sttc_abs_error"] < 1e-10).all()),
        "sttc_delta_ms": 20,
        "source_sheet": "ST1",
        "source_dataset_doi": "10.5281/zenodo.20286251",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    merged.to_csv(args.output_dir / "feature_comparison.csv", index=False)
    (args.output_dir / "validation_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    if len(merged) != len(extracted) or not report["firing_rate_exact_within_1e_10"] or not report["sttc_exact_within_1e_10"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
