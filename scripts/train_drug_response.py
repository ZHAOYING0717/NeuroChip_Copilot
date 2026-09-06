from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, roc_auc_score
from sklearn.model_selection import LeaveOneGroupOut

from neurochip.drug_response import (
    DRUG_RESPONSE_FEATURES,
    DRUG_RESPONSE_FEATURES_V1,
    fit_drug_response_model,
    paired_feature_deltas,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def cross_validated_scores(table: pd.DataFrame, feature_names: tuple[str, ...]) -> pd.DataFrame:
    groups = table["group_id"].astype(str).to_numpy()
    rows: list[pd.DataFrame] = []
    for fold, (train_index, test_index) in enumerate(LeaveOneGroupOut().split(table, groups=groups), start=1):
        model = fit_drug_response_model(table.iloc[train_index], feature_names)
        scored = model.transform(table.iloc[test_index]).copy()
        scored["fold"] = fold
        rows.append(scored)
        print(
            f"[fold {fold}/4] held-out organoid={groups[test_index][0]} train={len(train_index)} test={len(test_index)}",
            flush=True,
        )
    return pd.concat(rows, ignore_index=True).sort_values(["group_id", "dose_um"]).reset_index(drop=True)


def cluster_intervals(predictions: pd.DataFrame, iterations: int = 3000, seed: int = 42) -> dict[str, list[float]]:
    rng = np.random.default_rng(seed)
    group_ids = predictions["group_id"].unique()
    rho_values: list[float] = []
    auc_values: list[float] = []
    for _ in range(iterations):
        sampled = rng.choice(group_ids, size=len(group_ids), replace=True)
        sample = pd.concat([predictions.loc[predictions["group_id"] == group_id] for group_id in sampled])
        rho_values.append(float(spearmanr(sample["dose_um"], sample["response_magnitude"]).statistic))
        labels = sample["dose_um"].to_numpy(float) >= 30.0
        if np.unique(labels).size == 2:
            auc_values.append(float(roc_auc_score(labels, sample["response_magnitude"])))
    return {
        "dose_spearman_cluster_bootstrap_95ci": [float(value) for value in np.nanpercentile(rho_values, [2.5, 97.5])],
        "high_dose_auc_cluster_bootstrap_95ci": [float(value) for value in np.nanpercentile(auc_values, [2.5, 97.5])],
    }


def blocked_permutation_pvalue(predictions: pd.DataFrame, iterations: int = 5000, seed: int = 43) -> float:
    treated = predictions["dose_um"].to_numpy(float) > 0
    dose = predictions["dose_um"].to_numpy(float)
    score = predictions["response_magnitude"].to_numpy(float)
    groups = predictions["group_id"].astype(str).to_numpy()
    observed = abs(float(spearmanr(dose[treated], score[treated]).statistic))
    rng = np.random.default_rng(seed)
    exceedances = 0
    for _ in range(iterations):
        permuted = dose.copy()
        for group_id in np.unique(groups):
            indices = np.flatnonzero((groups == group_id) & treated)
            permuted[indices] = rng.permutation(permuted[indices])
        statistic = abs(float(spearmanr(permuted[treated], score[treated]).statistic))
        exceedances += int(statistic >= observed)
    return float((exceedances + 1) / (iterations + 1))


def unpaired_baseline_scores(table: pd.DataFrame, feature_names: tuple[str, ...]) -> np.ndarray:
    groups = table["group_id"].astype(str).to_numpy()
    dose = table["dose_um"].to_numpy(float)
    matrix = np.log1p(table.loc[:, list(feature_names)].to_numpy(float))
    scores = np.zeros(len(table), dtype=float)
    for train_index, test_index in LeaveOneGroupOut().split(matrix, groups=groups):
        control_index = train_index[dose[train_index] == 0]
        center = np.median(matrix[control_index], axis=0)
        centered = matrix[train_index] - center
        quartiles = np.percentile(centered, [25, 75], axis=0)
        scales = quartiles[1] - quartiles[0]
        standard_deviation = np.std(centered, axis=0)
        scales = np.where(scales > 1e-8, scales, np.where(standard_deviation > 1e-8, standard_deviation, 1.0))
        scores[test_index] = np.sqrt(np.mean(np.square((matrix[test_index] - center) / scales), axis=1))
    return scores


def main() -> int:
    parser = argparse.ArgumentParser(description="Train and validate the matched-control diazepam response model")
    parser.add_argument(
        "--input",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "diazepam_features.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "results" / "drug_response",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    table = pd.read_csv(args.input).sort_values(["group_id", "dose_um"]).reset_index(drop=True)
    if len(table) != 19 or table["group_id"].nunique() != 4:
        raise RuntimeError("Expected 19 conditions across four organoids")

    predictions = cross_validated_scores(table, DRUG_RESPONSE_FEATURES)
    dose = predictions["dose_um"].to_numpy(float)
    magnitude = predictions["response_magnitude"].to_numpy(float)
    predicted_dose = predictions["predicted_dose_um_exploratory"].to_numpy(float)
    treated = dose > 0
    high_dose = dose >= 30
    intervals = cluster_intervals(predictions)

    within_group = {
        str(group_id): float(spearmanr(group["dose_um"], group["response_magnitude"]).statistic)
        for group_id, group in predictions.groupby("group_id")
    }
    metrics = {
        "n_conditions": int(len(table)),
        "n_organoids": int(table["group_id"].nunique()),
        "cross_validation": "LeaveOneGroupOut by organoid; held-out treatments paired only to their held-out control",
        "feature_names": list(DRUG_RESPONSE_FEATURES),
        "response_magnitude_dose_spearman": float(spearmanr(dose, magnitude).statistic),
        "response_magnitude_dose_spearman_cluster_bootstrap_95ci": intervals[
            "dose_spearman_cluster_bootstrap_95ci"
        ],
        "treated_only_dose_spearman": float(spearmanr(dose[treated], magnitude[treated]).statistic),
        "treated_only_blocked_permutation_p": blocked_permutation_pvalue(predictions),
        "high_dose_auc": float(roc_auc_score(high_dose, magnitude)),
        "high_dose_auc_cluster_bootstrap_95ci": intervals["high_dose_auc_cluster_bootstrap_95ci"],
        "exploratory_dose_mae_um": float(mean_absolute_error(dose, predicted_dose)),
        "exploratory_dose_rmse_um": float(mean_squared_error(dose, predicted_dose) ** 0.5),
        "exploratory_dose_r2": float(r2_score(dose, predicted_dose)),
        "exploratory_dose_spearman": float(spearmanr(dose, predicted_dose).statistic),
        "within_organoid_dose_spearman": within_group,
        "scope": "Small public proof-of-concept cohort; response magnitude is primary, calibrated dose is exploratory.",
    }

    ablations: list[dict[str, float | str | int]] = []
    feature_sets = {
        "primary_spike_timing": DRUG_RESPONSE_FEATURES,
        "legacy_v1_timing_and_burst": DRUG_RESPONSE_FEATURES_V1,
        "research_extended_exploratory": DRUG_RESPONSE_FEATURES_V1
        + (
            "firing_stability_cv",
            "activity_decay_log2_ratio",
            "avalanche_branching_ratio",
            "mutual_information_mean_bits",
            "transfer_entropy_mean_bits",
        ),
        "isi_cv_only": ("isi_cv_mean",),
        "burst_duration_only": ("network_burst_mean_duration_s",),
    }
    for name, features in feature_sets.items():
        scored = cross_validated_scores(table, features)
        ablations.append(
            {
                "analysis": name,
                "n_features": len(features),
                "dose_spearman": float(spearmanr(scored["dose_um"], scored["response_magnitude"]).statistic),
                "high_dose_auc": float(
                    roc_auc_score(scored["dose_um"].to_numpy(float) >= 30, scored["response_magnitude"])
                ),
            }
        )
    unpaired = unpaired_baseline_scores(table, DRUG_RESPONSE_FEATURES)
    ablations.append(
        {
            "analysis": "unpaired_training_control_reference",
            "n_features": len(DRUG_RESPONSE_FEATURES),
            "dose_spearman": float(spearmanr(table["dose_um"], unpaired).statistic),
            "high_dose_auc": float(roc_auc_score(table["dose_um"].to_numpy(float) >= 30, unpaired)),
        }
    )
    ablation_lookup = {str(row["analysis"]): row for row in ablations}
    metrics["model_version"] = "2.0"
    metrics["feature_selection"] = {
        "primary": list(DRUG_RESPONSE_FEATURES),
        "legacy_v1": list(DRUG_RESPONSE_FEATURES_V1),
        "primary_grouped_cv_dose_spearman": ablation_lookup["primary_spike_timing"]["dose_spearman"],
        "legacy_grouped_cv_dose_spearman": ablation_lookup["legacy_v1_timing_and_burst"]["dose_spearman"],
        "policy": (
            "The simpler spike-timing model is primary because it improved leave-one-organoid-out metrics. "
            "The extended research feature set remains exploratory and did not improve this small cohort."
        ),
    }
    metrics["quality_gate"] = "Paired inference reports the minimum event-QC score and flags scores below 50."

    full_model = fit_drug_response_model(table, DRUG_RESPONSE_FEATURES)
    full_model.save(PROJECT_ROOT / "artifacts" / "models" / "drug_response_model.joblib")
    legacy_model = fit_drug_response_model(table, DRUG_RESPONSE_FEATURES_V1)
    legacy_model.save(PROJECT_ROOT / "artifacts" / "models" / "drug_response_model_v1.joblib")
    predictions.to_csv(args.output_dir / "cross_validation_predictions.csv", index=False)
    full_model.transform(table).to_csv(args.output_dir / "full_model_scores.csv", index=False)
    paired_feature_deltas(table, DRUG_RESPONSE_FEATURES).to_csv(args.output_dir / "paired_feature_deltas.csv", index=False)
    pd.DataFrame(ablations).to_csv(args.output_dir / "ablation.csv", index=False)
    (args.output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
