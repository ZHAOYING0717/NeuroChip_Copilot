from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from sklearn.metrics import roc_auc_score

from neurochip.drug_response import DrugResponseModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WINDOWS = (180, 600)
COMPARISONS = (
    ("pharma_vs_baseline", "pharma", "baseline", {"Control"}),
    ("ttx_vs_pharma", "ttx", "pharma", {"Control", "NoTreatment"}),
)


def build_pair_scores(table: pd.DataFrame, model: DrugResponseModel, window_s: int) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    indexed = table.set_index(["dataset_id", "well", "stage"], verify_integrity=True)
    for comparison, sample_stage, control_stage, negative_treatments in COMPARISONS:
        for (dataset_id, well), group in table.groupby(["dataset_id", "well"], sort=True):
            stages = set(group["stage"])
            if sample_stage not in stages or control_stage not in stages:
                continue
            sample = indexed.loc[(dataset_id, well, sample_stage)]
            control = indexed.loc[(dataset_id, well, control_stage)]
            score = model.score_pair(sample, control)
            treatment = str(sample["treatment"])
            row: dict[str, float | int | str] = {
                "window_s": int(window_s),
                "dataset_id": str(dataset_id),
                "culture_type": str(sample["culture_type"]),
                "well": str(well),
                "group_id": str(sample["group_id"]),
                "comparison": comparison,
                "sample_stage": sample_stage,
                "control_stage": control_stage,
                "treatment": treatment,
                "dose_um": float(sample["dose_um"]) if pd.notna(sample["dose_um"]) else np.nan,
                "active_perturbation": int(treatment not in negative_treatments),
                "sample_recording_id": str(sample["recording_id"]),
                "control_recording_id": str(control["recording_id"]),
                "data_doi": str(sample["data_doi"]),
            }
            row.update(score)
            for feature in model.feature_names:
                row[f"sample__{feature}"] = float(sample[feature])
                row[f"control__{feature}"] = float(control[feature])
            rows.append(row)
    return pd.DataFrame(rows).sort_values(["window_s", "comparison", "dataset_id", "well"])


