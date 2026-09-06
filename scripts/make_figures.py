from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve


plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
plt.rcParams["svg.fonttype"] = "none"
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["font.size"] = 7
plt.rcParams["axes.linewidth"] = 0.8
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False
plt.rcParams["legend.frameon"] = False

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COLORS = {
    "clean": "#606060",
    "channel_dropout": "#5B8FD6",
    "hyperactivity": "#D24B40",
    "hypersynchrony": "#E28E2C",
    "hero": "#0F4D92",
    "grid": "#D8D8D8",
    "2950": "#0F6B78",
    "2953": "#3166A8",
    "2954": "#C55A2A",
    "2957": "#8B4F87",
}
LABELS = {
    "clean": "Clean",
    "channel_dropout": "Channel dropout",
    "hyperactivity": "Hyperactivity",
    "hypersynchrony": "Hypersynchrony",
}


def panel_label(axis: plt.Axes, label: str) -> None:
    axis.text(-0.16, 1.04, label, transform=axis.transAxes, fontsize=9, fontweight="bold", va="bottom")


def save_figure(figure: plt.Figure, base: Path) -> None:
    base.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(base.with_suffix(".svg"), bbox_inches="tight")
    figure.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
    figure.savefig(base.with_suffix(".tiff"), dpi=600, bbox_inches="tight")
    figure.savefig(base.with_suffix(".png"), dpi=220, bbox_inches="tight")


def create_drug_response_figure(output_dir: Path) -> None:
    drug_features = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "diazepam_features.csv")
    results_dir = PROJECT_ROOT / "artifacts" / "results" / "drug_response"
    predictions = pd.read_csv(results_dir / "cross_validation_predictions.csv")
    ablation = pd.read_csv(results_dir / "ablation.csv")
    metrics = json.loads((results_dir / "metrics.json").read_text(encoding="utf-8"))

    figure, axes = plt.subplots(1, 3, figsize=(183 / 25.4, 92 / 25.4), constrained_layout=True)
    axis_isi, axis_response, axis_ablation = axes
    for group_id, group in drug_features.groupby("group_id"):
        group = group.sort_values("dose_um")
        control = float(group.loc[group["dose_um"] == 0, "isi_cv_mean"].iloc[0])
        axis_isi.plot(
            group["dose_um"],
            group["isi_cv_mean"] / control,
            color=COLORS[str(int(group_id))],
            marker="o",
            markersize=3.8,
            linewidth=1.2,
            label=str(int(group_id)),
        )
    axis_isi.axhline(1, color=COLORS["grid"], linestyle="--", linewidth=0.9)
    axis_isi.set(xlabel="Diazepam (uM)", ylabel="ISI CV / matched control", xticks=[0, 3, 10, 30, 50])
    axis_isi.set_title("Observed spike-train regularization", loc="left", fontsize=8, fontweight="bold")
    axis_isi.legend(title="Organoid", fontsize=6, title_fontsize=6, ncols=2)
    panel_label(axis_isi, "a")

    for group_id, group in predictions.groupby("group_id"):
        group = group.sort_values("dose_um")
        axis_response.plot(
            group["dose_um"],
            group["response_magnitude"],
            color=COLORS[str(int(group_id))],
            marker="o",
            markersize=3.8,
            linewidth=1.2,
        )
    low, high = metrics["response_magnitude_dose_spearman_cluster_bootstrap_95ci"]
    axis_response.text(
        0.04,
        0.96,
        f"LOO organoid rho = {metrics['response_magnitude_dose_spearman']:.3f}\n"
        f"95% CI {low:.3f}-{high:.3f}\n"
        f"treated-only block p = {metrics['treated_only_blocked_permutation_p']:.4f}",
        transform=axis_response.transAxes,
        va="top",
        fontsize=6.4,
        color="#333333",
    )
    axis_response.set(xlabel="Diazepam (uM)", ylabel="Matched-control response magnitude", xticks=[0, 3, 10, 30, 50])
    axis_response.set_title("Held-out dose response", loc="left", fontsize=8, fontweight="bold")
    panel_label(axis_response, "b")

    labels = {
        "primary_spike_timing": "Primary: spike timing",
        "legacy_v1_timing_and_burst": "Legacy v1: timing + burst",
        "research_extended_exploratory": "Extended research set",
        "isi_cv_only": "Matched: ISI CV",
        "burst_duration_only": "Matched: burst duration",
        "unpaired_training_control_reference": "Unpaired reference",
    }
    plotted = ablation.iloc[::-1].copy()
    colors = ["#A7A7A7" if name.startswith("unpaired") else "#42949E" for name in plotted["analysis"]]
    axis_ablation.barh(
        range(len(plotted)),
        plotted["dose_spearman"],
        color=colors,
        height=0.62,
    )
    axis_ablation.axvline(0, color="#777777", linewidth=0.8)
    axis_ablation.set_yticks(range(len(plotted)), [labels.get(name, name) for name in plotted["analysis"]])
    axis_ablation.set(xlabel="Dose-response Spearman rho", xlim=(-0.62, 1.02))
    for index, value in enumerate(plotted["dose_spearman"]):
        axis_ablation.text(
            value + (0.025 if value >= 0 else 0.04),
            index,
            f"{value:.2f}",
            ha="left",
            va="center",
            fontsize=6,
            color="#FFFFFF" if value < 0 else "#333333",
        )
    axis_ablation.set_title("Matched-control ablation", loc="left", fontsize=8, fontweight="bold")
    panel_label(axis_ablation, "c")

    save_figure(figure, output_dir / "figure2_drug_response")
    plt.close(figure)


