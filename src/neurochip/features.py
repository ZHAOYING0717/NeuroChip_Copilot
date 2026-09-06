from __future__ import annotations

from itertools import combinations

import networkx as nx
import numpy as np

from .avalanche import avalanche_features
from .connectivity import connectivity_features
from .qc import assess_event_quality
from .schema import SpikeRecording


def _safe_stat(values: np.ndarray, function, default: float = 0.0) -> float:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    return float(function(finite)) if finite.size else default


def _covered_fraction(times: np.ndarray, delta_s: float, duration_s: float) -> float:
    if times.size == 0:
        return 0.0
    starts = np.maximum(0.0, times - delta_s)
    ends = np.minimum(duration_s, times + delta_s)
    order = np.argsort(starts)
    starts, ends = starts[order], ends[order]
    total = 0.0
    current_start, current_end = starts[0], ends[0]
    for start, end in zip(starts[1:], ends[1:], strict=True):
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            total += current_end - current_start
            current_start, current_end = start, end
    total += current_end - current_start
    return float(total / duration_s)


def _coincident_fraction(source: np.ndarray, target: np.ndarray, delta_s: float) -> float:
    if source.size == 0 or target.size == 0:
        return 0.0
    positions = np.searchsorted(target, source)
    left = np.abs(source - target[np.clip(positions - 1, 0, target.size - 1)])
    right = np.abs(source - target[np.clip(positions, 0, target.size - 1)])
    return float(np.mean(np.minimum(left, right) <= delta_s))


def spike_time_tiling_coefficient(a: np.ndarray, b: np.ndarray, duration_s: float, delta_s: float = 0.02) -> float:
    if a.size == 0 or b.size == 0:
        return 0.0
    pa = _coincident_fraction(a, b, delta_s)
    pb = _coincident_fraction(b, a, delta_s)
    ta = _covered_fraction(a, delta_s, duration_s)
    tb = _covered_fraction(b, delta_s, duration_s)
    term_a = (pa - tb) / (1 - pa * tb) if not np.isclose(1 - pa * tb, 0) else 0.0
    term_b = (pb - ta) / (1 - pb * ta) if not np.isclose(1 - pb * ta, 0) else 0.0
    return float(np.clip(0.5 * (term_a + term_b), -1, 1))


def _network_bursts(recording: SpikeRecording, bin_s: float = 0.05) -> dict[str, float]:
    edges = np.arange(0, recording.duration_s + bin_s, bin_s)
    if edges.size < 3:
        return {"network_burst_rate_per_min": 0.0, "network_burst_mean_duration_s": 0.0, "network_burst_participation": 0.0}
    per_channel = np.stack([np.histogram(times, bins=edges)[0] for times in recording.spike_times])
    population = per_channel.sum(axis=0)
    baseline = np.median(population)
    mad = np.median(np.abs(population - baseline))
    threshold = max(2.0, baseline + 4.0 * max(mad, 0.5))
    active = population >= threshold
    padded = np.r_[False, active, False]
    starts = np.flatnonzero(np.diff(padded.astype(int)) == 1)
    ends = np.flatnonzero(np.diff(padded.astype(int)) == -1)
    if starts.size == 0:
        return {"network_burst_rate_per_min": 0.0, "network_burst_mean_duration_s": 0.0, "network_burst_participation": 0.0}
    durations = (ends - starts) * bin_s
    participation = [np.mean(per_channel[:, start:end].sum(axis=1) > 0) for start, end in zip(starts, ends, strict=True)]
    return {
        "network_burst_rate_per_min": float(starts.size / recording.duration_s * 60),
        "network_burst_mean_duration_s": float(np.mean(durations)),
        "network_burst_participation": float(np.mean(participation)),
    }


def _population_entropy(recording: SpikeRecording, bin_s: float = 0.1) -> float:
    edges = np.arange(0, recording.duration_s + bin_s, bin_s)
    counts = sum((np.histogram(times, bins=edges)[0] for times in recording.spike_times), start=np.zeros(edges.size - 1, dtype=int))
    frequencies = np.bincount(counts)
    probabilities = frequencies[frequencies > 0] / frequencies.sum()
    entropy = -np.sum(probabilities * np.log2(probabilities))
    return float(entropy / np.log2(max(frequencies.size, 2)))


