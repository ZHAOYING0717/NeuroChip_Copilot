from __future__ import annotations

import numpy as np

from .schema import SpikeRecording


def avalanche_features(
    recording: SpikeRecording,
    bin_s: float | None = None,
    minimum_bin_s: float = 0.001,
    maximum_bin_s: float = 0.100,
) -> dict[str, float]:
    """Summarize neuronal avalanches using consecutive non-empty population bins."""

    all_times = np.sort(
        np.concatenate([times[(times >= 0) & (times < recording.duration_s)] for times in recording.spike_times])
        if recording.n_spikes
        else np.array([], dtype=float)
    )
    if bin_s is None:
        positive_intervals = np.diff(all_times)
        positive_intervals = positive_intervals[positive_intervals > 0]
        adaptive = float(np.mean(positive_intervals)) if positive_intervals.size else maximum_bin_s
        bin_s = float(np.clip(adaptive, minimum_bin_s, maximum_bin_s))
    if not np.isfinite(bin_s) or bin_s <= 0:
        raise ValueError("bin_s must be positive")
    edges = np.arange(0.0, recording.duration_s + bin_s, bin_s)
    if edges[-1] < recording.duration_s:
        edges = np.append(edges, recording.duration_s)
    if edges.size < 3 or all_times.size == 0:
        return _empty_avalanche_features(bin_s)

    per_channel = np.stack([np.histogram(times, bins=edges)[0] for times in recording.spike_times])
    population = per_channel.sum(axis=0)
    active = population > 0
    padded = np.r_[False, active, False]
    starts = np.flatnonzero(np.diff(padded.astype(np.int8)) == 1)
    ends = np.flatnonzero(np.diff(padded.astype(np.int8)) == -1)
    if starts.size == 0:
        return _empty_avalanche_features(bin_s)

    sizes = np.asarray([population[start:end].sum() for start, end in zip(starts, ends, strict=True)], dtype=float)
    durations = (ends - starts).astype(float) * bin_s
    active_channels = (per_channel > 0).sum(axis=0).astype(float)
    ancestors: list[float] = []
    descendants: list[float] = []
    for start, end in zip(starts, ends, strict=True):
        if end - start < 2:
            continue
        ancestors.extend(active_channels[start : end - 1].tolist())
        descendants.extend(active_channels[start + 1 : end].tolist())
    denominator = float(np.sum(ancestors))
    branching_ratio = float(np.sum(descendants) / denominator) if denominator > 0 else 0.0
    return {
        "avalanche_bin_s": float(bin_s),
        "avalanche_count": float(starts.size),
        "avalanche_rate_per_min": float(starts.size / recording.duration_s * 60.0),
        "avalanche_size_mean": float(np.mean(sizes)),
        "avalanche_size_median": float(np.median(sizes)),
        "avalanche_size_max": float(np.max(sizes)),
        "avalanche_size_cv": float(np.std(sizes) / np.mean(sizes)) if np.mean(sizes) > 0 else 0.0,
        "avalanche_duration_mean_s": float(np.mean(durations)),
        "avalanche_branching_ratio": branching_ratio,
        "avalanche_criticality_distance": float(abs(branching_ratio - 1.0)),
    }


def _empty_avalanche_features(bin_s: float) -> dict[str, float]:
    return {
        "avalanche_bin_s": float(bin_s),
        "avalanche_count": 0.0,
        "avalanche_rate_per_min": 0.0,
        "avalanche_size_mean": 0.0,
        "avalanche_size_median": 0.0,
        "avalanche_size_max": 0.0,
        "avalanche_size_cv": 0.0,
        "avalanche_duration_mean_s": 0.0,
        "avalanche_branching_ratio": 0.0,
        "avalanche_criticality_distance": 1.0,
    }
