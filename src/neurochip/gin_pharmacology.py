from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .schema import SpikeRecording


ELECTRODE_IDS = (
    "11",
    "12",
    "13",
    "14",
    "21",
    "22",
    "23",
    "24",
    "31",
    "32",
    "33",
    "34",
    "41",
    "42",
    "43",
    "44",
)
CHANNEL_PATTERN = re.compile(r"^(?P<well>[A-F][1-8])_(?P<electrode>[1-4][1-4])$")
DOSE_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?:u|µ|μ)M", re.IGNORECASE)


def parse_channel(value: str) -> tuple[str, str]:
    match = CHANNEL_PATTERN.match(str(value).strip())
    if match is None:
        raise ValueError(f"Invalid Axion 48-well channel: {value}")
    return match.group("well"), match.group("electrode")


def parse_dose_um(value: object) -> float:
    if value is None or pd.isna(value):
        return float("nan")
    if isinstance(value, (int, float, np.number)):
        return float(value)
    match = DOSE_PATTERN.search(str(value).strip())
    return float(match.group("value")) if match else float("nan")


@dataclass
class GinStage:
    events: pd.DataFrame
    experiment_log: pd.DataFrame
    noisy_channels: frozenset[str]
    input_rows: int
    duplicate_rows_removed: int
    invalid_rows_removed: int
    protocol_duration_s: float
    source_path: Path

    @property
    def wells(self) -> list[str]:
        included = self.experiment_log.loc[
            self.experiment_log["Treatment"].str.casefold() != "excludedwell", "Well"
        ]
        return included.astype(str).tolist()


def _read_noisy_channels(path: str | Path | None) -> frozenset[str]:
    if path is None:
        return frozenset()
    table = pd.read_csv(path, dtype=str)
    if table.empty:
        return frozenset()
    values = table.iloc[:, 0].dropna().astype(str).str.strip()
    return frozenset(value for value in values if CHANNEL_PATTERN.match(value))


def load_gin_stage(
    spike_path: str | Path,
    experiment_log_path: str | Path,
    protocol_duration_s: float,
    noisy_channels_path: str | Path | None = None,
) -> GinStage:
    source = Path(spike_path)
    events = pd.read_csv(source, dtype={"Channel": "string", "Time": "float64"})
    missing = {"Channel", "Time"}.difference(events.columns)
    if missing:
        raise ValueError(f"{source.name} is missing columns: {', '.join(sorted(missing))}")
    input_rows = len(events)
    parsed = events["Channel"].str.extract(CHANNEL_PATTERN)
    valid = (
        parsed["well"].notna()
        & np.isfinite(events["Time"].to_numpy(float))
        & events["Time"].between(0.0, protocol_duration_s, inclusive="left")
    )
    invalid_rows = int((~valid).sum())
    events = events.loc[valid, ["Channel", "Time"]].copy()
    parsed = parsed.loc[valid]
    events["well"] = parsed["well"].astype(str)
    events["electrode"] = parsed["electrode"].astype(str)
    events = events.rename(columns={"Time": "time_s"})
    duplicate_rows = int(events.duplicated(["Channel", "time_s"]).sum())
    events = events.drop_duplicates(["Channel", "time_s"])

    experiment_log = pd.read_csv(experiment_log_path, dtype=str).fillna("")
    required_log = {"Well", "Treatment", "Dose"}
    missing_log = required_log.difference(experiment_log.columns)
    if missing_log:
        raise ValueError(f"Experiment log is missing columns: {', '.join(sorted(missing_log))}")
    experiment_log["Well"] = experiment_log["Well"].str.strip()
    experiment_log["Treatment"] = experiment_log["Treatment"].str.strip()
    experiment_log["dose_um"] = experiment_log["Dose"].map(parse_dose_um)

    included_wells = set(
        experiment_log.loc[experiment_log["Treatment"].str.casefold() != "excludedwell", "Well"]
    )
    unexpected_wells = set(events["well"]).difference(included_wells)
    if unexpected_wells:
        raise ValueError(f"Spike table contains excluded or unknown wells: {', '.join(sorted(unexpected_wells))}")
    unexpected_electrodes = set(events["electrode"]).difference(ELECTRODE_IDS)
    if unexpected_electrodes:
        raise ValueError(f"Unexpected electrode IDs: {', '.join(sorted(unexpected_electrodes))}")

    return GinStage(
        events=events,
        experiment_log=experiment_log,
        noisy_channels=_read_noisy_channels(noisy_channels_path),
        input_rows=input_rows,
        duplicate_rows_removed=duplicate_rows,
        invalid_rows_removed=invalid_rows,
        protocol_duration_s=float(protocol_duration_s),
        source_path=source,
    )


def build_well_recording(stage: GinStage, well: str, analysis_window_s: float, recording_id: str) -> SpikeRecording:
    if analysis_window_s <= 0 or analysis_window_s > stage.protocol_duration_s:
        raise ValueError("analysis_window_s must be within the recording duration")
    metadata_row = stage.experiment_log.loc[stage.experiment_log["Well"] == well]
    if len(metadata_row) != 1:
        raise ValueError(f"Expected exactly one experiment-log row for well {well}")
    metadata_row = metadata_row.iloc[0]
    well_events = stage.events.loc[
        (stage.events["well"] == well) & (stage.events["time_s"] < analysis_window_s)
    ]
    spike_times: list[np.ndarray] = []
    noisy_count = 0
    for electrode in ELECTRODE_IDS:
        channel = f"{well}_{electrode}"
        if channel in stage.noisy_channels:
            spike_times.append(np.array([], dtype=float))
            noisy_count += 1
        else:
            values = well_events.loc[well_events["electrode"] == electrode, "time_s"].to_numpy(float)
            spike_times.append(values)
    return SpikeRecording(
        recording_id=recording_id,
        spike_times=spike_times,
        duration_s=float(analysis_window_s),
        channel_ids=[f"{well}_{electrode}" for electrode in ELECTRODE_IDS],
        metadata={
            "well": well,
            "treatment": str(metadata_row["Treatment"]),
            "dose_um": float(metadata_row["dose_um"]),
            "source_path": str(stage.source_path),
            "protocol_duration_s": stage.protocol_duration_s,
            "analysis_window_s": float(analysis_window_s),
            "noisy_channels_excluded": noisy_count,
            "duplicates_removed_from_stage": stage.duplicate_rows_removed,
            "invalid_rows_removed_from_stage": stage.invalid_rows_removed,
        },
    )
