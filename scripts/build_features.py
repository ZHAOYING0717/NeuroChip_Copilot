from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from neurochip import extract_features, read_recording


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build recording-level NeuroChip features")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "interim" / "zenodo_20286251" / "individual",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "forebrain_features.csv",
    )
    parser.add_argument("--resume", action="store_true", help="Reuse per-recording JSON checkpoints")
    args = parser.parse_args()
    paths = sorted([*args.input_dir.rglob("*.mat"), *args.input_dir.rglob("*.csv"), *args.input_dir.rglob("*.h5")])
    if not paths:
        raise FileNotFoundError(f"No supported recordings found under {args.input_dir}")
    checkpoint_dir = args.output.parent / "checkpoints" / args.output.stem
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for index, path in enumerate(paths, start=1):
        checkpoint = checkpoint_dir / f"{path.stem}.json"
        row = json.loads(checkpoint.read_text(encoding="utf-8")) if args.resume and checkpoint.exists() else None
        if row is not None and float(row.get("feature_schema_version", 0)) >= 2.0:
            print(f"[{index:03d}/{len(paths):03d}] resume {path.name}", flush=True)
        else:
            if row is not None:
                print(f"[{index:03d}/{len(paths):03d}] refresh stale checkpoint {path.name}", flush=True)
            print(f"[{index:03d}/{len(paths):03d}] analyze {path.name}", flush=True)
            recording = read_recording(path)
            row = extract_features(recording)
            row.update({key: value for key, value in recording.metadata.items() if isinstance(value, (str, int, float, bool))})
            checkpoint.write_text(json.dumps(row, indent=2, sort_keys=True), encoding="utf-8")
        assert row is not None
        rows.append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).sort_values("recording_id").to_csv(args.output, index=False)
    print(f"[complete] {len(rows)} recordings -> {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