def _external_metric(metrics: dict, comparison: str, dataset_id: str) -> dict:
    return next(
        item
        for item in metrics["metrics"]
        if item["window_s"] == 180
        and item["comparison"] == comparison
        and item["dataset_id"] == dataset_id
    )


def _external_distribution_panel(
    axis: plt.Axes,
    pair_scores: pd.DataFrame,
    metrics: dict,
    comparison: str,
    title: str,
    active_label: str,
) -> None:
    subset = pair_scores.loc[
        (pair_scores["window_s"] == 180) & (pair_scores["comparison"] == comparison)
    ].copy()
    datasets = [("hpsc_mea3", "Human 2D"), ("rat_mea2", "Rat 2D")]
    positions = [0.82, 1.18, 1.82, 2.18]
    groups: list[np.ndarray] = []
    colors: list[str] = []
    rng = np.random.default_rng(17 if comparison == "pharma_vs_baseline" else 23)

    for dataset_id, _ in datasets:
        data = subset.loc[subset["dataset_id"] == dataset_id]
        for active in (False, True):
            values = data.loc[data["active_perturbation"].astype(bool) == active, "response_magnitude"].to_numpy()
            groups.append(values)
            colors.append("#90979B" if not active else "#C94F45")

    boxes = axis.boxplot(
        groups,
        positions=positions,
        widths=0.28,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": "#FFFFFF", "linewidth": 1.1},
        whiskerprops={"linewidth": 0.8},
        capprops={"linewidth": 0.8},
    )
    for patch, color in zip(boxes["boxes"], colors, strict=True):
        patch.set_facecolor(color)
        patch.set_edgecolor(color)
    for position, values, color in zip(positions, groups, colors, strict=True):
        axis.scatter(
            rng.normal(position, 0.025, len(values)),
            values,
            s=7,
            alpha=0.5,
            color=color,
            linewidths=0,
            zorder=3,
        )

    tick_labels = []
    for dataset_id, label in datasets:
        metric = _external_metric(metrics, comparison, dataset_id)
        tick_labels.append(f"{label}\nAUC {metric['roc_auc']:.3f}")
    axis.set_xticks([1, 2], tick_labels)
    axis.set_xlim(0.55, 2.45)
    axis.set_ylim(0, 20)
    axis.set_ylabel("Frozen-model response magnitude")
    axis.set_title(title, loc="left", fontsize=8, fontweight="bold")
    axis.plot([], [], color="#90979B", linewidth=5, label="Negative control")
    axis.plot([], [], color="#C94F45", linewidth=5, label=active_label)
    axis.legend(loc="upper left", fontsize=5.8)


