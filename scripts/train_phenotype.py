from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import GroupKFold

from neurochip import extract_features, read_recording
from neurochip.modeling import (
    PHENOTYPE_FEATURES,
    PHENOTYPE_FEATURES_EXTENDED,
    fit_phenotype_model,
    pca_loading_table,
)
from neurochip.perturb import perturb_recording


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PERTURBATIONS = ("channel_dropout", "hyperactivity", "hypersynchrony")
FEATURE_SETS = {
    "full_functional": PHENOTYPE_FEATURES,
    "research_extended_exploratory": PHENOTYPE_FEATURES_EXTENDED,
    "activity_only": (
        "firing_rate_mean_hz",
        "firing_rate_median_hz",
        "firing_rate_std_hz",
        "firing_rate_max_hz",
        "firing_rate_cv",
        "active_channel_fraction",
        "dominant_channel_fraction",
    ),
    "spike_timing_only": ("isi_median_s", "isi_cv_mean"),
    "network_only": (
        "sttc_mean",
        "sttc_median",
        "sttc_max",
        "network_density",
        "network_clustering",
        "population_entropy",
        "network_burst_rate_per_min",
        "network_burst_mean_duration_s",
        "network_burst_participation",
    ),
    "stability_criticality": (
        "firing_stability_cv",
        "activity_decay_log2_ratio",
        "activity_trend_normalized_slope",
        "avalanche_rate_per_min",
        "avalanche_size_mean",
        "avalanche_size_cv",
        "avalanche_branching_ratio",
        "avalanche_criticality_distance",
    ),
    "information_flow": (
        "mutual_information_mean_bits",
        "transfer_entropy_mean_bits",
        "transfer_entropy_asymmetry_mean_bits",
        "granger_log_variance_ratio_mean",
    ),
}


