from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, wilcoxon
from sklearn.metrics import roc_auc_score

from neurochip.drug_response import DrugResponseModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRIMARY_WINDOW_S = 120
ACTIVE_EFFECT_CLASS = "active_spike_burst_perturbation"
NEGATIVE_EFFECT_CLASS = "negative_control"


def _absolute_log_delta(sample: pd.Series, control: pd.Series, feature: str) -> float:
    sample_value = float(sample[feature])
    control_value = float(control[feature])
    return float(abs(np.sign(sample_value) * np.log1p(abs(sample_value)) - np.sign(control_value) * np.log1p(abs(control_value))))


def build_pair_scores(
    table: pd.DataFrame,
    model: DrugResponseModel,
    legacy_model: DrugResponseModel | None = None,
) -> pd.DataFrame:
    index_columns = ["analysis_window_s", "recording_date", "well", "stage"]
    indexed = table.set_index(index_columns, verify_integrity=True)
    rows: list[dict[str, float | int | str]] = []
    groups = table[["analysis_window_s", "recording_date", "well"]].drop_duplicates()
    for item in groups.itertuples(index=False):
        key = (int(item.analysis_window_s), str(item.recording_date), int(item.well))
        control = indexed.loc[(*key, "baseline_control")]
        repeat = indexed.loc[(*key, "baseline_repeat")]
        post = indexed.loc[(*key, "post_treatment")]
        comparisons = (
            ("within_baseline_drift", repeat, "natural_time_drift", NEGATIVE_EFFECT_CLASS, 0.0),
            (
                "post_vs_baseline",
                post,
                str(post["treatment"]),
                str(post["treatment_effect_class"]),
                1.0 if post["treatment_effect_class"] == ACTIVE_EFFECT_CLASS else (
                    0.0 if post["treatment_effect_class"] == NEGATIVE_EFFECT_CLASS else np.nan
                ),
            ),
        )
        for comparison, sample, treatment, effect_class, binary_label in comparisons:
            score = model.score_pair(sample, control)
            row: dict[str, float | int | str] = {
                "analysis_window_s": key[0],
                "recording_date": key[1],
                "well": key[2],
                "group_id": str(control["group_id"]),
                "comparison": comparison,
                "treatment": treatment,
                "treatment_effect_class": effect_class,
                "binary_label": binary_label,
                "sample_recording_id": str(sample["recording_id"]),
                "control_recording_id": str(control["recording_id"]),
                "sample_event_quality_score": float(sample["event_quality_score"]),
                "control_event_quality_score": float(control["event_quality_score"]),
                "firing_rate_abs_log_delta": _absolute_log_delta(sample, control, "firing_rate_mean_hz"),
                "isi_cv_only_abs_log_delta": _absolute_log_delta(sample, control, "isi_cv_mean"),
                "isi_median_only_abs_log_delta": _absolute_log_delta(sample, control, "isi_median_s"),
                "data_doi": str(sample["data_doi"]),
            }
            row.update(score)
            if legacy_model is not None:
                row["legacy_v1_response_magnitude"] = legacy_model.score_pair(sample, control)[
                    "response_magnitude"
                ]
            for feature in model.feature_names:
                row[f"sample__{feature}"] = float(sample[feature])
                row[f"control__{feature}"] = float(control[feature])
            rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["analysis_window_s", "recording_date", "well", "comparison"], ignore_index=True
    )


