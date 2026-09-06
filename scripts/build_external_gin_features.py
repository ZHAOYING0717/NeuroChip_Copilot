from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from neurochip import extract_features
from neurochip.gin_pharmacology import build_well_recording, load_gin_stage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = PROJECT_ROOT / "data" / "x" / "gin" / "comparative_mea_dataset"
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "external" / "gin_comparative_mea"


@dataclass(frozen=True)
class StageConfig:
    dataset_id: str
    culture_type: str
    stage: str
    protocol_duration_s: float
    spike_path: Path
    log_path: Path
    noisy_path: Path


def stage_configs() -> tuple[StageConfig, ...]:
    hpsc = REPOSITORY / "Data" / "hPSC_MEA3_Pharmacology"
    rat = REPOSITORY / "Data" / "Rat_MEA2_Pharmacology"
    return (
        StageConfig(
            "hpsc_mea3",
            "human iPSC-derived cortical neurons (2D)",
            "baseline",
            1800.0,
            RAW_DIR / "hPSC_120618_MEA3Baseline_DIV29_spikes.csv",
            hpsc / "hPSC_MEA3Baseline_DIV29" / "hPSC_MEA3Baseline_DIV29_spikes_noise_explogs" / "hPSC_120618_MEA3Baseline_DIV29_expLog.csv",
            hpsc / "hPSC_MEA3Baseline_DIV29" / "hPSC_MEA3Baseline_DIV29_spikes_noise_explogs" / "noisy_electrodes_hPSC_MEA3Baseline_DIV29.csv",
        ),
        StageConfig(
            "hpsc_mea3",
            "human iPSC-derived cortical neurons (2D)",
            "pharma",
            1800.0,
            RAW_DIR / "hPSC_120618_MEA3Pharma_DIV29_spikes.csv",
            hpsc / "hPSC_MEA3Pharma_DIV29" / "hPSC_MEA3Pharma_DIV29_spikes_noise_explogs" / "hPSC_120618_MEA3Pharma_DIV29_expLog.csv",
            hpsc / "hPSC_MEA3Pharma_DIV29" / "hPSC_MEA3Pharma_DIV29_spikes_noise_explogs" / "noisy_electrodes_hPSC_MEA3Pharma_DIV29.csv",
        ),
        StageConfig(
            "hpsc_mea3",
            "human iPSC-derived cortical neurons (2D)",
            "ttx",
            600.0,
            hpsc / "hPSC_MEA3TTX_DIV29" / "hPSC_MEA3TTX_DIV29_spikes_noise_explogs" / "hPSC_120618_MEA3TTX_DIV29_spikes.csv",
            hpsc / "hPSC_MEA3TTX_DIV29" / "hPSC_MEA3TTX_DIV29_spikes_noise_explogs" / "hPSC_120618_MEA3TTX_DIV29_expLog.csv",
            hpsc / "hPSC_MEA3TTX_DIV29" / "hPSC_MEA3TTX_DIV29_spikes_noise_explogs" / "noisy_electrodes_hPSC_MEA3TTX_DIV29.csv",
        ),
        StageConfig(
            "rat_mea2",
            "rat embryonic cortical neurons (2D)",
            "baseline",
            1800.0,
            RAW_DIR / "Rat_50618_MEA2Baseline_DIV22_spikes.csv",
            rat / "Rat_MEA2Baseline_DIV22" / "Rat_MEA2Baseline_DIV22_spikes_noise_explogs" / "Rat_50618_MEA2Baseline_DIV22_expLog.csv",
            rat / "Rat_MEA2Baseline_DIV22" / "Rat_MEA2Baseline_DIV22_spikes_noise_explogs" / "noisy_electrodes_Rat_MEA2Baseline_DIV22.csv",
        ),
        StageConfig(
            "rat_mea2",
            "rat embryonic cortical neurons (2D)",
            "pharma",
            1800.0,
            RAW_DIR / "Rat_50618_MEA2Pharma_DIV22_spikes.csv",
            rat / "Rat_MEA2Pharma_DIV22" / "Rat_MEA2Pharma_DIV22_spikes_noise_explogs" / "Rat_50618_MEA2Pharma_DIV22_expLog.csv",
            rat / "Rat_MEA2Pharma_DIV22" / "Rat_MEA2Pharma_DIV22_spikes_noise_explogs" / "noisy_electrodes_Rat_MEA2Pharma_DIV22.csv",
        ),
        StageConfig(
            "rat_mea2",
            "rat embryonic cortical neurons (2D)",
            "ttx",
            600.0,
            rat / "Rat_MEA2TTX_DIV22" / "Rat_MEA2TTX_DIV22_spikes_noise_explogs" / "Rat_50618_MEA2TTX_DIV22_spikes.csv",
            rat / "Rat_MEA2TTX_DIV22" / "Rat_MEA2TTX_DIV22_spikes_noise_explogs" / "Rat_50618_MEA2TTX_DIV22_expLog.csv",
            rat / "Rat_MEA2TTX_DIV22" / "Rat_MEA2TTX_DIV22_spikes_noise_explogs" / "noisy_electrodes_Rat_MEA2TTX_DIV22.csv",
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build matched-well features for the external GIN pharmacology data")
    parser.add_argument("--window-s", type=float, choices=(180.0, 600.0), default=180.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or PROJECT_ROOT / "data" / "processed" / f"external_gin_features_{args.window_s:g}s.csv"
    checkpoint_dir = output.parent / "checkpoints" / output.stem
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    configs = stage_configs()
    total_recordings = 198
    completed = 0
    for stage_index, config in enumerate(configs, start=1):
        print(f"[stage {stage_index}/{len(configs)}] load {config.dataset_id} {config.stage}", flush=True)
        stage = load_gin_stage(
            config.spike_path,
            config.log_path,
            config.protocol_duration_s,
            config.noisy_path,
        )
        for well in stage.wells:
            completed += 1
            checkpoint = checkpoint_dir / f"{config.dataset_id}__{config.stage}__{well}.json"
            row = json.loads(checkpoint.read_text(encoding="utf-8")) if args.resume and checkpoint.exists() else None
            if row is not None and float(row.get("feature_schema_version", 0)) >= 2.0:
                print(f"[{completed:03d}/{total_recordings}] resume {config.dataset_id} {config.stage} {well}", flush=True)
            else:
                if row is not None:
                    print(
                        f"[{completed:03d}/{total_recordings}] refresh stale checkpoint "
                        f"{config.dataset_id} {config.stage} {well}",
                        flush=True,
                    )
                recording_id = f"{config.dataset_id}__{config.stage}__{well}__{args.window_s:g}s"
                recording = build_well_recording(stage, well, args.window_s, recording_id)
                print(
                    f"[{completed:03d}/{total_recordings}] analyze {config.dataset_id} {config.stage} {well} "
                    f"({recording.n_spikes:,} spikes)",
                    flush=True,
                )
                row = extract_features(recording)
                row.update(
                    {
                        "dataset_id": config.dataset_id,
                        "culture_type": config.culture_type,
                        "stage": config.stage,
                        "well": well,
                        "group_id": f"{config.dataset_id}__{well}",
                        "treatment": recording.metadata["treatment"],
                        "dose_um": recording.metadata["dose_um"],
                        "analysis_window_s": args.window_s,
                        "protocol_duration_s": config.protocol_duration_s,
                        "noisy_channels_excluded": recording.metadata["noisy_channels_excluded"],
                        "stage_input_rows": stage.input_rows,
                        "stage_duplicate_rows_removed": stage.duplicate_rows_removed,
                        "stage_invalid_rows_removed": stage.invalid_rows_removed,
                        "data_doi": "10.12751/g-node.wvr3jf",
                    }
                )
                checkpoint.write_text(json.dumps(row, indent=2, sort_keys=True), encoding="utf-8")
            assert row is not None
            rows.append(row)
    table = pd.DataFrame(rows).sort_values(["dataset_id", "well", "stage"])
    if len(table) != total_recordings:
        raise RuntimeError(f"Expected {total_recordings} well-stage recordings, got {len(table)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output, index=False)
    print(f"[complete] {len(table)} recordings -> {output}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
