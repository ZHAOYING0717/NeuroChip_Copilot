import numpy as np
import pandas as pd

from neurochip.drug_response import fit_drug_response_model, paired_feature_deltas


def response_table() -> pd.DataFrame:
    rows = []
    for group_id, offset in [("a", 0.0), ("b", 0.1), ("c", -0.1)]:
        for dose in (0.0, 3.0, 10.0, 50.0):
            strength = np.log1p(dose) / np.log(51)
            rows.append(
                {
                    "recording_id": f"{group_id}-{dose:g}",
                    "group_id": group_id,
                    "dose_um": dose,
                    "isi_cv_mean": 1.5 + offset - 0.6 * strength,
                    "isi_median_s": 0.2 + offset / 10 + 0.4 * strength,
                    "network_burst_mean_duration_s": 0.5 + offset / 10 - 0.2 * strength,
                }
            )
    return pd.DataFrame(rows)


def test_paired_deltas_are_zero_for_controls():
    paired = paired_feature_deltas(response_table())
    controls = paired.loc[paired["dose_um"] == 0]
    assert np.allclose(controls.filter(like="delta_log__").to_numpy(float), 0)


def test_response_model_scores_monotonic_synthetic_doses():
    table = response_table()
    model = fit_drug_response_model(table)
    scored = model.transform(table)
    for _, group in scored.groupby("group_id"):
        assert np.all(np.diff(group.sort_values("dose_um")["response_magnitude"]) >= 0)
    assert scored["response_percentile"].between(0, 100).all()


def test_score_pair_matches_table_transform():
    table = response_table()
    model = fit_drug_response_model(table)
    group = table.loc[table["group_id"] == "a"].sort_values("dose_um")
    expected = model.transform(group).iloc[-1]
    actual = model.score_pair(group.iloc[-1], group.iloc[0])
    assert np.isclose(actual["response_magnitude"], expected["response_magnitude"])
    explanation = model.explain_pair(group.iloc[-1], group.iloc[0])
    assert np.isclose(explanation["response_squared_contribution_fraction"].sum(), 1.0)