def create_external_validation_figure(output_dir: Path) -> None:
    drug_dir = PROJECT_ROOT / "artifacts" / "results" / "drug_response"
    external_dir = PROJECT_ROOT / "artifacts" / "results" / "external_validation"
    ablation = pd.read_csv(drug_dir / "ablation.csv").set_index("analysis")
    pair_scores = pd.read_csv(external_dir / "gin_pair_scores.csv")
    metrics = json.loads((external_dir / "gin_metrics.json").read_text(encoding="utf-8"))

    figure, axes = plt.subplots(1, 3, figsize=(183 / 25.4, 90 / 25.4), constrained_layout=True)
    axis_internal, axis_pharma, axis_ttx = axes

    versions = ["legacy_v1_timing_and_burst", "primary_spike_timing"]
    values = np.array(
        [
            [ablation.loc[name, "dose_spearman"], ablation.loc[name, "high_dose_auc"]]
            for name in versions
        ]
    )
    x = np.arange(2)
    width = 0.32
    axis_internal.bar(x - width / 2, values[0], width, color="#9AA1A5", label="Legacy v1")
    axis_internal.bar(x + width / 2, values[1], width, color="#167C80", label="Primary v2")
    for version_index, offset in enumerate((-width / 2, width / 2)):
        for metric_index, value in enumerate(values[version_index]):
            axis_internal.text(metric_index + offset, value + 0.018, f"{value:.3f}", ha="center", va="bottom", fontsize=6)
    axis_internal.set_xticks(x, ["Dose\nSpearman rho", "High-dose\nAUROC"])
    axis_internal.set_ylim(0, 1.08)
    axis_internal.set_ylabel("Held-out performance")
    axis_internal.set_title("Simpler paired model", loc="left", fontsize=8, fontweight="bold")
    axis_internal.legend(loc="lower right", fontsize=6)
    panel_label(axis_internal, "a")

    _external_distribution_panel(
        axis_pharma,
        pair_scores,
        metrics,
        "pharma_vs_baseline",
        "External pharmacology",
        "Active treatment",
    )
    panel_label(axis_pharma, "b")
    _external_distribution_panel(
        axis_ttx,
        pair_scores,
        metrics,
        "ttx_vs_pharma",
        "External TTX suppression",
        "TTX",
    )
    panel_label(axis_ttx, "c")

    save_figure(figure, output_dir / "figure3_external_validation")
    plt.close(figure)


