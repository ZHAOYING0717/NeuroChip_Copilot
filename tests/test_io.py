from pathlib import Path

import numpy as np

from neurochip.io import read_recording


def test_read_spike_csv(tmp_path: Path):
    source = tmp_path / "events.csv"
    source.write_text("channel,time_s,duration_s\nA,0.1,2\nA,0.2,2\nB,0.3,2\n", encoding="utf-8")
    recording = read_recording(source)
    assert recording.n_channels == 2
    assert recording.n_spikes == 3
    assert recording.duration_s == 2
    np.testing.assert_allclose(recording.spike_times[0], [0.1, 0.2])


def test_read_neurochip_standard_csv(tmp_path: Path):
    source = tmp_path / "standard.csv"
    source.write_text(
        "recording_id,timestamp_s,channel_id,amplitude_uv,duration_s\n"
        "sample,0.1,A,12,2\n"
        "sample,0.2,B,15,2\n",
        encoding="utf-8",
    )
    recording = read_recording(source)
    assert recording.recording_id == "sample"
    assert recording.channel_ids == ["A", "B"]
    assert recording.amplitudes is not None


def test_duration_override_preserves_events_for_qc(tmp_path: Path):
    source = tmp_path / "events.csv"
    source.write_text("channel,time_s\nA,1.0\nA,180.1\n", encoding="utf-8")
    recording = read_recording(source, duration_s=180.0)
    assert recording.duration_s == 180.0
    assert recording.n_spikes == 2
    assert recording.metadata["duration_override_s"] == 180.0
    assert recording.metadata["original_duration_s"] > 180.0


def test_read_public_hdf5_mat_when_available():
    source = Path(__file__).resolve().parents[1] / "data" / "interim" / "zenodo_20286251" / "individual" / "fs363-org0.mat"
    if not source.exists():
        return
    recording = read_recording(source)
    assert recording.n_channels == 8
    assert recording.duration_s == 400
    assert recording.n_spikes > 0


def test_matlab_empty_spike_train_when_available():
    source = Path(__file__).resolve().parents[1] / "data" / "interim" / "zenodo_20286251" / "individual" / "fs371-org3.mat"
    if not source.exists():
        return
    recording = read_recording(source)
    assert recording.spike_times[2].size == 0


def test_read_kilosort_units_when_available():
    source = Path(__file__).resolve().parents[1] / "data" / "interim" / "zenodo_6578989" / "kilosort2" / "drug" / "kilosort2" / "control_2950.mat"
    if not source.exists():
        return
    recording = read_recording(source)
    assert recording.n_channels == 18
    assert recording.duration_s == 180
    assert recording.metadata["sampling_rate_hz"] == 20000
    assert max(max(times) for times in recording.spike_times if times.size) < 180


def test_kilosort_protocol_duration_override_when_available():
    source = Path(__file__).resolve().parents[1] / "data" / "interim" / "zenodo_6578989" / "kilosort2" / "drug" / "kilosort2" / "diazepam10uM_2953.mat"
    if not source.exists():
        return
    recording = read_recording(source, duration_s=180.0)
    assert recording.duration_s == 180.0
    assert sum(np.sum(times >= 180.0) for times in recording.spike_times) == 29
