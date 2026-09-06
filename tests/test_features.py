import numpy as np

from neurochip.avalanche import avalanche_features
from neurochip.connectivity import advanced_connectivity_matrices, connectivity_features
from neurochip.features import extract_features, spike_time_tiling_coefficient
from neurochip.qc import assess_event_quality, assess_raw_voltage_quality
from neurochip.schema import SpikeRecording


def synthetic_recording() -> SpikeRecording:
    base = np.arange(0.1, 10.0, 0.25)
    return SpikeRecording(
        "synthetic",
        [base, base + 0.002, np.arange(0.2, 10.0, 0.5), np.arange(0.3, 10.0, 0.7)],
        10.0,
    )


def test_sttc_detects_synchronous_trains():
    base = np.arange(0.1, 10.0, 0.25)
    synchronous = spike_time_tiling_coefficient(base, base + 0.002, 10.0)
    unrelated = spike_time_tiling_coefficient(base, np.arange(0.21, 10.0, 0.43), 10.0)
    assert synchronous > 0.9
    assert synchronous > unrelated


def test_feature_extraction_is_finite():
    features = extract_features(synthetic_recording())
    numeric = [value for key, value in features.items() if key != "recording_id"]
    assert all(np.isfinite(value) for value in numeric)
    assert features["sttc_mean"] > 0
    assert 0 <= features["network_density"] <= 1


def test_event_qc_declares_scope():
    summary, channels = assess_event_quality(synthetic_recording())
    assert summary["scope"] == "event_level"
    assert len(channels) == 4
    assert 0 <= summary["quality_score"] <= 100


def test_out_of_range_events_are_audited_but_excluded_from_features():
    recording = SpikeRecording("bounded", [np.array([1.0, 2.0, 10.0])], 10.0)
    features = extract_features(recording)
    summary, channels = assess_event_quality(recording)
    assert features["input_total_spikes"] == 3
    assert features["total_spikes"] == 2
    assert features["excluded_out_of_range_spikes"] == 1
    assert features["firing_rate_mean_hz"] == 0.2
    assert np.isclose(channels.loc[0, "out_of_range_fraction"], 1 / 3)
    assert summary["n_spikes"] == 3


def test_avalanche_branching_ratio_detects_expanding_activity():
    recording = SpikeRecording(
        "avalanche",
        [
            np.array([0.01]),
            np.array([0.11, 0.21]),
            np.array([0.11, 0.21]),
            np.array([0.21]),
        ],
        1.0,
    )
    result = avalanche_features(recording, bin_s=0.1)
    assert result["avalanche_count"] == 1
    assert result["avalanche_size_max"] == 6
    assert result["avalanche_branching_ratio"] > 1


def test_directed_connectivity_tracks_delayed_source():
    source = np.arange(0.1, 9.0, 0.4)
    target = source + 0.05
    recording = SpikeRecording("directed", [source, target, np.arange(0.3, 9.0, 0.73)], 10.0)
    matrices = advanced_connectivity_matrices(recording, bin_s=0.05)
    summary = connectivity_features(recording, bin_s=0.05)
    assert matrices.transfer_entropy_bits[0, 1] > matrices.transfer_entropy_bits[1, 0]
    assert np.allclose(matrices.mutual_information_bits, matrices.mutual_information_bits.T)
    assert summary["granger_log_variance_ratio_max"] > 0


def test_raw_voltage_qc_separates_dead_and_noisy_channels():
    rng = np.random.default_rng(12)
    good = rng.normal(0, 5, 5000)
    dead = np.zeros(5000)
    noisy = rng.normal(0, 80, 5000) + np.linspace(0, 500, 5000)
    summary, channels = assess_raw_voltage_quality(np.vstack([good, dead, noisy]), 1000.0)
    assert summary["raw_voltage_qc_available"] is True
    assert channels.loc[1, "status"] == "excluded"
    assert channels.loc[2, "status"] == "noisy_or_drifting"
