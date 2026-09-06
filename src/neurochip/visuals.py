from __future__ import annotations

from itertools import combinations

import numpy as np
import plotly.graph_objects as go

from .features import spike_time_tiling_coefficient
from .schema import SpikeRecording


COLORS = {
    "ink": "#1E2428",
    "muted": "#667078",
    "teal": "#168C86",
    "blue": "#3478B8",
    "red": "#C95148",
    "gold": "#D49B27",
    "line": "#D9DEE2",
}


def _valid_recording(recording: SpikeRecording) -> SpikeRecording:
    return recording.window(0.0, recording.duration_s, suffix="visualized-events")


def raster_figure(recording: SpikeRecording, max_points: int = 50000) -> go.Figure:
    recording = _valid_recording(recording)
    x_values: list[np.ndarray] = []
    y_values: list[np.ndarray] = []
    for index, times in enumerate(recording.spike_times):
        x_values.append(times)
        y_values.append(np.full(times.size, index))
    x = np.concatenate(x_values) if x_values else np.array([])
    y = np.concatenate(y_values) if y_values else np.array([])
    if x.size > max_points:
        keep = np.linspace(0, x.size - 1, max_points, dtype=int)
        x, y = x[keep], y[keep]
    figure = go.Figure(go.Scattergl(x=x, y=y, mode="markers", marker={"size": 2.5, "color": COLORS["ink"], "opacity": 0.55}))
    figure.update_layout(
        margin={"l": 48, "r": 16, "t": 18, "b": 42},
        height=330,
        xaxis_title="Time (s)",
        yaxis={"title": "Channel", "tickmode": "array", "tickvals": list(range(recording.n_channels)), "ticktext": recording.channel_ids},
        showlegend=False,
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    figure.update_xaxes(showgrid=True, gridcolor="#EDF0F2", zeroline=False)
    figure.update_yaxes(showgrid=False, zeroline=False)
    return figure


def channel_rate_figure(recording: SpikeRecording) -> go.Figure:
    recording = _valid_recording(recording)
    rates = [times.size / recording.duration_s for times in recording.spike_times]
    figure = go.Figure(go.Bar(x=recording.channel_ids, y=rates, marker_color=COLORS["teal"]))
    figure.update_layout(
        margin={"l": 50, "r": 16, "t": 18, "b": 42},
        height=300,
        xaxis_title="Channel",
        yaxis_title="Firing rate (Hz)",
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
    )
    figure.update_yaxes(showgrid=True, gridcolor="#EDF0F2", zeroline=False)
    return figure


def sttc_matrix(recording: SpikeRecording, delta_s: float = 0.02) -> np.ndarray:
    recording = _valid_recording(recording)
    matrix = np.eye(recording.n_channels)
    for left, right in combinations(range(recording.n_channels), 2):
        value = spike_time_tiling_coefficient(recording.spike_times[left], recording.spike_times[right], recording.duration_s, delta_s)
        matrix[left, right] = matrix[right, left] = value
    return matrix


def sttc_heatmap_figure(recording: SpikeRecording) -> go.Figure:
    matrix = sttc_matrix(recording)
    figure = go.Figure(
        go.Heatmap(
            z=matrix,
            x=recording.channel_ids,
            y=recording.channel_ids,
            zmin=-0.2,
            zmax=1,
            colorscale=[[0, "#DCE7EF"], [0.167, "#F7F7F7"], [0.45, "#F2C28F"], [1, "#B6403A"]],
            colorbar={"title": "STTC", "thickness": 12},
            hovertemplate="%{y} - %{x}<br>STTC %{z:.3f}<extra></extra>",
        )
    )
    figure.update_layout(margin={"l": 55, "r": 26, "t": 18, "b": 46}, height=340, plot_bgcolor="white", paper_bgcolor="white")
    return figure


def population_activity_figure(recording: SpikeRecording, bin_s: float = 1.0) -> go.Figure:
    recording = _valid_recording(recording)
    edges = np.arange(0, recording.duration_s + bin_s, bin_s)
    counts = sum((np.histogram(times, bins=edges)[0] for times in recording.spike_times), start=np.zeros(edges.size - 1, dtype=int))
    centers = edges[:-1] + bin_s / 2
    figure = go.Figure(go.Scatter(x=centers, y=counts / bin_s, mode="lines", line={"color": COLORS["blue"], "width": 1.3}, fill="tozeroy", fillcolor="rgba(52,120,184,0.12)"))
    figure.update_layout(
        margin={"l": 52, "r": 16, "t": 18, "b": 42},
        height=280,
        xaxis_title="Time (s)",
        yaxis_title="Population rate (spikes/s)",
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
    )
    figure.update_xaxes(showgrid=True, gridcolor="#EDF0F2", zeroline=False)
    figure.update_yaxes(showgrid=True, gridcolor="#EDF0F2", zeroline=False)
    return figure
