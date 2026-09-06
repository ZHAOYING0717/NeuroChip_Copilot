from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.signal import welch

from .schema import SpikeRecording


def recording_stability(recording: SpikeRecording, n_segments: int = 6) -> tuple[dict[str, float | str], pd.DataFrame]:
    """Quantify stationarity from detected-event rates over equal time segments."""

    segment_count = int(np.clip(n_segments, 3, max(3, np.floor(recording.duration_s))))
    edges = np.linspace(0.0, recording.duration_s, segment_count + 1)
    segment_duration = recording.duration_s / segment_count
    per_channel = np.stack([np.histogram(times, bins=edges)[0] for times in recording.spike_times]).astype(float)
    channel_rates = per_channel / segment_duration
    population_rate = channel_rates.mean(axis=0) if channel_rates.size else np.zeros(segment_count)
    mean_rate = float(np.mean(population_rate))
    stability_cv = float(np.std(population_rate) / mean_rate) if mean_rate > 0 else 0.0
    pseudocount_hz = 1.0 / max(segment_duration * max(recording.n_channels, 1), 1.0)
    decay_log2_ratio = float(np.log2((population_rate[-1] + pseudocount_hz) / (population_rate[0] + pseudocount_hz)))
    positions = np.linspace(-0.5, 0.5, segment_count)
    normalized_slope = (
        float(np.polyfit(positions, population_rate, 1)[0] / mean_rate)
        if mean_rate > 0 and segment_count >= 3
        else 0.0
    )
    if abs(decay_log2_ratio) <= 1.0 and stability_cv <= 0.75:
        grade = "pass"
    elif abs(decay_log2_ratio) <= 2.0 and stability_cv <= 1.5:
        grade = "review"
    else:
        grade = "fail"

    rows: list[dict[str, Any]] = []
    for channel_id, rates in zip(recording.channel_ids, channel_rates, strict=True):
        channel_mean = float(np.mean(rates))
        rows.append(
            {
                "channel": channel_id,
                "segment_rate_mean_hz": channel_mean,
                "segment_rate_cv": float(np.std(rates) / channel_mean) if channel_mean > 0 else 0.0,
                "first_segment_rate_hz": float(rates[0]),
                "last_segment_rate_hz": float(rates[-1]),
            }
        )
    summary: dict[str, float | str] = {
        "stability_grade": grade,
        "stability_segments": float(segment_count),
        "firing_stability_cv": stability_cv,
        "activity_decay_log2_ratio": decay_log2_ratio,
        "activity_trend_normalized_slope": normalized_slope,
    }
    return summary, pd.DataFrame(rows)


