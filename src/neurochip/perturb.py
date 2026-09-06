from __future__ import annotations

import numpy as np

from .schema import SpikeRecording


def perturb_recording(recording: SpikeRecording, kind: str, seed: int) -> SpikeRecording:
    """Create controlled event-level perturbations for robustness evaluation."""

    rng = np.random.default_rng(seed)
    spikes = [times.copy() for times in recording.spike_times]
    if kind == "channel_dropout":
        count = max(1, int(np.ceil(recording.n_channels * 0.5)))
        dropped = rng.choice(recording.n_channels, size=count, replace=False)
        for channel in dropped:
            spikes[int(channel)] = np.array([], dtype=float)
    elif kind == "hyperactivity":
        for channel, times in enumerate(spikes):
            baseline_rate = max(times.size / recording.duration_s, 0.1)
            count = rng.poisson(baseline_rate * recording.duration_s * 3.0)
            spikes[channel] = np.sort(np.r_[times, rng.uniform(0, recording.duration_s, count)])
    elif kind == "hypersynchrony":
        centers = np.arange(5.0, recording.duration_s, 10.0)
        for channel, times in enumerate(spikes):
            injected = np.concatenate(
                [center + rng.normal(0, 0.003, size=8) for center in centers]
            ) if centers.size else np.array([], dtype=float)
            injected = injected[(injected >= 0) & (injected <= recording.duration_s)]
            spikes[channel] = np.sort(np.r_[times, injected])
    else:
        raise ValueError(f"Unknown perturbation: {kind}")
    metadata = dict(recording.metadata)
    metadata["perturbation"] = kind
    return SpikeRecording(
        recording_id=f"{recording.recording_id}__{kind}",
        spike_times=spikes,
        duration_s=recording.duration_s,
        channel_ids=list(recording.channel_ids),
        metadata=metadata,
    )

