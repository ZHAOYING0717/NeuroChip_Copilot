from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import RobustScaler


NON_FEATURE_COLUMNS = {
    "recording_id",
    "source_path",
    "source_format",
    "source_file",
    "source_folder",
    "file_format",
    "fs_id",
    "org_id",
    "parent_recording_id",
    "perturbation",
    "dose_um",
    "group_id",
}

PHENOTYPE_FEATURES_V1 = (
    "firing_rate_mean_hz",
    "firing_rate_median_hz",
    "firing_rate_std_hz",
    "firing_rate_max_hz",
    "firing_rate_cv",
    "active_channel_fraction",
    "dominant_channel_fraction",
    "isi_median_s",
    "isi_cv_mean",
    "sttc_mean",
    "sttc_median",
    "sttc_max",
    "network_density",
    "network_clustering",
    "population_entropy",
    "network_burst_rate_per_min",
    "network_burst_mean_duration_s",
    "network_burst_participation",
)

PHENOTYPE_FEATURES_EXTENDED = PHENOTYPE_FEATURES_V1 + (
    "firing_stability_cv",
    "activity_decay_log2_ratio",
    "activity_trend_normalized_slope",
    "avalanche_rate_per_min",
    "avalanche_size_mean",
    "avalanche_size_cv",
    "avalanche_branching_ratio",
    "avalanche_criticality_distance",
    "mutual_information_mean_bits",
    "transfer_entropy_mean_bits",
    "transfer_entropy_asymmetry_mean_bits",
    "granger_log_variance_ratio_mean",
)

# The validated anomaly model remains low-dimensional; advanced descriptors are
# reported separately until a larger independent reference cohort is available.
PHENOTYPE_FEATURES = PHENOTYPE_FEATURES_V1


def select_feature_columns(table: pd.DataFrame) -> list[str]:
    columns: list[str] = []
    for column in PHENOTYPE_FEATURES:
        if column not in table.columns:
            continue
        if column in NON_FEATURE_COLUMNS:
            continue
        values = pd.to_numeric(table[column], errors="coerce")
        if values.notna().sum() >= max(3, int(len(table) * 0.5)) and values.nunique(dropna=True) > 1:
            columns.append(column)
    return columns


def _percentile(reference: np.ndarray, values: np.ndarray) -> np.ndarray:
    ordered = np.sort(np.asarray(reference, dtype=float))
    return np.searchsorted(ordered, values, side="right") / max(ordered.size, 1) * 100.0


