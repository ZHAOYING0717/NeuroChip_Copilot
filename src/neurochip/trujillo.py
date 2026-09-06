from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

from .schema import SpikeRecording


ACTIVE_WELLS = tuple(range(5, 13))

# These assignments are reproduced from the authors' corticoid_figures.m.
# The March recording is retained as unlabeled because no public well map was found.
TREATMENT_BY_DATE_AND_WELL: dict[tuple[str, int], str] = {
    **{("161217", well): "control" for well in (5, 6, 9, 10)},
    **{("161217", well): "CNQX+AP5" for well in (7, 11)},
    **{("161217", well): "bicuculline" for well in (8, 12)},
    **{("170207", well): "control" for well in (5, 9)},
    **{("170207", well): "baclofen" for well in (6, 10)},
    **{("170207", well): "CNQX+AP5" for well in (7, 11)},
    **{("170207", well): "bicuculline" for well in (8, 12)},
}


def treatment_for_well(recording_date: str, well: int) -> str:
    return TREATMENT_BY_DATE_AND_WELL.get((str(recording_date), int(well)), "unknown_pharmacology")


def treatment_effect_class(treatment: str) -> str:
    if treatment == "control":
        return "negative_control"
    if treatment in {"CNQX+AP5", "baclofen"}:
        return "active_spike_burst_perturbation"
    if treatment == "bicuculline":
        return "subtle_spike_effect"
    return "unlabeled"


def _time_axis_metadata(handle: h5py.File) -> tuple[float, float]:
    timestamps = handle["t_s"]
    if timestamps.ndim != 2 or timestamps.shape[0] != 1 or timestamps.shape[1] < 2:
        raise ValueError("Expected t_s to have shape (1, n_samples)")
    first = float(timestamps[0, 0])
    second = float(timestamps[0, 1])
    last = float(timestamps[0, -1])
    interval_s = second - first
    if not np.isfinite(interval_s) or interval_s <= 0:
        raise ValueError("Invalid t_s sampling interval")
    return 1.0 / interval_s, last + interval_s


def read_trujillo_well(
    path: str | Path,
    well: int,
    *,
    start_s: float = 0.0,
    duration_s: float | None = None,
    recording_id: str | None = None,
) -> SpikeRecording:
    """Read one active MEA well from a Trujillo MATLAB 7.3 spike file.

    The HDF5 representation has physical shape ``(64 channels, 12 wells)``.
    Spike values are sample numbers on the original 12.5 kHz time axis.
    """

    source = Path(path)
    well_number = int(well)
    if well_number not in range(1, 13):
        raise ValueError("well must be in the inclusive range 1..12")
    if start_s < 0:
        raise ValueError("start_s must be non-negative")

    with h5py.File(source, "r") as handle:
        if "spikes" not in handle or "spike_cnt" not in handle or "t_s" not in handle:
            raise ValueError(f"Missing required Trujillo variables in {source.name}")
        spikes = handle["spikes"]
        counts = np.asarray(handle["spike_cnt"], dtype=float)
        if spikes.shape != (64, 12) or counts.shape != (64, 12):
            raise ValueError(f"Unexpected spikes/spike_cnt shape in {source.name}")

        sampling_rate_hz, available_duration_s = _time_axis_metadata(handle)
        end_s = available_duration_s if duration_s is None else start_s + float(duration_s)
        if end_s > available_duration_s + 1e-9:
            raise ValueError(
                f"Requested window {start_s:g}-{end_s:g}s exceeds {available_duration_s:g}s in {source.name}"
            )
        if end_s <= start_s:
            raise ValueError("duration_s must be positive")

        channel_spikes: list[np.ndarray] = []
        well_index = well_number - 1
        for channel_index in range(64):
            count = int(counts[channel_index, well_index])
            if count <= 0:
                channel_spikes.append(np.array([], dtype=float))
                continue
            reference = spikes[channel_index, well_index]
            values = np.asarray(handle[reference], dtype=float).ravel()
            if values.size != count:
                raise ValueError(
                    f"spike_cnt mismatch in {source.name}, well {well_number}, channel {channel_index + 1}"
                )
            times = values / sampling_rate_hz
            selected = times[(times >= start_s) & (times < end_s)] - start_s
            channel_spikes.append(selected)

    identifier = recording_id or f"{source.stem}__well{well_number:02d}__{start_s:g}-{end_s:g}s"
    return SpikeRecording(
        recording_id=identifier,
        spike_times=channel_spikes,
        duration_s=end_s - start_s,
        channel_ids=[f"ch_{index:02d}" for index in range(1, 65)],
        metadata={
            "source_path": str(source.resolve()),
            "source_format": "Trujillo MATLAB 7.3 spike cells",
            "well": well_number,
            "window_start_s": float(start_s),
            "window_end_s": float(end_s),
            "sampling_rate_hz": float(sampling_rate_hz),
            "available_duration_s": float(available_duration_s),
        },
    )
