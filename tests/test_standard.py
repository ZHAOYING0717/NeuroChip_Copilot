from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from neurochip.standard import convert_axion_csv, standardize_event_table


def test_standardize_axion_columns_and_filter_well():
    source = pd.DataFrame(
        {
            "Channel": ["A5_11", "A5_12", "B5_11"],
            "Time": [0.1, 0.2, 0.3],
            "Amplitude": [10, 11, 12],
        }
    )
    result = standardize_event_table(source, "sample", source_vendor="Axion", well="A5")
    assert result["channel_id"].tolist() == ["11", "12"]
    assert result["well_id"].tolist() == ["A5", "A5"]
    assert result["timestamp_s"].tolist() == [0.1, 0.2]


def test_chunked_axion_converter_is_resumable(tmp_path: Path):
    source = tmp_path / "axion.csv"
    pd.DataFrame({"Channel": ["A1_11", "A1_12", "A1_11"], "Time": [0.1, 0.2, 0.3]}).to_csv(source, index=False)
    output = tmp_path / "standard.csv"
    first = convert_axion_csv(source, output, chunksize=2)
    resumed = convert_axion_csv(source, output, chunksize=2, resume=True)
    assert first["complete"] is True
    assert resumed["source_sha256"] == first["source_sha256"]
    assert len(pd.read_csv(output)) == 3
    sidecar = json.loads(output.with_suffix(".csv.metadata.json").read_text(encoding="utf-8"))
    assert sidecar["schema_version"] == "1.0"