def stratified_auc_interval(
    labels: np.ndarray,
    scores: np.ndarray,
    iterations: int = 5000,
    seed: int = 20260808,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    positive = scores[labels == 1]
    negative = scores[labels == 0]
    estimates = np.empty(iterations, dtype=float)
    for index in range(iterations):
        sampled_positive = rng.choice(positive, size=positive.size, replace=True)
        sampled_negative = rng.choice(negative, size=negative.size, replace=True)
        differences = sampled_positive[:, None] - sampled_negative[None, :]
        estimates[index] = float(np.mean(differences > 0) + 0.5 * np.mean(differences == 0))
    return tuple(float(value) for value in np.percentile(estimates, [2.5, 97.5]))


def classifier_metric(subset: pd.DataFrame, score_column: str) -> dict[str, float | int | list[float] | str]:
    labels = subset["binary_label"].to_numpy(int)
    scores = subset[score_column].to_numpy(float)
    positive = scores[labels == 1]
    negative = scores[labels == 0]
    auc = float(roc_auc_score(labels, scores))
    test = mannwhitneyu(positive, negative, alternative="two-sided", method="auto")
    return {
        "score": score_column,
        "n_active": int(positive.size),
        "n_control": int(negative.size),
        "roc_auc": auc,
        "roc_auc_stratified_bootstrap_95ci": list(stratified_auc_interval(labels, scores)),
        "median_active": float(np.median(positive)),
        "median_control": float(np.median(negative)),
        "mann_whitney_two_sided_p": float(test.pvalue),
        "rank_biserial_effect": float(2.0 * auc - 1.0),
    }


def primary_metrics(scores: pd.DataFrame, window_s: int) -> tuple[dict, list[dict]]:
    primary = scores.loc[
        (scores["analysis_window_s"] == window_s)
        & (scores["comparison"] == "post_vs_baseline")
        & scores["binary_label"].notna()
    ].copy()
    score_columns = [
        "response_magnitude",
        "firing_rate_abs_log_delta",
        "isi_cv_only_abs_log_delta",
        "isi_median_only_abs_log_delta",
    ]
    if "legacy_v1_response_magnitude" in primary:
        score_columns.append("legacy_v1_response_magnitude")
    comparison = [classifier_metric(primary, column) for column in score_columns]
    model_metric = comparison[0]
    labels = primary["binary_label"].to_numpy(int)
    threshold_positive = primary.loc[labels == 1, "response_percentile"].to_numpy(float) >= 95.0
    threshold_negative = primary.loc[labels == 0, "response_percentile"].to_numpy(float) < 95.0
    model_metric.update(
        {
            "window_s": int(window_s),
            "endpoint": "known spike/burst-suppressing treatment vs contemporaneous untreated control wells",
            "sensitivity_at_frozen_diazepam_reference_p95": float(np.mean(threshold_positive)),
            "specificity_at_frozen_diazepam_reference_p95": float(np.mean(threshold_negative)),
        }
    )
    return model_metric, comparison


def paired_drift_metric(scores: pd.DataFrame, window_s: int) -> dict[str, float | int]:
    subset = scores.loc[scores["analysis_window_s"] == window_s]
    active = subset.loc[
        (subset["comparison"] == "post_vs_baseline")
        & (subset["treatment_effect_class"] == ACTIVE_EFFECT_CLASS),
        ["group_id", "response_magnitude"],
    ].set_index("group_id")
    drift = subset.loc[
        subset["comparison"] == "within_baseline_drift", ["group_id", "response_magnitude"]
    ].set_index("group_id")
    paired = active.join(drift, lsuffix="_active", rsuffix="_drift", how="inner")
    test = wilcoxon(
        paired["response_magnitude_active"],
        paired["response_magnitude_drift"],
        alternative="greater",
        method="auto",
    )
    return {
        "window_s": int(window_s),
        "n_matched_active_wells": int(len(paired)),
        "median_active_response_magnitude": float(paired["response_magnitude_active"].median()),
        "median_same_well_natural_drift_magnitude": float(paired["response_magnitude_drift"].median()),
        "paired_wilcoxon_active_greater_p": float(test.pvalue),
        "fraction_active_exceeding_same_well_drift": float(
            np.mean(paired["response_magnitude_active"] > paired["response_magnitude_drift"])
        ),
    }


def treatment_summary(scores: pd.DataFrame) -> pd.DataFrame:
    return (
        scores.groupby(
            ["analysis_window_s", "comparison", "treatment", "treatment_effect_class"],
            dropna=False,
        )
        .agg(
            n_pairs=("response_magnitude", "size"),
            median_response_magnitude=("response_magnitude", "median"),
            q25_response_magnitude=("response_magnitude", lambda values: values.quantile(0.25)),
            q75_response_magnitude=("response_magnitude", lambda values: values.quantile(0.75)),
            median_response_percentile=("response_percentile", "median"),
            median_pair_quality=("pair_minimum_event_quality_score", "median"),
        )
        .reset_index()
    )


def make_figure(scores: pd.DataFrame, baseline_metrics: list[dict], output_dir: Path) -> None:
    primary = scores.loc[
        (scores["analysis_window_s"] == PRIMARY_WINDOW_S)
        & (scores["comparison"] == "post_vs_baseline")
    ].copy()
    order = ["control", "CNQX+AP5", "baclofen", "bicuculline", "unknown_pharmacology"]
    colors = ["#4C78A8", "#E45756", "#F2CF5B", "#72B7B2", "#9D9DA1"]
    rng = np.random.default_rng(42)
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.4), constrained_layout=True)
    groups = [primary.loc[primary["treatment"] == name, "response_magnitude"].to_numpy(float) for name in order]
    boxes = axes[0].boxplot(groups, positions=np.arange(len(order)), widths=0.55, patch_artist=True, showfliers=False)
    for patch, color in zip(boxes["boxes"], colors, strict=True):
        patch.set_facecolor(color)
        patch.set_alpha(0.28)
        patch.set_edgecolor(color)
    for index, (values, color) in enumerate(zip(groups, colors, strict=True)):
        axes[0].scatter(
            index + rng.uniform(-0.12, 0.12, len(values)),
            values,
            s=34,
            color=color,
            edgecolor="white",
            linewidth=0.5,
            zorder=3,
        )
    axes[0].set_xticks(np.arange(len(order)), ["Control", "CNQX+AP5", "Baclofen", "Bicuculline", "Unlabeled"], rotation=20)
    axes[0].set_ylabel("Frozen-model response magnitude")
    axes[0].set_title("A. External cortical organoid responses")
    axes[0].grid(axis="y", alpha=0.2)

    labels = {
        "response_magnitude": "NeuroChip v2",
        "firing_rate_abs_log_delta": "Firing rate",
        "isi_cv_only_abs_log_delta": "ISI CV only",
        "isi_median_only_abs_log_delta": "Median ISI only",
        "legacy_v1_response_magnitude": "Legacy v1",
    }
    names = [labels[item["score"]] for item in baseline_metrics]
    aucs = [float(item["roc_auc"]) for item in baseline_metrics]
    intervals = [item["roc_auc_stratified_bootstrap_95ci"] for item in baseline_metrics]
    errors = np.asarray([[auc - interval[0], interval[1] - auc] for auc, interval in zip(aucs, intervals)]).T
    axes[1].bar(np.arange(len(names)), aucs, color="#4C78A8", alpha=0.82)
    axes[1].errorbar(np.arange(len(names)), aucs, yerr=errors, fmt="none", color="#333333", capsize=3)
    axes[1].axhline(0.5, color="#777777", linestyle="--", linewidth=1)
    axes[1].set_ylim(0, 1.05)
    axes[1].set_xticks(np.arange(len(names)), names, rotation=25)
    axes[1].set_ylabel("ROC AUC (95% bootstrap CI)")
    axes[1].set_title("B. Frozen model vs simple baselines")
    axes[1].grid(axis="y", alpha=0.2)
    for suffix in ("png", "svg"):
        fig.savefig(output_dir / f"trujillo_external_validation.{suffix}", dpi=220 if suffix == "png" else None)
    plt.close(fig)