def assess_event_quality(recording: SpikeRecording, active_rate_per_min: float = 5.0) -> tuple[dict[str, Any], pd.DataFrame]:
    """Assess detected spike events without claiming raw-waveform quality."""

    stability, channel_stability = recording_stability(recording)
    rows: list[dict[str, Any]] = []
    for channel_id, times in zip(recording.channel_ids, recording.spike_times, strict=True):
        in_range = times[(times >= 0) & (times < recording.duration_s)]
        intervals = np.diff(in_range)
        rate_hz = in_range.size / recording.duration_s
        rows.append(
            {
                "channel": channel_id,
                "n_spikes": int(in_range.size),
                "firing_rate_hz": rate_hz,
                "active": bool(rate_hz * 60 >= active_rate_per_min),
                "out_of_range_fraction": float(1 - in_range.size / max(times.size, 1)),
                "duplicate_fraction": float(np.mean(intervals == 0)) if intervals.size else 0.0,
                "refractory_violation_fraction": float(np.mean(intervals < 0.001)) if intervals.size else 0.0,
                "median_isi_s": float(np.median(intervals)) if intervals.size else np.nan,
            }
        )
    channels = pd.DataFrame(rows).merge(channel_stability, on="channel", how="left")
    active_fraction = float(channels["active"].mean()) if not channels.empty else 0.0
    rates = channels["firing_rate_hz"].to_numpy(float) if not channels.empty else np.array([])
    dominance = float(rates.max() / rates.sum()) if rates.size and rates.sum() > 0 else 1.0
    positive_log_rates = np.log1p(rates[rates > 0])
    center = float(np.median(positive_log_rates)) if positive_log_rates.size else 0.0
    mad = float(np.median(np.abs(positive_log_rates - center))) if positive_log_rates.size else 0.0
    robust_scale = max(1.4826 * mad, 0.15)

    if not channels.empty:
        log_rate_z = (np.log1p(channels["firing_rate_hz"].to_numpy(float)) - center) / robust_scale
        invalid = (
            (channels["out_of_range_fraction"] > 0.05)
            | (channels["duplicate_fraction"] > 0.05)
            | (channels["refractory_violation_fraction"] > 0.10)
        )
        noisy_proxy = (log_rate_z > 4.0) | (channels["segment_rate_cv"] > 1.5)
        status = np.full(len(channels), "good", dtype=object)
        status[~channels["active"].to_numpy(bool)] = "inactive_candidate"
        status[noisy_proxy.to_numpy(bool)] = "review_event_proxy"
        status[invalid.to_numpy(bool)] = "excluded_event_invalid"
        channels["event_rate_robust_z"] = log_rate_z
        channels["status"] = status
        channels["recommended_exclusion"] = invalid.to_numpy(bool)

    score = 100.0
    score -= 35.0 * max(0.0, 0.5 - active_fraction) / 0.5
    score -= 25.0 * max(0.0, dominance - 0.6) / 0.4
    score -= 20.0 * min(1.0, float(channels["out_of_range_fraction"].mean()) * 20) if not channels.empty else 20.0
    score -= 20.0 * min(1.0, float(channels["refractory_violation_fraction"].mean()) * 10) if not channels.empty else 20.0
    if stability["stability_grade"] == "review":
        score -= 7.5
    elif stability["stability_grade"] == "fail":
        score -= 15.0
    score = float(np.clip(score, 0, 100))
    grade = "pass" if score >= 75 else "review" if score >= 50 else "fail"
    summary = {
        "scope": "event_level",
        "recording_id": recording.recording_id,
        "quality_score": score,
        "quality_grade": grade,
        "n_channels": recording.n_channels,
        "n_spikes": recording.n_spikes,
        "active_channel_fraction": active_fraction,
        "dominant_channel_fraction": dominance,
        "inactive_channel_candidates": int((channels["status"] == "inactive_candidate").sum()) if "status" in channels else 0,
        "review_channel_candidates": int((channels["status"] == "review_event_proxy").sum()) if "status" in channels else 0,
        "excluded_channel_candidates": int(channels["recommended_exclusion"].sum()) if "recommended_exclusion" in channels else 0,
        "raw_voltage_qc_available": False,
        **stability,
        "limitations": (
            "Inactive channels cannot be distinguished from dead electrodes without raw voltage or impedance. "
            "Raw-voltage noise, saturation, line noise, baseline drift, and waveform morphology are not assessed "
            "from spike-time-only inputs."
        ),
    }
    return summary, channels


