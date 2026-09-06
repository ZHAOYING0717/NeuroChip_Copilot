import numpy as np
import pandas as pd

from neurochip.modeling import fit_phenotype_model, select_feature_columns


def test_phenotype_model_scores_rows():
    rng = np.random.default_rng(4)
    table = pd.DataFrame(
        {
            "recording_id": [f"r{i}" for i in range(20)],
            "firing_rate_mean_hz": rng.normal(1, 0.2, 20),
            "active_channel_fraction": rng.uniform(0.6, 1.0, 20),
            "sttc_mean": rng.uniform(0.05, 0.4, 20),
            "network_burst_rate_per_min": rng.uniform(0.2, 3.0, 20),
            "population_entropy": rng.uniform(0.3, 0.9, 20),
        }
    )
    model = fit_phenotype_model(table)
    scored = model.transform(table)
    assert len(scored) == len(table)
    assert scored["anomaly_percentile"].between(0, 100).all()
    assert scored["functional_phenotype_index"].between(0, 100).all()
    explanation = model.explain(table.iloc[[0]], n_permutations=32)
    observed_difference = explanation["sample_anomaly_raw"].iloc[0] - explanation["baseline_anomaly_raw"].iloc[0]
    assert np.isclose(explanation["anomaly_shap_value"].sum(), observed_difference)
    assert explanation["explanation_method"].str.contains("Shapley").all()


def test_phenotype_features_exclude_acquisition_and_qc_columns():
    table = pd.DataFrame(
        {
            "duration_s": [100, 200, 300],
            "total_spikes": [10, 20, 30],
            "event_quality_score": [80, 90, 100],
            "amplitude_median": [1, 2, 3],
            "firing_rate_mean_hz": [0.1, 0.2, 0.3],
            "sttc_mean": [0.01, 0.02, 0.03],
        }
    )
    assert select_feature_columns(table) == ["firing_rate_mean_hz", "sttc_mean"]
