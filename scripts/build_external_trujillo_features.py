from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from neurochip import extract_features
from neurochip.trujillo import ACTIVE_WELLS, read_trujillo_well, treatment_effect_class, treatment_for_well


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "external" / "zenodo_4751759"
DEFAULT_WINDOWS = (90, 120)
DATE_PATTERN = re.compile(r"LFP_Sp_(\d{6})(?:_Drugs)?\.mat$")


@dataclass(frozen=True)
class WindowStage:
    stage: str
    source_kind: str
    start_multiplier: int


STAGES = (
    WindowStage("baseline_control", "baseline", 0),
    WindowStage("baseline_repeat", "baseline", 1),
    WindowStage("post_treatment", "drugs", 0),
)


def date_pairs(raw_dir: Path) -> list[tuple[str, Path, Path]]:
    baselines: dict[str, Path] = {}
    drugs: dict[str, Path] = {}
    for path in raw_dir.glob("LFP_Sp_*.mat"):
        match = DATE_PATTERN.fullmatch(path.name)
        if not match:
            continue
        recording_date = match.group(1)
        target = drugs if path.stem.endswith("_Drugs") else baselines
        target[recording_date] = path
    if set(baselines) != set(drugs):
        missing_baseline = sorted(set(drugs).difference(baselines))
        missing_drugs = sorted(set(baselines).difference(drugs))
        raise RuntimeError(
            f"Unpaired Trujillo files; missing baseline={missing_baseline}, missing drugs={missing_drugs}"
        )
    return [(date, baselines[date], drugs[date]) for date in sorted(baselines)]


def build_features(raw_dir: Path, output: Path, windows: tuple[int, ...], resume: bool) -> pd.DataFrame:
    pairs = date_pairs(raw_dir)
    expected = len(pairs) * len(ACTIVE_WELLS) * len(STAGES) * len(windows)
    checkpoint_dir = output.parent / "checkpoints" / output.stem
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    completed = 0
    for window_s in windows:
        for recording_date, baseline_path, drugs_path in pairs:
            treatment_paths = {"baseline": baseline_path, "drugs": drugs_path}
            for well in ACTIVE_WELLS:
                treatment = treatment_for_well(recording_date, well)
                effect_class = treatment_effect_class(treatment)
                for stage in STAGES:
                    completed += 1
                    checkpoint = checkpoint_dir / (
                        f"{recording_date}__well{well:02d}__{stage.stage}__{window_s}s.json"
                    )
                    row = None
                    if resume and checkpoint.exists():
                        candidate = json.loads(checkpoint.read_text(encoding="utf-8"))
                        if float(candidate.get("feature_schema_version", 0)) >= 2.0:
                            row = candidate
                    if row is not None:
                        print(f"[{completed:03d}/{expected}] resume {checkpoint.stem}", flush=True)
                    else:
                        source = treatment_paths[stage.source_kind]
                        start_s = stage.start_multiplier * window_s
                        recording_id = (
                            f"trujillo_{recording_date}__well{well:02d}__{stage.stage}__{window_s}s"
                        )
                        recording = read_trujillo_well(
                            source,
                            well,
                            start_s=float(start_s),
                            duration_s=float(window_s),
                            recording_id=recording_id,
                        )
                        print(
                            f"[{completed:03d}/{expected}] analyze {recording_id} "
                            f"({recording.n_spikes:,} spikes)",
                            flush=True,
                        )
                        row = extract_features(recording)
                        row.update(
                            {
                                "dataset_id": "trujillo_zenodo_4751759",
                                "recording_date": recording_date,
                                "well": int(well),
                                "group_id": f"{recording_date}__well{well:02d}",
                                "stage": stage.stage,
                                "treatment": treatment,
                                "treatment_effect_class": effect_class,
                                "analysis_window_s": int(window_s),
                                "window_start_s": int(start_s),
                                "source_file": source.name,
                                "data_doi": "10.5281/zenodo.4751759",
                                "article_doi": "10.1016/j.stem.2019.08.002",
                            }
                        )
                        checkpoint.write_text(json.dumps(row, indent=2, sort_keys=True), encoding="utf-8")
                    rows.append(row)

    table = pd.DataFrame(rows).sort_values(
        ["analysis_window_s", "recording_date", "well", "stage"], ignore_index=True
    )
    if len(table) != expected:
        raise RuntimeError(f"Expected {expected} feature rows, got {len(table)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output, index=False)
    print(f"[complete] {len(table)} feature rows -> {output}", flush=True)
    return table


def main() -> int:
    parser = argparse.ArgumentParser(description="Build external Trujillo organoid MEA features")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "external_trujillo_features.csv",
    )
    parser.add_argument("--windows", type=int, nargs="+", default=list(DEFAULT_WINDOWS))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    windows = tuple(dict.fromkeys(args.windows))
    if any(window <= 0 or window > 120 for window in windows):
        raise ValueError("Trujillo validation windows must be in the range 1..120 seconds")
    build_features(args.raw_dir, args.output, windows, args.resume)
    return 0


if __name__ == "__main__":
    sys.exit(main())
