from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

from neurochip import extract_features, read_recording


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FILE_PATTERN = re.compile(r"(?:(control)|diazepam(?P<dose>\d+)uM)_(?P<organoid>\d+)\.mat$", re.IGNORECASE)


def parse_condition(path: Path) -> tuple[float, str]:
    match = FILE_PATTERN.match(path.name)
    if match is None:
        raise ValueError(f"Unrecognized drug filename: {path.name}")
    dose = 0.0 if match.group(1) else float(match.group("dose"))
    return dose, match.group("organoid")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build diazepam-response features")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "interim" / "zenodo_6578989" / "kilosort2" / "drug" / "kilosort2",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "diazepam_features.csv",
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    paths = sorted(args.input_dir.glob("*.mat"))
    if len(paths) < 10:
        raise RuntimeError(f"Expected at least 10 drug recordings, found {len(paths)}")
    checkpoint_dir = args.output.parent / "checkpoints" / args.output.stem
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for index, path in enumerate(paths, start=1):
        checkpoint = checkpoint_dir / f"{path.stem}.json"
        row = json.loads(checkpoint.read_text(encoding="utf-8")) if args.resume and checkpoint.exists() else None
        if row is not None and float(row.get("feature_schema_version", 0)) >= 2.0:
            print(f"[{index:02d}/{len(paths):02d}] resume {path.name}", flush=True)
        else:
            if row is not None:
                print(f"[{index:02d}/{len(paths):02d}] refresh stale checkpoint {path.name}", flush=True)
            dose, organoid = parse_condition(path)
            print(f"[{index:02d}/{len(paths):02d}] analyze {path.name}", flush=True)
            recording = read_recording(path, duration_s=180.0)
            row = extract_features(recording)
            row.update(
                {
                    "dose_um": dose,
                    "group_id": organoid,
                    "condition": "control" if dose == 0 else "diazepam",
                    "data_doi": "10.25349/D9031Z",
                    "sampling_rate_hz": recording.metadata.get("sampling_rate_hz"),
                    "duration_inferred": recording.metadata.get("duration_inferred"),
                    "protocol_duration_s": 180.0,
                    "duration_source": "Sharf et al. 2022 three-minute recording protocol",
                }
            )
            checkpoint.write_text(json.dumps(row, indent=2, sort_keys=True), encoding="utf-8")
        assert row is not None
        rows.append(row)
    output = pd.DataFrame(rows).sort_values(["group_id", "dose_um"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    print(f"[complete] {len(output)} conditions across {output['group_id'].nunique()} organoids -> {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
