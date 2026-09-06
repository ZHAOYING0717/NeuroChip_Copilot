from __future__ import annotations

from typing import Any

import numpy as np

from .schema import SpikeRecording


def recording_to_cache_payload(recording: SpikeRecording) -> dict[str, Any]:
    """Convert a recording to a cache-stable structure without custom classes."""
    return {
        "recording_id": recording.recording_id,
        "spike_times": [np.asarray(times, dtype=float).copy() for times in recording.spike_times],
        "duration_s": float(recording.duration_s),
        "channel_ids": list(recording.channel_ids),
        "amplitudes": (
            None
            if recording.amplitudes is None
            else [np.asarray(values, dtype=float).copy() for values in recording.amplitudes]
        ),
        "metadata": dict(recording.metadata),
    }


def recording_from_cache_payload(payload: dict[str, Any]) -> SpikeRecording:
    """Restore a recording after Streamlit has copied a cached data payload."""
    return SpikeRecording(
        recording_id=str(payload["recording_id"]),
        spike_times=list(payload["spike_times"]),
        duration_s=float(payload["duration_s"]),
        channel_ids=[str(value) for value in payload["channel_ids"]],
        amplitudes=payload["amplitudes"],
        metadata=dict(payload["metadata"]),
    )
