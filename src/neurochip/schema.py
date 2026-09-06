from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(slots=True)
class SpikeRecording:
    """A device-neutral multichannel extracellular spike recording."""

    recording_id: str
    spike_times: list[np.ndarray]
    duration_s: float
    channel_ids: list[str] = field(default_factory=list)
    amplitudes: list[np.ndarray] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not np.isfinite(self.duration_s) or self.duration_s <= 0:
            raise ValueError("duration_s must be a positive finite value")
        self.spike_times = [self._clean_times(times) for times in self.spike_times]
        if not self.channel_ids:
            self.channel_ids = [f"ch_{index + 1}" for index in range(len(self.spike_times))]
        if len(self.channel_ids) != len(self.spike_times):
            raise ValueError("channel_ids and spike_times must have the same length")
        if self.amplitudes is not None:
            self.amplitudes = [np.asarray(values, dtype=float).ravel() for values in self.amplitudes]
            if len(self.amplitudes) != len(self.spike_times):
                raise ValueError("amplitudes and spike_times must have the same length")

    @staticmethod
    def _clean_times(values: np.ndarray) -> np.ndarray:
        times = np.asarray(values, dtype=float).ravel()
        return np.sort(times[np.isfinite(times)])

    @property
    def n_channels(self) -> int:
        return len(self.spike_times)

    @property
    def n_spikes(self) -> int:
        return int(sum(values.size for values in self.spike_times))

    def window(self, start_s: float, end_s: float, suffix: str | None = None) -> "SpikeRecording":
        if start_s < 0 or end_s <= start_s or end_s > self.duration_s + 1e-9:
            raise ValueError("window bounds are outside the recording")
        spikes: list[np.ndarray] = []
        amplitudes: list[np.ndarray] | None = [] if self.amplitudes is not None else None
        for index, times in enumerate(self.spike_times):
            mask = (times >= start_s) & (times < end_s)
            spikes.append(times[mask] - start_s)
            if amplitudes is not None and self.amplitudes is not None:
                channel_amplitudes = self.amplitudes[index]
                amplitudes.append(channel_amplitudes[mask] if channel_amplitudes.size == times.size else np.array([]))
        label = suffix or f"{start_s:g}-{end_s:g}s"
        metadata = dict(self.metadata)
        metadata.update({"parent_recording_id": self.recording_id, "window_start_s": start_s, "window_end_s": end_s})
        return SpikeRecording(
            recording_id=f"{self.recording_id}__{label}",
            spike_times=spikes,
            duration_s=end_s - start_s,
            channel_ids=list(self.channel_ids),
            amplitudes=amplitudes,
            metadata=metadata,
        )