def stratified_auc_interval(
    labels: np.ndarray,
    scores: np.ndarray,
    iterations: int = 3000,
    seed: int = 20260806,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    positive = scores[labels == 1]
    negative = scores[labels == 0]
    estimates = np.empty(iterations, dtype=float)
    for index in range(iterations):
        sampled_positive = rng.choice(positive, size=positive.size, replace=True)
        sampled_negative = rng.choice(negative, size=negative.size, replace=True)
        pairwise = sampled_positive[:, None] - sampled_negative[None, :]
        estimates[index] = float(np.mean(pairwise > 0) + 0.5 * np.mean(pairwise == 0))
    lower, upper = np.percentile(estimates, [2.5, 97.5])
    return float(lower), float(upper)


def metric_row(subset: pd.DataFrame, scope: str) -> dict[str, float | int | str | list[float]]:
    labels = subset["active_perturbation"].to_numpy(int)
    scores = subset["response_magnitude"].to_numpy(float)
    positive = scores[labels == 1]
    negative = scores[labels == 0]
    if positive.size == 0 or negative.size == 0:
        raise ValueError(f"Both classes are required for external validation: {scope}")
    auc = float(roc_auc_score(labels, scores))
    auc_interval = stratified_auc_interval(labels, scores)
    test = mannwhitneyu(positive, negative, alternative="two-sided", method="auto")
    rank_biserial = float(2.0 * auc - 1.0)
    threshold_positive = subset.loc[labels == 1, "response_percentile"].to_numpy(float) >= 95.0
    threshold_negative = subset.loc[labels == 0, "response_percentile"].to_numpy(float) >= 95.0
    return {
        "scope": scope,
        "window_s": int(subset["window_s"].iloc[0]),
        "comparison": str(subset["comparison"].iloc[0]),
        "dataset_id": scope,
        "n_pairs": int(len(subset)),
        "n_active": int(positive.size),
        "n_negative_control": int(negative.size),
        "roc_auc": auc,
        "roc_auc_stratified_bootstrap_95ci": list(auc_interval),
        "median_active_response_magnitude": float(np.median(positive)),
        "median_negative_response_magnitude": float(np.median(negative)),
        "mann_whitney_u": float(test.statistic),
        "mann_whitney_two_sided_p": float(test.pvalue),
        "rank_biserial_effect": rank_biserial,
        "sensitivity_at_diazepam_reference_p95": float(np.mean(threshold_positive)),
        "negative_rate_at_diazepam_reference_p95": float(np.mean(threshold_negative)),
    }


def calculate_metrics(scores: pd.DataFrame) -> list[dict[str, float | int | str | list[float]]]:
    rows: list[dict[str, float | int | str | list[float]]] = []
    for (window_s, comparison), comparison_table in scores.groupby(["window_s", "comparison"], sort=True):
        rows.append(metric_row(comparison_table, "pooled"))
        for dataset_id, subset in comparison_table.groupby("dataset_id", sort=True):
            rows.append(metric_row(subset, str(dataset_id)))
    return rows


def compound_summary(scores: pd.DataFrame) -> pd.DataFrame:
    return (
        scores.groupby(["window_s", "dataset_id", "comparison", "treatment"], dropna=False)
        .agg(
            n_pairs=("response_magnitude", "size"),
            median_response_magnitude=("response_magnitude", "median"),
            q25_response_magnitude=("response_magnitude", lambda values: values.quantile(0.25)),
            q75_response_magnitude=("response_magnitude", lambda values: values.quantile(0.75)),
            median_response_percentile=("response_percentile", "median"),
        )
        .reset_index()
    )


def make_figure(scores: pd.DataFrame, output_dir: Path) -> None:
    primary = scores.loc[scores["window_s"] == 180].copy()
    comparisons = [item[0] for item in COMPARISONS]
    datasets = ["hpsc_mea3", "rat_mea2"]
    display = {
        "pharma_vs_baseline": "Pharmacology vs baseline",
        "ttx_vs_pharma": "TTX stage vs pharmacology",
        "hpsc_mea3": "Human iPSC cortical neurons",
        "rat_mea2": "Rat cortical neurons",
    }
    colors = {0: "#4C78A8", 1: "#E45756"}
    rng = np.random.default_rng(42)
    fig, axes = plt.subplots(2, 2, figsize=(10.6, 7.6), sharey=False)
    for row_index, comparison in enumerate(comparisons):
        for column_index, dataset_id in enumerate(datasets):
            axis = axes[row_index, column_index]
            subset = primary.loc[
                (primary["comparison"] == comparison) & (primary["dataset_id"] == dataset_id)
            ]
            groups = [
                subset.loc[subset["active_perturbation"] == label, "response_magnitude"].to_numpy(float)
                for label in (0, 1)
            ]
            box = axis.boxplot(groups, positions=(0, 1), widths=0.48, patch_artist=True, showfliers=False)
            for patch, label in zip(box["boxes"], (0, 1), strict=True):
                patch.set_facecolor(colors[label])
                patch.set_alpha(0.22)
                patch.set_edgecolor(colors[label])
            for label, values in enumerate(groups):
                jitter = rng.uniform(-0.12, 0.12, size=len(values))
                axis.scatter(label + jitter, values, s=28, color=colors[label], alpha=0.82, edgecolor="white", linewidth=0.4)
            labels = subset["active_perturbation"].to_numpy(int)
            auc = roc_auc_score(labels, subset["response_magnitude"].to_numpy(float))
            axis.text(0.04, 0.94, f"AUC = {auc:.2f}", transform=axis.transAxes, va="top", fontsize=10)
            axis.set_xticks((0, 1), ("Control", "Perturbed"))
            axis.set_title(display[dataset_id], fontsize=11)
            axis.grid(axis="y", alpha=0.18)
            if column_index == 0:
                axis.set_ylabel(f"{display[comparison]}\nResponse magnitude")
    fig.suptitle("Frozen diazepam model: external matched-well validation (first 180 s)", fontsize=14, y=0.995)
    fig.tight_layout()
    for suffix in ("png", "svg"):
        target = output_dir / f"gin_external_validation.{suffix}"
        fig.savefig(target, dpi=220 if suffix == "png" else None, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the frozen drug-response model on external GIN datasets")
    parser.add_argument(
        "--model",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "models" / "drug_response_model.joblib",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "results" / "external_validation",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    model = DrugResponseModel.load(args.model)
    model_sha256 = hashlib.sha256(args.model.read_bytes()).hexdigest()
    try:
        public_model_path = args.model.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        public_model_path = args.model.name
    score_tables: list[pd.DataFrame] = []
    for window_s in DEFAULT_WINDOWS:
        source = PROJECT_ROOT / "data" / "processed" / f"external_gin_features_{window_s}s.csv"
        table = pd.read_csv(source)
        score_tables.append(build_pair_scores(table, model, window_s))
        print(f"[score] {window_s}s: {len(score_tables[-1])} matched-well comparisons", flush=True)
    scores = pd.concat(score_tables, ignore_index=True)
    metrics = calculate_metrics(scores)
    summary = compound_summary(scores)
    scores.to_csv(args.output_dir / "gin_pair_scores.csv", index=False)
    summary.to_csv(args.output_dir / "gin_compound_summary.csv", index=False)
    (args.output_dir / "gin_metrics.json").write_text(
        json.dumps(
            {
                "model_status": "frozen; trained only on Sharf et al. diazepam organoid data",
                "model_path": public_model_path,
                "model_sha256": model_sha256,
                "model_feature_names": list(model.feature_names),
                "primary_window_s": 180,
                "sensitivity_window_s": 600,
                "external_data_doi": "10.12751/g-node.wvr3jf",
                "interpretation": (
                    "Response magnitude is transferred across compounds and culture systems. "
                    "The diazepam dose calibrator is not interpreted for external compounds."
                ),
                "metrics": metrics,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    make_figure(scores, args.output_dir)
    print(f"[complete] external validation -> {args.output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