def extract_features(recording: SpikeRecording, sttc_delta_s: float = 0.02) -> dict[str, float | str]:
    qc, channel_qc = assess_event_quality(recording)
    valid_recording = recording.window(0.0, recording.duration_s, suffix="valid-events")
    rates = channel_qc["firing_rate_hz"].to_numpy(float)
    isi_cv: list[float] = []
    isi_median: list[float] = []
    for times in valid_recording.spike_times:
        intervals = np.diff(times)
        if intervals.size:
            isi_median.append(float(np.median(intervals)))
        if intervals.size > 1 and np.mean(intervals) > 0:
            isi_cv.append(float(np.std(intervals, ddof=1) / np.mean(intervals)))

    pair_values: list[float] = []
    graph = nx.Graph()
    graph.add_nodes_from(range(valid_recording.n_channels))
    for left, right in combinations(range(valid_recording.n_channels), 2):
        value = spike_time_tiling_coefficient(
            valid_recording.spike_times[left],
            valid_recording.spike_times[right],
            valid_recording.duration_s,
            sttc_delta_s,
        )
        pair_values.append(value)
        if value >= 0.1:
            graph.add_edge(left, right, weight=value)
    pairs = np.asarray(pair_values, dtype=float)
    clustering = float(nx.average_clustering(graph, weight="weight")) if graph.number_of_edges() else 0.0
    density = float(nx.density(graph)) if valid_recording.n_channels > 1 else 0.0

    features: dict[str, float | str] = {
        "recording_id": recording.recording_id,
        "duration_s": float(recording.duration_s),
        "n_channels": float(recording.n_channels),
        "input_total_spikes": float(recording.n_spikes),
        "excluded_out_of_range_spikes": float(recording.n_spikes - valid_recording.n_spikes),
        "total_spikes": float(valid_recording.n_spikes),
        "firing_rate_mean_hz": _safe_stat(rates, np.mean),
        "firing_rate_median_hz": _safe_stat(rates, np.median),
        "firing_rate_std_hz": _safe_stat(rates, np.std),
        "firing_rate_max_hz": _safe_stat(rates, np.max),
        "firing_rate_cv": float(np.std(rates) / np.mean(rates)) if rates.size and np.mean(rates) > 0 else 0.0,
        "active_channel_fraction": float(qc["active_channel_fraction"]),
        "dominant_channel_fraction": float(qc["dominant_channel_fraction"]),
        "refractory_violation_fraction": _safe_stat(channel_qc["refractory_violation_fraction"].to_numpy(), np.mean),
        "isi_median_s": _safe_stat(np.asarray(isi_median), np.median),
        "isi_cv_mean": _safe_stat(np.asarray(isi_cv), np.mean),
        "sttc_mean": _safe_stat(pairs, np.mean),
        "sttc_median": _safe_stat(pairs, np.median),
        "sttc_max": _safe_stat(pairs, np.max),
        "network_density": density,
        "network_clustering": clustering,
        "population_entropy": _population_entropy(valid_recording),
        "event_quality_score": float(qc["quality_score"]),
        "firing_stability_cv": float(qc["firing_stability_cv"]),
        "activity_decay_log2_ratio": float(qc["activity_decay_log2_ratio"]),
        "activity_trend_normalized_slope": float(qc["activity_trend_normalized_slope"]),
        "feature_schema_version": 2.0,
    }
    features.update(_network_bursts(valid_recording))
    features.update(avalanche_features(valid_recording))
    features.update(connectivity_features(valid_recording))
    if valid_recording.amplitudes is not None:
        amplitudes = (
            np.concatenate([values for values in valid_recording.amplitudes if values.size])
            if any(values.size for values in valid_recording.amplitudes)
            else np.array([])
        )
        features.update(
            {
                "amplitude_median": _safe_stat(amplitudes, np.median),
                "amplitude_iqr": float(np.subtract(*np.percentile(amplitudes, [75, 25]))) if amplitudes.size else 0.0,
            }
        )
    return features
