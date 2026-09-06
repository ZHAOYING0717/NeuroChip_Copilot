from __future__ import annotations

import numpy as np
import pandas as pd

from neurochip.gin_pharmacology import (
    ELECTRODE_IDS,
    build_well_recording,
    load_gin_stage,
    parse_channel,
    parse_dose_um,
)


def test_parse_channel_and_dose() -> None:
    assert parse_channel("C7_43") == ("C7", "43")
    assert parse_dose_um("30uM") == 30.0
    assert parse_dose_um("1 μM") == 1.0
    assert np.isnan(parse_dose_um(""))


def test_load_stage_deduplicates_and_excludes_noisy_channel(tmp_path) -> None:
    spikes = tmp_path / "spikes.csv"
    pd.DataFrame(
        {
            "Channel": ["A2_11", "A2_11", "A2_12", "A2_12", "bad"],
            "Time": [0.1, 0.1, 0.2, 2.0, 0.3],
        }
    ).to_csv(spikes, index=False)
    experiment_log = tmp_path / "expLog.csv"
    pd.DataFrame(
        {
            "Well": ["A1", "A2"],
            "Treatment": ["ExcludedWell", "TTX"],
            "Dose": ["", "1uM"],
        }
    ).to_csv(experiment_log, index=False)
    noisy = tmp_path / "noisy.csv"
    pd.DataFrame({"DIV": ["A2_12"]}).to_csv(noisy, index=False)

    stage = load_gin_stage(spikes, experiment_log, 1.0, noisy)
    assert stage.wells == ["A2"]
    assert stage.duplicate_rows_removed == 1
    assert stage.invalid_rows_removed == 2
    recording = build_well_recording(stage, "A2", 1.0, "test")
    assert recording.n_channels == len(ELECTRODE_IDS) == 16
    assert recording.n_spikes == 1
    assert recording.spike_times[0].tolist() == [0.1]
    assert recording.spike_times[1].size == 0
    assert recording.metadata["noisy_channels_excluded"] == 1