@dataclass
class PhenotypeModel:
    feature_names: list[str]
    imputer: SimpleImputer
    scaler: RobustScaler
    pca: PCA
    detector: IsolationForest
    component_sign: float
    reference_component: np.ndarray
    reference_anomaly: np.ndarray

    def transform(self, table: pd.DataFrame) -> pd.DataFrame:
        matrix = table.reindex(columns=self.feature_names).apply(pd.to_numeric, errors="coerce")
        scaled = self.scaler.transform(self.imputer.transform(matrix))
        components = self.pca.transform(scaled)
        phenotype_axis = components[:, 0] * self.component_sign
        anomaly_raw = -self.detector.score_samples(scaled)
        return pd.DataFrame(
            {
                "recording_id": table.get("recording_id", pd.Series(range(len(table)))).astype(str).to_numpy(),
                "functional_phenotype_index": _percentile(self.reference_component, phenotype_axis),
                "anomaly_percentile": _percentile(self.reference_anomaly, anomaly_raw),
                "anomaly_raw": anomaly_raw,
                "pc1": components[:, 0],
                "pc2": components[:, 1] if components.shape[1] > 1 else np.zeros(len(table)),
            }
        )

    def explain(
        self,
        table: pd.DataFrame,
        n_permutations: int = 128,
        random_state: int = 42,
    ) -> pd.DataFrame:
        """Estimate single-reference Shapley values for the anomaly score."""

        if n_permutations < 1:
            raise ValueError("n_permutations must be positive")
        matrix = table.reindex(columns=self.feature_names).apply(pd.to_numeric, errors="coerce")
        imputed = self.imputer.transform(matrix)
        scaled = self.scaler.transform(imputed)
        reference = np.zeros(len(self.feature_names), dtype=float)
        baseline_anomaly = float(-self.detector.score_samples(reference.reshape(1, -1))[0])
        rng = np.random.default_rng(random_state)
        rows: list[dict[str, float | str]] = []
        for row_index, sample in enumerate(scaled):
            permutations = np.asarray(
                [rng.permutation(len(self.feature_names)) for _ in range(n_permutations)],
                dtype=int,
            )
            states = np.repeat(reference[None, None, :], n_permutations, axis=0)
            states = np.repeat(states, len(self.feature_names) + 1, axis=1)
            for permutation_index, permutation in enumerate(permutations):
                current = reference.copy()
                for step, feature_index in enumerate(permutation, start=1):
                    current = current.copy()
                    current[feature_index] = sample[feature_index]
                    states[permutation_index, step] = current
            anomaly_path = -self.detector.score_samples(states.reshape(-1, len(self.feature_names)))
            anomaly_path = anomaly_path.reshape(n_permutations, len(self.feature_names) + 1)
            increments = np.diff(anomaly_path, axis=1)
            contributions = np.zeros(len(self.feature_names), dtype=float)
            for permutation, values in zip(permutations, increments, strict=True):
                contributions[permutation] += values
            contributions /= n_permutations
            phenotype_contributions = sample * self.pca.components_[0] * self.component_sign
            recording_id = str(table.iloc[row_index].get("recording_id", row_index))
            sample_anomaly = float(-self.detector.score_samples(sample.reshape(1, -1))[0])
            for feature_index, feature_name in enumerate(self.feature_names):
                rows.append(
                    {
                        "recording_id": recording_id,
                        "feature": feature_name,
                        "value": float(imputed[row_index, feature_index]),
                        "scaled_value": float(sample[feature_index]),
                        "anomaly_shap_value": float(contributions[feature_index]),
                        "phenotype_axis_contribution": float(phenotype_contributions[feature_index]),
                        "baseline_anomaly_raw": baseline_anomaly,
                        "sample_anomaly_raw": sample_anomaly,
                        "explanation_method": "Monte Carlo single-reference Shapley; robust-median reference",
                    }
                )
        return pd.DataFrame(rows)

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, target)

    @classmethod
    def load(cls, path: str | Path) -> "PhenotypeModel":
        model = joblib.load(path)
        if not isinstance(model, cls):
            raise TypeError("Model file does not contain a PhenotypeModel")
        return model


def fit_phenotype_model(
    table: pd.DataFrame,
    random_state: int = 42,
    feature_names: list[str] | tuple[str, ...] | None = None,
) -> PhenotypeModel:
    features = list(feature_names) if feature_names is not None else select_feature_columns(table)
    missing = set(features).difference(table.columns)
    if missing:
        raise ValueError(f"Missing phenotype features: {', '.join(sorted(missing))}")
    if len(features) < 2:
        raise ValueError("At least two varying numeric features are required")
    matrix = table[features].apply(pd.to_numeric, errors="coerce")
    imputer = SimpleImputer(strategy="median")
    scaler = RobustScaler(quantile_range=(10, 90))
    scaled = scaler.fit_transform(imputer.fit_transform(matrix))
    components = min(5, scaled.shape[0] - 1, scaled.shape[1])
    pca = PCA(n_components=max(2, components), random_state=random_state).fit(scaled)
    scores = pca.transform(scaled)
    detector = IsolationForest(
        n_estimators=500,
        contamination="auto",
        max_samples="auto",
        random_state=random_state,
    ).fit(scaled)
    anchors = [name for name in ("firing_rate_mean_hz", "active_channel_fraction", "sttc_mean", "network_burst_rate_per_min") if name in features]
    anchor_values = np.nanmean(
        np.column_stack([pd.to_numeric(table[name], errors="coerce").to_numpy(float) for name in anchors]), axis=1
    ) if anchors else np.arange(len(table), dtype=float)
    correlation = np.corrcoef(scores[:, 0], np.nan_to_num(anchor_values, nan=np.nanmedian(anchor_values)))[0, 1]
    component_sign = 1.0 if np.isfinite(correlation) and correlation >= 0 else -1.0
    return PhenotypeModel(
        feature_names=features,
        imputer=imputer,
        scaler=scaler,
        pca=pca,
        detector=detector,
        component_sign=component_sign,
        reference_component=scores[:, 0] * component_sign,
        reference_anomaly=-detector.score_samples(scaled),
    )


def pca_loading_table(model: PhenotypeModel) -> pd.DataFrame:
    rows = []
    for component_index, values in enumerate(model.pca.components_, start=1):
        for name, value in zip(model.feature_names, values, strict=True):
            rows.append({"component": f"PC{component_index}", "feature": name, "loading": float(value)})
    return pd.DataFrame(rows)
