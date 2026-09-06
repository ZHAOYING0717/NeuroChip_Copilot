from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .schema import SpikeRecording


@dataclass(frozen=True)
class ConnectivityMatrices:
    channel_ids: list[str]
    mutual_information_bits: np.ndarray
    transfer_entropy_bits: np.ndarray
    granger_log_variance_ratio: np.ndarray


def _discrete_information(x: np.ndarray, y: np.ndarray) -> float:
    joint = np.bincount(x.astype(np.int8) * 2 + y.astype(np.int8), minlength=4).reshape(2, 2).astype(float)
    joint /= max(joint.sum(), 1.0)
    px = joint.sum(axis=1, keepdims=True)
    py = joint.sum(axis=0, keepdims=True)
    expected = px @ py
    mask = (joint > 0) & (expected > 0)
    return float(np.sum(joint[mask] * np.log2(joint[mask] / expected[mask])))


def _transfer_entropy(source: np.ndarray, target: np.ndarray) -> float:
    if source.size < 3 or target.size != source.size:
        return 0.0
    source_past = source[:-1].astype(np.int8)
    target_past = target[:-1].astype(np.int8)
    target_now = target[1:].astype(np.int8)
    state = target_now + 2 * target_past + 4 * source_past
    joint = np.bincount(state, minlength=8).reshape(2, 2, 2).astype(float)
    joint /= max(joint.sum(), 1.0)
    p_target_past_source = joint.sum(axis=0)
    p_target_now_past = joint.sum(axis=2)
    p_target_past = joint.sum(axis=(0, 2))
    value = 0.0
    for now in (0, 1):
        for past in (0, 1):
            for source_value in (0, 1):
                probability = joint[now, past, source_value]
                denominator_joint = p_target_past_source[past, source_value]
                denominator_past = p_target_past[past]
                if probability <= 0 or denominator_joint <= 0 or denominator_past <= 0:
                    continue
                conditioned_source = probability / denominator_joint
                conditioned_past = p_target_now_past[now, past] / denominator_past
                if conditioned_past > 0:
                    value += probability * np.log2(conditioned_source / conditioned_past)
    return float(max(value, 0.0))


def _granger_score(source: np.ndarray, target: np.ndarray) -> float:
    if source.size < 5 or target.size != source.size:
        return 0.0
    x = source[:-1].astype(float)
    y_lag = target[:-1].astype(float)
    y_now = target[1:].astype(float)
    design = np.column_stack((np.ones(y_lag.size), y_lag))
    beta_y, *_ = np.linalg.lstsq(design, y_now, rcond=None)
    beta_x, *_ = np.linalg.lstsq(design, x, rcond=None)
    residual_y = y_now - design @ beta_y
    residual_x = x - design @ beta_x
    denominator = float(np.linalg.norm(residual_y) * np.linalg.norm(residual_x))
    if denominator <= 1e-12:
        return 0.0
    partial_r = float(np.clip(np.dot(residual_y, residual_x) / denominator, -0.999999, 0.999999))
    return float(-np.log(max(1.0 - partial_r * partial_r, 1e-12)))


def advanced_connectivity_matrices(
    recording: SpikeRecording,
    bin_s: float = 0.05,
    max_channels: int = 24,
) -> ConnectivityMatrices:
    """Estimate pairwise association and directed predictive information from binned spikes."""

    if not np.isfinite(bin_s) or bin_s <= 0:
        raise ValueError("bin_s must be positive")
    counts = np.asarray([times[(times >= 0) & (times < recording.duration_s)].size for times in recording.spike_times])
    selected = np.argsort(counts)[::-1][: min(max_channels, recording.n_channels)]
    selected = np.sort(selected)
    edges = np.arange(0.0, recording.duration_s + bin_s, bin_s)
    if edges[-1] < recording.duration_s:
        edges = np.append(edges, recording.duration_s)
    if selected.size == 0:
        empty = np.zeros((0, 0), dtype=float)
        return ConnectivityMatrices([], empty, empty.copy(), empty.copy())
    binned_counts = np.stack([np.histogram(recording.spike_times[index], bins=edges)[0] for index in selected])
    binary = binned_counts > 0
    n_channels = selected.size
    mutual_information = np.zeros((n_channels, n_channels), dtype=float)
    transfer_entropy = np.zeros((n_channels, n_channels), dtype=float)
    granger = np.zeros((n_channels, n_channels), dtype=float)
    surrogate_shift = max(1, binary.shape[1] // 3)
    for source in range(n_channels):
        for target in range(source + 1, n_channels):
            raw_mi = _discrete_information(binary[source], binary[target])
            shift = surrogate_shift + source + target
            surrogate_mi = 0.5 * (
                _discrete_information(np.roll(binary[source], shift), binary[target])
                + _discrete_information(binary[source], np.roll(binary[target], shift))
            )
            corrected_mi = max(raw_mi - surrogate_mi, 0.0)
            mutual_information[source, target] = corrected_mi
            mutual_information[target, source] = corrected_mi
    for source in range(n_channels):
        for target in range(n_channels):
            if source == target:
                continue
            raw_te = _transfer_entropy(binary[source], binary[target])
            surrogate_te = _transfer_entropy(np.roll(binary[source], surrogate_shift + source), binary[target])
            transfer_entropy[source, target] = max(raw_te - surrogate_te, 0.0)
            granger[source, target] = _granger_score(binned_counts[source], binned_counts[target])
    return ConnectivityMatrices(
        channel_ids=[recording.channel_ids[index] for index in selected],
        mutual_information_bits=mutual_information,
        transfer_entropy_bits=transfer_entropy,
        granger_log_variance_ratio=granger,
    )


def connectivity_features(
    recording: SpikeRecording,
    bin_s: float = 0.05,
    max_channels: int = 24,
) -> dict[str, float]:
    matrices = advanced_connectivity_matrices(recording, bin_s=bin_s, max_channels=max_channels)
    size = len(matrices.channel_ids)
    if size < 2:
        off_diagonal = np.zeros((size, size), dtype=bool)
    else:
        off_diagonal = ~np.eye(size, dtype=bool)

    def values(matrix: np.ndarray) -> np.ndarray:
        return matrix[off_diagonal] if np.any(off_diagonal) else np.array([], dtype=float)

    mi = values(matrices.mutual_information_bits)
    te = values(matrices.transfer_entropy_bits)
    gc = values(matrices.granger_log_variance_ratio)
    te_asymmetry = []
    for left in range(size):
        for right in range(left + 1, size):
            te_asymmetry.append(abs(matrices.transfer_entropy_bits[left, right] - matrices.transfer_entropy_bits[right, left]))
    return {
        "connectivity_bin_s": float(bin_s),
        "connectivity_channels_used": float(size),
        "mutual_information_mean_bits": float(np.mean(mi)) if mi.size else 0.0,
        "mutual_information_max_bits": float(np.max(mi)) if mi.size else 0.0,
        "transfer_entropy_mean_bits": float(np.mean(te)) if te.size else 0.0,
        "transfer_entropy_max_bits": float(np.max(te)) if te.size else 0.0,
        "transfer_entropy_asymmetry_mean_bits": float(np.mean(te_asymmetry)) if te_asymmetry else 0.0,
        "granger_log_variance_ratio_mean": float(np.mean(gc)) if gc.size else 0.0,
        "granger_log_variance_ratio_max": float(np.max(gc)) if gc.size else 0.0,
    }
