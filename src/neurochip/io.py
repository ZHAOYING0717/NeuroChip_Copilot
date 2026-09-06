from __future__ import annotations

from pathlib import Path
from typing import Any

import h5py
import numpy as np
import pandas as pd
from scipy.io import loadmat

from .schema import SpikeRecording
from .standard import infer_event_columns


def _decode_matlab_chars(values: np.ndarray) -> str:
    array = np.asarray(values).ravel()
    if array.dtype.kind in "ui":
        return "".join(chr(int(value)) for value in array if int(value) > 0)
    return str(array.tolist())


def _scalar(group: h5py.Group, key: str, default: float | None = None) -> float | None:
    if key not in group:
        return default
    values = np.asarray(group[key][()]).ravel()
    return float(values[0]) if values.size else default


def _object_vectors(handle: h5py.File, dataset_name: str) -> list[np.ndarray] | None:
    if dataset_name not in handle:
        return None
    dataset = handle[dataset_name]
    if dataset.dtype.kind != "O":
        values = np.asarray(dataset[()])
        if values.ndim == 1:
            return [values.astype(float)]
        return [np.asarray(row, dtype=float).ravel() for row in values]
    result: list[np.ndarray] = []
    for reference in np.asarray(dataset[()]).ravel():
        if not reference:
            result.append(np.array([], dtype=float))
            continue
        referenced = handle[reference]
        if bool(referenced.attrs.get("MATLAB_empty", 0)):
            result.append(np.array([], dtype=float))
        else:
            result.append(np.asarray(referenced[()], dtype=float).ravel())
    return result


def read_hdf5_mat(path: str | Path) -> SpikeRecording:
    source = Path(path)
    with h5py.File(source, "r") as handle:
        spikes = _object_vectors(handle, "spike_times")
        if spikes is None:
            raise ValueError(f"{source.name} has no spike_times dataset")
        amplitudes = _object_vectors(handle, "amplitudes")
        metadata_group = handle.get("metadata")
        metadata: dict[str, Any] = {"source_path": str(source), "source_format": "matlab-v7.3"}
        duration = max((float(np.max(times)) for times in spikes if times.size), default=0.0)
        channel_ids = [f"ch_{index + 1}" for index in range(len(spikes))]
        if isinstance(metadata_group, h5py.Group):
            duration = _scalar(metadata_group, "recording_duration", duration) or duration
            if "channel_ids" in metadata_group:
                channel_ids = [str(int(value)) for value in np.asarray(metadata_group["channel_ids"][()]).ravel()]
            for key in ("fs_id", "org_id", "n_blocks", "sweep_duration", "sweeps_per_block"):
                value = _scalar(metadata_group, key)
                if value is not None:
                    metadata[key] = value
            for key in ("source_file", "source_folder", "file_format"):
                if key in metadata_group:
                    metadata[key] = _decode_matlab_chars(metadata_group[key][()])
        return SpikeRecording(
            recording_id=source.stem,
            spike_times=spikes,
            duration_s=float(duration),
            channel_ids=channel_ids,
            amplitudes=amplitudes,
            metadata=metadata,
        )


def _extract_unit_spikes(units: Any) -> list[np.ndarray]:
    flat = np.asarray(units, dtype=object).ravel()
    spikes: list[np.ndarray] = []
    for unit in flat:
        if hasattr(unit, "spike_train"):
            spikes.append(np.asarray(unit.spike_train, dtype=float).ravel())
        elif isinstance(unit, np.void) and unit.dtype.names and "spike_train" in unit.dtype.names:
            spikes.append(np.asarray(unit["spike_train"], dtype=float).ravel())
    return spikes