def assess_raw_voltage_quality(
    voltage_uv: np.ndarray,
    sampling_rate_hz: float,
    channel_ids: list[str] | None = None,
    channel_axis: int = 0,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Assess raw-voltage noise, drift, line interference, and saturation in microvolts."""

    if not np.isfinite(sampling_rate_hz) or sampling_rate_hz <= 0:
        raise ValueError("sampling_rate_hz must be positive")
    values = np.asarray(voltage_uv, dtype=float)
    if values.ndim != 2:
        raise ValueError("voltage_uv must be a two-dimensional channel-by-sample array")
    if channel_axis not in (0, 1):
        raise ValueError("channel_axis must be 0 or 1")
    if channel_axis == 1:
        values = values.T
    n_channels, n_samples = values.shape
    if n_channels == 0 or n_samples < 16:
        raise ValueError("raw-voltage QC requires at least one channel and 16 samples")
    identifiers = channel_ids or [f"ch_{index + 1}" for index in range(n_channels)]
    if len(identifiers) != n_channels:
        raise ValueError("channel_ids length does not match voltage channels")

    segment_count = min(10, max(2, n_samples // 8))
    segments = np.array_split(np.arange(n_samples), segment_count)
    rows: list[dict[str, Any]] = []
    for channel_id, trace in zip(identifiers, values, strict=True):
        finite = trace[np.isfinite(trace)]
        if finite.size < 16:
            rows.append(
                {
                    "channel": channel_id,
                    "noise_rms_uv": np.nan,
                    "robust_noise_sigma_uv": np.nan,
                    "baseline_drift_uv": np.nan,
                    "line_noise_ratio": np.nan,
                    "saturation_fraction": 1.0,
                }
            )
            continue
        baselines = np.asarray([np.nanmedian(trace[index]) for index in segments], dtype=float)
        detrended = np.concatenate([trace[index] - np.nanmedian(trace[index]) for index in segments])
        detrended = detrended[np.isfinite(detrended)]
        robust_sigma = float(1.4826 * np.median(np.abs(detrended - np.median(detrended))))
        rms = float(np.sqrt(np.mean(np.square(detrended))))
        drift = float(np.max(baselines) - np.min(baselines))
        low, high = np.min(finite), np.max(finite)
        saturation = float(np.mean((finite == low) | (finite == high))) if high > low else 1.0
        spectrum_samples = detrended[: min(detrended.size, int(sampling_rate_hz * 60))]
        if spectrum_samples.size >= 256:
            frequencies, power = welch(
                spectrum_samples,
                fs=sampling_rate_hz,
                nperseg=min(4096, spectrum_samples.size),
            )
            total_mask = (frequencies >= 5.0) & (frequencies <= min(500.0, sampling_rate_hz / 2.0))
            total_power = float(np.trapezoid(power[total_mask], frequencies[total_mask])) if np.any(total_mask) else 0.0
            line_powers = []
            for line_hz in (50.0, 60.0):
                mask = (frequencies >= line_hz - 1.0) & (frequencies <= line_hz + 1.0)
                line_powers.append(float(np.trapezoid(power[mask], frequencies[mask])) if np.any(mask) else 0.0)
            line_ratio = max(line_powers) / total_power if total_power > 0 else 0.0
        else:
            line_ratio = np.nan
        rows.append(
            {
                "channel": channel_id,
                "noise_rms_uv": rms,
                "robust_noise_sigma_uv": robust_sigma,
                "baseline_drift_uv": drift,
                "line_noise_ratio": line_ratio,
                "saturation_fraction": saturation,
            }
        )

    channels = pd.DataFrame(rows)
    noise = channels["robust_noise_sigma_uv"].to_numpy(float)
    finite_noise = noise[np.isfinite(noise)]
    median_noise = float(np.median(finite_noise)) if finite_noise.size else 0.0
    if median_noise <= 1e-12:
        positive_noise = finite_noise[finite_noise > 0]
        median_noise = float(np.median(positive_noise)) if positive_noise.size else 0.0
    dead = (~np.isfinite(noise)) | (noise <= max(median_noise * 0.1, 1e-12))
    noisy = noise >= max(median_noise * 5.0, 1e-12)
    drifted = channels["baseline_drift_uv"].to_numpy(float) > np.maximum(noise * 10.0, median_noise * 10.0)
    saturated = channels["saturation_fraction"].to_numpy(float) > 0.01
    line_noisy = channels["line_noise_ratio"].fillna(0).to_numpy(float) > 0.20
    status = np.full(n_channels, "good", dtype=object)
    status[noisy | drifted | line_noisy] = "noisy_or_drifting"
    status[dead | saturated] = "excluded"
    channels["status"] = status
    channels["recommended_exclusion"] = dead | saturated
    summary = {
        "scope": "raw_voltage",
        "raw_voltage_qc_available": True,
        "sampling_rate_hz": float(sampling_rate_hz),
        "n_channels": int(n_channels),
        "n_samples": int(n_samples),
        "median_robust_noise_sigma_uv": median_noise,
        "good_channels": int(np.sum(status == "good")),
        "noisy_or_drifting_channels": int(np.sum(status == "noisy_or_drifting")),
        "excluded_channels": int(np.sum(status == "excluded")),
        "method_note": (
            "Thresholds are explicit engineering defaults and require local blank-well/impedance calibration "
            "before confirmatory use."
        ),
    }
    return summary, channels
