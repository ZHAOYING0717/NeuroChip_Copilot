from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression


DRUG_RESPONSE_FEATURES_V1 = (
    "isi_cv_mean",
    "isi_median_s",
    "network_burst_mean_duration_s",
)

DRUG_RESPONSE_FEATURES = (
    "isi_cv_mean",
    "isi_median_s",
)


def _signed_log1p(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    return np.sign(array) * np.log1p(np.abs(array))


def paired_feature_deltas(
    table: pd.DataFrame,
    feature_names: tuple[str, ...] = DRUG_RESPONSE_FEATURES,
    group_column: str = "group_id",
    dose_column: str = "dose_um",
) -> pd.DataFrame:
    missing = set(feature_names).union({group_column, dose_column}).difference(table.columns)
    if missing:
        raise ValueError(f"Missing paired-response columns: {', '.join(sorted(missing))}")
    rows: list[dict[str, float | str]] = []
    for group_id, group in table.groupby(group_column, sort=False):
        controls = group.loc[pd.to_numeric(group[dose_column], errors="coerce") == 0]
        if len(controls) != 1:
            raise ValueError(f"Group {group_id} must contain exactly one zero-dose control")
        control = controls.iloc[0]
        control_values = _signed_log1p(control.loc[list(feature_names)].to_numpy(float))
        for index, row in group.iterrows():
            values = _signed_log1p(row.loc[list(feature_names)].to_numpy(float))
            result: dict[str, float | str] = {
                "row_index": int(index),
                group_column: str(group_id),
                dose_column: float(row[dose_column]),
                "recording_id": str(row.get("recording_id", index)),
                "control_recording_id": str(control.get("recording_id", controls.index[0])),
            }
            result.update({f"delta_log__{name}": float(value) for name, value in zip(feature_names, values - control_values, strict=True)})
            rows.append(result)
    return pd.DataFrame(rows)


@dataclass
class DrugResponseModel:
    feature_names: tuple[str, ...]
    scales: np.ndarray
    calibrator: IsotonicRegression
    reference_magnitudes: np.ndarray

    @property
    def delta_columns(self) -> list[str]:
        return [f"delta_log__{name}" for name in self.feature_names]

    def transform(self, table: pd.DataFrame) -> pd.DataFrame:
        paired = paired_feature_deltas(table, self.feature_names)
        matrix = paired[self.delta_columns].to_numpy(float)
        magnitude = np.sqrt(np.mean(np.square(matrix / self.scales), axis=1))
        ordered = np.sort(self.reference_magnitudes)
        percentile = np.searchsorted(ordered, magnitude, side="right") / max(ordered.size, 1) * 100.0
        paired["response_magnitude"] = magnitude
        paired["response_percentile"] = percentile
        paired["predicted_dose_um_exploratory"] = self.calibrator.predict(magnitude)
        return paired

    def score_pair(self, sample: Mapping[str, float], control: Mapping[str, float]) -> dict[str, float]:
        sample_values = _signed_log1p(np.asarray([sample[name] for name in self.feature_names], dtype=float))
        control_values = _signed_log1p(np.asarray([control[name] for name in self.feature_names], dtype=float))
        delta = sample_values - control_values
        magnitude = float(np.sqrt(np.mean(np.square(delta / self.scales))))
        ordered = np.sort(self.reference_magnitudes)
        result = {
            f"delta_log__{name}": float(value)
            for name, value in zip(self.feature_names, delta, strict=True)
        }
        result.update(
            {
                "response_magnitude": magnitude,
                "response_percentile": float(np.searchsorted(ordered, magnitude, side="right") / max(ordered.size, 1) * 100.0),
                "predicted_dose_um_exploratory": float(self.calibrator.predict([magnitude])[0]),
            }
        )
        if "event_quality_score" in sample and "event_quality_score" in control:
            minimum_quality = float(min(sample["event_quality_score"], control["event_quality_score"]))
            result["pair_minimum_event_quality_score"] = minimum_quality
            result["pair_quality_gate_pass"] = float(minimum_quality >= 50.0)
        return result

    def explain_pair(self, sample: Mapping[str, float], control: Mapping[str, float]) -> pd.DataFrame:
        """Return exact per-feature contributions to the squared response magnitude."""

        score = self.score_pair(sample, control)
        deltas = np.asarray([score[f"delta_log__{name}"] for name in self.feature_names], dtype=float)
        standardized = deltas / self.scales
        squared = np.square(standardized)
        total = float(np.sum(squared))
        fractions = squared / total if total > 0 else np.zeros_like(squared)
        return pd.DataFrame(
            {
                "feature": self.feature_names,
                "control_value": [float(control[name]) for name in self.feature_names],
                "sample_value": [float(sample[name]) for name in self.feature_names],
                "delta_log": deltas,
                "standardized_delta": standardized,
                "response_squared_contribution_fraction": fractions,
            }
        )

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, target)

    @classmethod
    def load(cls, path: str | Path) -> "DrugResponseModel":
        model = joblib.load(path)
        if not isinstance(model, cls):
            raise TypeError("Model file does not contain a DrugResponseModel")
        return model


def fit_drug_response_model(
    table: pd.DataFrame,
    feature_names: tuple[str, ...] = DRUG_RESPONSE_FEATURES,
) -> DrugResponseModel:
    paired = paired_feature_deltas(table, feature_names)
    columns = [f"delta_log__{name}" for name in feature_names]
    matrix = paired[columns].to_numpy(float)
    quartiles = np.percentile(matrix, [25, 75], axis=0)
    scales = quartiles[1] - quartiles[0]
    standard_deviation = np.std(matrix, axis=0)
    scales = np.where(scales > 1e-8, scales, np.where(standard_deviation > 1e-8, standard_deviation, 1.0))
    magnitude = np.sqrt(np.mean(np.square(matrix / scales), axis=1))
    dose = paired["dose_um"].to_numpy(float)
    calibrator = IsotonicRegression(y_min=0.0, y_max=float(np.max(dose)), out_of_bounds="clip")
    calibrator.fit(magnitude, dose)
    return DrugResponseModel(feature_names, scales, calibrator, magnitude)