def read_legacy_mat(path: str | Path) -> SpikeRecording:
    source = Path(path)
    payload = loadmat(source, squeeze_me=True, struct_as_record=False)
    channel_ids: list[str] | None = None
    if "spike_times" in payload:
        raw = np.asarray(payload["spike_times"], dtype=object).ravel()
        spikes = [np.asarray(values, dtype=float).ravel() for values in raw]
    elif "units" in payload:
        units = np.asarray(payload["units"], dtype=object).ravel()
        spikes = _extract_unit_spikes(units)
        channel_ids = [str(getattr(unit, "unit_id", index)) for index, unit in enumerate(units)]
    else:
        raise ValueError(f"{source.name} contains neither spike_times nor units")
    if not spikes:
        raise ValueError(f"{source.name} contains no readable spike trains")
    max_time = max((float(np.max(values)) for values in spikes if values.size), default=0.0)
    sampling_rate = float(np.asarray(payload.get("sampling_rate", payload.get("fs", 1.0))).squeeze())
    if max_time > 1e5 and sampling_rate > 1:
        spikes = [values / sampling_rate for values in spikes]
        max_time /= sampling_rate
    has_declared_duration = "recording_duration" in payload
    duration = float(np.asarray(payload.get("recording_duration", np.ceil(max_time / 10.0) * 10.0)).squeeze())
    return SpikeRecording(
        recording_id=source.stem,
        spike_times=spikes,
        duration_s=max(duration, max_time + 1e-6),
        channel_ids=channel_ids or [],
        metadata={
            "source_path": str(source),
            "source_format": "matlab-legacy",
            "sampling_rate_hz": sampling_rate,
            "duration_inferred": not has_declared_duration,
        },
    )


def read_spike_csv(path: str | Path) -> SpikeRecording:
    source = Path(path)
    table = pd.read_csv(source)
    mapping = infer_event_columns(list(table.columns))
    table = table.rename(columns={source_name: target for target, source_name in mapping.items()})
    table = table.dropna(subset=["channel_id", "timestamp_s"]).copy()
    channel_ids = [str(value) for value in pd.unique(table["channel_id"])]
    spikes = [
        table.loc[table["channel_id"].astype(str) == channel, "timestamp_s"].to_numpy(float)
        for channel in channel_ids
    ]
    amplitudes = None
    if "amplitude_uv" in table.columns:
        amplitudes = [
            table.loc[table["channel_id"].astype(str) == channel, "amplitude_uv"].to_numpy(float)
            for channel in channel_ids
        ]
    declared = table["duration_s"].dropna() if "duration_s" in table.columns else pd.Series(dtype=float)
    duration = float(declared.iloc[0]) if not declared.empty else max(float(table["timestamp_s"].max()), 0.0) + 1e-6
    recording_values = table["recording_id"].dropna() if "recording_id" in table.columns else pd.Series(dtype=str)
    recording_id = str(recording_values.iloc[0]) if not recording_values.empty else source.stem
    return SpikeRecording(recording_id, spikes, duration, channel_ids, amplitudes, {"source_path": str(source), "source_format": "csv"})


def _with_duration_override(recording: SpikeRecording, duration_s: float | None) -> SpikeRecording:
    if duration_s is None:
        return recording
    metadata = dict(recording.metadata)
    metadata.update(
        {
            "original_duration_s": float(recording.duration_s),
            "duration_override_s": float(duration_s),
            "duration_inferred": False,
        }
    )
    return SpikeRecording(
        recording_id=recording.recording_id,
        spike_times=recording.spike_times,
        duration_s=float(duration_s),
        channel_ids=recording.channel_ids,
        amplitudes=recording.amplitudes,
        metadata=metadata,
    )


def read_recording(path: str | Path, duration_s: float | None = None) -> SpikeRecording:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".csv":
        return _with_duration_override(read_spike_csv(source), duration_s)
    if suffix in {".mat", ".h5", ".hdf5"}:
        try:
            recording = read_hdf5_mat(source)
        except OSError:
            recording = read_legacy_mat(source)
        return _with_duration_override(recording, duration_s)
    raise ValueError(f"Unsupported recording format: {source.suffix}")