def cached_features(
    recording,
    checkpoint: Path,
    resume: bool,
) -> dict:
    if resume and checkpoint.exists():
        row = json.loads(checkpoint.read_text(encoding="utf-8"))
        if float(row.get("feature_schema_version", 0)) >= 2.0:
            print(f"[resume feature] {checkpoint.stem}", flush=True)
            return row
    row = extract_features(recording)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text(json.dumps(row, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[checkpoint feature] {checkpoint.stem}", flush=True)
    return row


def clustered_auc_interval(table: pd.DataFrame, iterations: int = 2000, seed: int = 42) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    source_ids = table["source_id"].unique()
    aucs: list[float] = []
    for _ in range(iterations):
        sampled = rng.choice(source_ids, size=len(source_ids), replace=True)
        boot = pd.concat([table.loc[table["source_id"] == source_id] for source_id in sampled], ignore_index=True)
        if boot["label"].nunique() == 2:
            aucs.append(roc_auc_score(boot["label"], boot["anomaly_percentile"]))
    return float(np.percentile(aucs, 2.5)), float(np.percentile(aucs, 97.5))


def main() -> int:
    parser = argparse.ArgumentParser(description="Train and validate the functional phenotype model")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "interim" / "zenodo_20286251" / "individual",
    )
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "artifacts" / "results" / "phenotype")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = sorted(args.input_dir.glob("*.mat"))
    if len(paths) < 10:
        raise RuntimeError(f"Expected at least 10 recordings, found {len(paths)}")
    recordings = [read_recording(path) for path in paths]
    checkpoint_dir = args.output_dir / "checkpoints" / "feature_schema_2"
    clean_rows = [
        cached_features(recording, checkpoint_dir / f"{recording.recording_id}__clean.json", args.resume)
        | {"fs_id": recording.metadata.get("fs_id")}
        for recording in recordings
    ]
    clean = pd.DataFrame(clean_rows)
    groups = clean["fs_id"].astype(str).to_numpy()
    unique_groups = np.unique(groups)
    splits = min(5, unique_groups.size)
    predictions: list[dict] = []
    ablation_predictions: dict[str, list[dict[str, float | int]]] = {name: [] for name in FEATURE_SETS}
    for fold, (train_index, test_index) in enumerate(GroupKFold(n_splits=splits).split(clean, groups=groups), start=1):
        test_rows: list[dict] = []
        for index in test_index:
            recording = recordings[int(index)]
            test_rows.append(clean_rows[int(index)] | {"label": 0, "perturbation": "clean", "source_id": recording.recording_id})
            for offset, kind in enumerate(PERTURBATIONS, start=1):
                seed = fold * 10000 + int(index) * 10 + offset
                perturbed = perturb_recording(recording, kind, seed=seed)
                feature_row = cached_features(
                    perturbed,
                    checkpoint_dir / f"{recording.recording_id}__{kind}__seed{seed}.json",
                    args.resume,
                )
                test_rows.append(feature_row | {"label": 1, "perturbation": kind, "source_id": recording.recording_id})
        test = pd.DataFrame(test_rows)
        model = fit_phenotype_model(clean.iloc[train_index], random_state=100 + fold)
        scores = model.transform(test)
        for row, score in zip(test.to_dict("records"), scores.to_dict("records"), strict=True):
            predictions.append(
                {
                    "fold": fold,
                    "source_id": row["source_id"],
                    "recording_id": row["recording_id"],
                    "perturbation": row["perturbation"],
                    "label": row["label"],
                    "anomaly_percentile": score["anomaly_percentile"],
                    "anomaly_raw": score["anomaly_raw"],
                }
            )
        for name, feature_names in FEATURE_SETS.items():
            available = [feature for feature in feature_names if feature in clean.columns and clean[feature].nunique() > 1]
            if len(available) < 2:
                continue
            ablation_model = fit_phenotype_model(
                clean.iloc[train_index],
                random_state=100 + fold,
                feature_names=available,
            )
            ablation_scores = ablation_model.transform(test)
            for label, score in zip(test["label"], ablation_scores["anomaly_percentile"], strict=True):
                ablation_predictions[name].append({"fold": fold, "label": int(label), "score": float(score)})
        print(f"[fold {fold}/{splits}] train={len(train_index)} test={len(test_index)}", flush=True)
    prediction_table = pd.DataFrame(predictions)
    labels = prediction_table["label"].to_numpy(int)
    scores = prediction_table["anomaly_percentile"].to_numpy(float)
    auc_low, auc_high = clustered_auc_interval(prediction_table)
    per_perturbation_auc = {}
    for kind in PERTURBATIONS:
        subset = prediction_table[prediction_table["perturbation"].isin(["clean", kind])]
        per_perturbation_auc[kind] = float(roc_auc_score(subset["label"], subset["anomaly_percentile"]))
    threshold_sensitivity = {
        f"p{threshold:g}": float(balanced_accuracy_score(labels, scores >= threshold))
        for threshold in (90.0, 95.0, 97.5)
    }
    fold_auc = {
        str(fold): float(roc_auc_score(group["label"], group["anomaly_percentile"]))
        for fold, group in prediction_table.groupby("fold")
    }
    ablation_rows = []
    for name, rows in ablation_predictions.items():
        if not rows:
            continue
        table = pd.DataFrame(rows)
        ablation_rows.append(
            {
                "feature_set": name,
                "n_features": len([feature for feature in FEATURE_SETS[name] if feature in clean.columns]),
                "roc_auc": float(roc_auc_score(table["label"], table["score"])),
            }
        )
    metrics = {
        "n_reference_recordings": len(clean),
        "n_unique_fs_groups": int(unique_groups.size),
        "cross_validation": f"{splits}-fold GroupKFold by fs_id",
        "roc_auc": float(roc_auc_score(labels, scores)),
        "roc_auc_cluster_bootstrap_95ci": [auc_low, auc_high],
        "average_precision": float(average_precision_score(labels, scores)),
        "balanced_accuracy_at_95th_percentile": float(balanced_accuracy_score(labels, scores >= 95.0)),
        "threshold_sensitivity_balanced_accuracy": threshold_sensitivity,
        "fold_roc_auc": fold_auc,
        "per_perturbation_auc": per_perturbation_auc,
        "perturbations": list(PERTURBATIONS),
        "feature_names": list(PHENOTYPE_FEATURES),
        "feature_schema_version": 2.0,
        "explanation": "Monte Carlo single-reference Shapley values relative to the robust training median.",
        "advanced_feature_policy": (
            "Stability, avalanche, and information-flow descriptors are reported, but the validated 18-feature "
            "model is retained because the 30-feature exploratory model reduced grouped-CV AUROC."
        ),
        "scope": "Synthetic event-level perturbation detection; not clinical or raw-waveform validation.",
    }
    full_model = fit_phenotype_model(clean)
    model_dir = PROJECT_ROOT / "artifacts" / "models"
    full_model.save(model_dir / "phenotype_model.joblib")
    clean_scores = full_model.transform(clean)
    clean.merge(clean_scores, on="recording_id").to_csv(args.output_dir / "reference_phenotypes.csv", index=False)
    prediction_table.to_csv(args.output_dir / "cross_validation_predictions.csv", index=False)
    pd.DataFrame(ablation_rows).to_csv(args.output_dir / "ablation.csv", index=False)
    pca_loading_table(full_model).to_csv(args.output_dir / "pca_loadings.csv", index=False)
    (args.output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
