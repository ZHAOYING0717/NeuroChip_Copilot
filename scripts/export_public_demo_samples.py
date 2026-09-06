from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from neurochip.public_samples import discover_public_samples, load_public_sample
from neurochip.standard import recording_to_event_table


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "data" / "demo" / "public_samples"
SELECTED_KEYS = (
    "forebrain:fs363-org0",
    "diazepam:control_2950",
    "diazepam:diazepam50uM_2950",
    "gin:hpsc_mea3:pharma:A5",
    "trujillo:161217:7:baseline_control",
    "trujillo:161217:7:post_treatment",
)


def main() -> int:
    groups = discover_public_samples(PROJECT_ROOT)
    samples = {
        sample.key: sample
        for dataset_samples in groups.values()
        for sample in dataset_samples
    }
    missing = set(SELECTED_KEYS).difference(samples)
    if missing:
        raise FileNotFoundError(f"Missing source samples: {', '.join(sorted(missing))}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    for key in SELECTED_KEYS:
        sample = samples[key]
        if key == "forebrain:fs363-org0":
            file_name = "../fs363-org0_events.csv"
            recording = load_public_sample(sample)
        else:
            recording = load_public_sample(sample)
            file_name = f"{key.replace(':', '__')}_events.csv"
            table = recording_to_event_table(recording, source_vendor="public_demo_export")
            table.to_csv(OUTPUT_DIR / file_name, index=False)
        manifest_rows.append(
            {
                "sample_id": key.replace(":", "__"),
                "dataset_id": sample.dataset_id,
                "dataset_label": sample.dataset_label,
                "sample_label": sample.sample_label,
                "file_name": file_name,
                "duration_s": recording.duration_s,
                "data_doi": sample.data_doi,
                "context": sample.context,
                "notice": sample.notice,
            }
        )
        print(f"[export] {sample.dataset_label}: {sample.sample_label}", flush=True)

    pd.DataFrame(manifest_rows).to_csv(OUTPUT_DIR / "manifest.csv", index=False, encoding="utf-8-sig")
    print(f"[complete] {len(manifest_rows)} public demo samples -> {OUTPUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
