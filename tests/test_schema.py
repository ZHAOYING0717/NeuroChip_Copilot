import numpy as np
import pytest

from neurochip.schema import SpikeRecording


def test_recording_sorts_times_and_builds_channel_names():
    recording = SpikeRecording("sample", [np.array([0.4, 0.1, np.nan])], 1.0)
    assert recording.channel_ids == ["ch_1"]
    np.testing.assert_allclose(recording.spike_times[0], [0.1, 0.4])


def test_window_rebases_times():
    recording = SpikeRecording("sample", [np.array([0.2, 0.7, 1.2])], 2.0)
    window = recording.window(0.5, 1.5)
    np.testing.assert_allclose(window.spike_times[0], [0.2, 0.7])
    assert window.duration_s == 1.0


def test_invalid_duration_is_rejected():
    with pytest.raises(ValueError):
        SpikeRecording("bad", [np.array([])], 0)