def create_architecture_figure(output_dir: Path) -> None:
    figure, axis = plt.subplots(figsize=(183 / 25.4, 72 / 25.4))
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")
    boxes = [
        (0.015, 0.36, 0.15, 0.34, "Spike-event inputs", "MAT / HDF5 / CSV", "#E9EFF4", "#3166A8"),
        (0.205, 0.36, 0.15, 0.34, "Scope and QC", "channel audit\nstability guard", "#E8F3F2", "#147F7A"),
        (0.395, 0.36, 0.18, 0.34, "Functional features", "rate / STTC / graph\navalanche / information", "#F7F1E5", "#B77C14"),
        (0.615, 0.36, 0.17, 0.34, "Interpretable models", "anomaly Shapley\ngoal-aware effects", "#F4EDEF", "#8B4F87"),
        (0.825, 0.36, 0.16, 0.34, "Research outputs", "dashboard / reports\nprojects / standard CSV", "#EEF2E7", "#557A30"),
    ]
    for x, y, width, height, title, detail, fill, edge in boxes:
        patch = FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle="round,pad=0.008,rounding_size=0.012",
            linewidth=1.15,
            edgecolor=edge,
            facecolor=fill,
        )
        axis.add_patch(patch)
        axis.text(x + width / 2, y + height * 0.68, title, ha="center", va="center", fontsize=7, fontweight="bold", color="#20262A")
        axis.text(x + width / 2, y + height * 0.34, detail, ha="center", va="center", fontsize=6.2, color="#4E585E", linespacing=1.35)
    for left, right in zip(boxes[:-1], boxes[1:], strict=True):
        start = left[0] + left[2] + 0.008
        end = right[0] - 0.008
        axis.annotate("", xy=(end, 0.53), xytext=(start, 0.53), arrowprops={"arrowstyle": "-|>", "color": "#8C969C", "lw": 1.1})
    axis.text(0.015, 0.89, "NeuroChip Copilot analysis architecture", fontsize=9, fontweight="bold", color="#20262A")
    axis.text(0.015, 0.16, "Validation: source reproduction | group-held-out anomalies | leave-one-organoid-out response | frozen 2D and organoid stress tests", fontsize=6.3, color="#465158")
    axis.text(0.015, 0.055, "Boundary: event-only files cannot establish voltage noise, saturation or waveform quality; predictive direction is not proof of causal influence.", fontsize=6.2, color="#A3453E")
    save_figure(figure, output_dir / "figure0_architecture")
    plt.close(figure)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create publication-quality NeuroChip figures")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "artifacts" / "figures")
    args = parser.parse_args()
    phenotype_dir = PROJECT_ROOT / "artifacts" / "results" / "phenotype"
    predictions = pd.read_csv(phenotype_dir / "cross_validation_predictions.csv")
    metrics = json.loads((phenotype_dir / "metrics.json").read_text(encoding="utf-8"))
    comparison = pd.read_csv(PROJECT_ROOT / "artifacts" / "results" / "source_validation" / "feature_comparison.csv")

    figure = plt.figure(figsize=(183 / 25.4, 110 / 25.4), constrained_layout=True)
    grid = figure.add_gridspec(2, 2, width_ratios=[1.08, 1], height_ratios=[1, 1])
    axis_roc = figure.add_subplot(grid[:, 0])
    axis_scores = figure.add_subplot(grid[0, 1])
    axis_validation = figure.add_subplot(grid[1, 1])

    fpr, tpr, _ = roc_curve(predictions["label"], predictions["anomaly_percentile"])
    axis_roc.plot(fpr, tpr, color=COLORS["hero"], linewidth=2.2)
    axis_roc.plot([0, 1], [0, 1], color=COLORS["grid"], linestyle="--", linewidth=1)
    low, high = metrics["roc_auc_cluster_bootstrap_95ci"]
    axis_roc.text(
        0.97,
        0.06,
        f"AUROC {metrics['roc_auc']:.3f}\n95% CI {low:.3f}-{high:.3f}",
        transform=axis_roc.transAxes,
        ha="right",
        va="bottom",
        color=COLORS["hero"],
        fontsize=8,
        fontweight="bold",
    )
    axis_roc.set(xlabel="False-positive rate", ylabel="True-positive rate", xlim=(0, 1), ylim=(0, 1))
    axis_roc.set_aspect("equal", adjustable="box")
    axis_roc.set_title("Group-held-out anomaly detection", loc="left", fontsize=8, fontweight="bold")
    panel_label(axis_roc, "a")

    order = ["clean", "channel_dropout", "hyperactivity", "hypersynchrony"]
    values = [predictions.loc[predictions["perturbation"] == kind, "anomaly_percentile"].to_numpy() for kind in order]
    box = axis_scores.boxplot(values, patch_artist=True, widths=0.6, showfliers=False, medianprops={"color": "white", "linewidth": 1.2})
    for patch, kind in zip(box["boxes"], order, strict=True):
        patch.set_facecolor(COLORS[kind])
        patch.set_edgecolor(COLORS[kind])
    rng = np.random.default_rng(7)
    for index, (kind, group_values) in enumerate(zip(order, values, strict=True), start=1):
        axis_scores.scatter(rng.normal(index, 0.045, len(group_values)), group_values, s=5, alpha=0.28, color=COLORS[kind], linewidths=0)
    axis_scores.axhline(95, color="#A8A8A8", linestyle="--", linewidth=0.8)
    axis_scores.set_xticks(range(1, len(order) + 1), [LABELS[kind] for kind in order], rotation=18, ha="right")
    axis_scores.set_ylabel("Anomaly percentile")
    axis_scores.set_ylim(-4, 104)
    axis_scores.set_title("Controlled event-level perturbations", loc="left", fontsize=8, fontweight="bold")
    panel_label(axis_scores, "b")

    fr_scale = max(comparison["FR"].max(), comparison["firing_rate_mean_hz"].max())
    sttc_scale = max(comparison["STTC"].max(), comparison["sttc_mean"].max())
    axis_validation.scatter(comparison["FR"] / fr_scale, comparison["firing_rate_mean_hz"] / fr_scale, s=13, color="#42949E", alpha=0.8, label="Firing rate")
    axis_validation.scatter(comparison["STTC"] / sttc_scale, comparison["sttc_mean"] / sttc_scale, s=13, facecolors="none", edgecolors="#9A4D8E", linewidths=0.8, label="STTC")
    axis_validation.plot([0, 1], [0, 1], color="#767676", linewidth=0.9, linestyle="--")
    axis_validation.set(xlabel="Publisher value (normalized)", ylabel="Extracted value (normalized)", xlim=(-0.03, 1.03), ylim=(-0.03, 1.03))
    axis_validation.legend(loc="lower right", fontsize=6)
    axis_validation.set_title("Exact source-data reproduction (n=45)", loc="left", fontsize=8, fontweight="bold")
    panel_label(axis_validation, "c")

    save_figure(figure, args.output_dir / "figure1_validation")
    plt.close(figure)
    create_architecture_figure(args.output_dir)
    create_drug_response_figure(args.output_dir)
    create_external_validation_figure(args.output_dir)
    print(f"[complete] figure exports -> {args.output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