def write_report(metrics: dict, output_dir: Path) -> None:
    primary = metrics["primary_labeled_endpoint"]
    drift = metrics["paired_natural_drift_check"]
    ci = primary["roc_auc_stratified_bootstrap_95ci"]
    text = f"""# Trujillo cortical organoid external validation

## Design

- Frozen NeuroChip v2 model; no retraining or threshold tuning on this dataset.
- Independent human cortical organoid MEA dataset: DOI 10.5281/zenodo.4751759.
- Primary endpoint: known CNQX+AP5/baclofen wells versus contemporaneous untreated control wells.
- Bicuculline is reported separately because the source paper describes little change in spike/burst counts.
- The 170303 well identities are not public in the located source code, so they remain unlabeled and exploratory.

## Primary result

- AUC: {primary['roc_auc']:.3f} (95% bootstrap CI {ci[0]:.3f}-{ci[1]:.3f})
- Active wells: {primary['n_active']}; control wells: {primary['n_control']}
- Frozen p95 sensitivity: {primary['sensitivity_at_frozen_diazepam_reference_p95']:.3f}
- Frozen p95 specificity: {primary['specificity_at_frozen_diazepam_reference_p95']:.3f}
- Mann-Whitney p: {primary['mann_whitney_two_sided_p']:.4g}

## Natural-drift check

- Matched active wells: {drift['n_matched_active_wells']}
- Active median response: {drift['median_active_response_magnitude']:.3f}
- Same-well baseline drift median: {drift['median_same_well_natural_drift_magnitude']:.3f}
- Fraction active response above its own drift: {drift['fraction_active_exceeding_same_well_drift']:.3f}
- One-sided paired Wilcoxon p: {drift['paired_wilcoxon_active_greater_p']:.4g}

## Interpretation boundary

This test supports or challenges transfer to one additional cortical-organoid protocol. It does not by itself prove universal applicability to every organoid type, laboratory, MEA platform, maturation stage, or drug. The original diazepam dose estimate is not interpreted for these external compounds.
"""
    (output_dir / "trujillo_validation_report.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the frozen model on Trujillo cortical organoid data")
    parser.add_argument(
        "--features",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "external_trujillo_features.csv",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "models" / "drug_response_model.joblib",
    )
    parser.add_argument(
        "--legacy-model",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "models" / "drug_response_model_v1.joblib",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "results" / "external_validation",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    model = DrugResponseModel.load(args.model)
    legacy_model = DrugResponseModel.load(args.legacy_model) if args.legacy_model.exists() else None
    table = pd.read_csv(args.features, dtype={"recording_date": str})
    scores = build_pair_scores(table, model, legacy_model)
    primary, baselines = primary_metrics(scores, PRIMARY_WINDOW_S)
    metrics = {
        "model_status": "frozen; trained only on Sharf et al. diazepam organoid data",
        "model_path": args.model.resolve().relative_to(PROJECT_ROOT).as_posix(),
        "model_sha256": hashlib.sha256(args.model.read_bytes()).hexdigest(),
        "model_feature_names": list(model.feature_names),
        "external_data_doi": "10.5281/zenodo.4751759",
        "external_article_doi": "10.1016/j.stem.2019.08.002",
        "primary_window_s": PRIMARY_WINDOW_S,
        "sensitivity_window_s": 90,
        "n_feature_rows": int(len(table)),
        "n_pair_scores": int(len(scores)),
        "primary_labeled_endpoint": primary,
        "baseline_comparison": baselines,
        "paired_natural_drift_check": paired_drift_metric(scores, PRIMARY_WINDOW_S),
        "sensitivity_90s_labeled_endpoint": primary_metrics(scores, 90)[0],
        "label_provenance": {
            "source": "voytekresearch/OscillatoryOrganoids scripts/corticoid_figures.m",
            "known_dates": ["161217", "170207"],
            "unlabeled_date": "170303",
        },
        "interpretation": (
            "Frozen paired-response transfer to an independent cortical-organoid MEA protocol. "
            "External compound dose estimates are not interpreted; small labeled sample sizes require caution."
        ),
    }
    scores.to_csv(args.output_dir / "trujillo_pair_scores.csv", index=False)
    treatment_summary(scores).to_csv(args.output_dir / "trujillo_treatment_summary.csv", index=False)
    (args.output_dir / "trujillo_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    make_figure(scores, baselines, args.output_dir)
    write_report(metrics, args.output_dir)
    print(f"[complete] Trujillo validation -> {args.output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
