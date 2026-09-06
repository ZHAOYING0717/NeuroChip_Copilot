import numpy as np
import pandas as pd

from neurochip.functional_effect import build_functional_effect_html, evaluate_functional_effect
from neurochip.modeling import PHENOTYPE_FEATURES, fit_phenotype_model


def reference_table() -> pd.DataFrame:
    rows = []
    for index in range(20):
        row = {name: 1.0 + index * 0.02 for name in PHENOTYPE_FEATURES}
        row.update(
            {
                "recording_id": f"r{index}",
                "firing_rate_mean_hz": 4.0 + index * 0.1,
                "firing_rate_median_hz": 3.0 + index * 0.08,
                "firing_rate_max_hz": 8.0 + index * 0.2,
                "active_channel_fraction": 0.75 + index * 0.005,
                "isi_median_s": 0.20 - index * 0.002,
                "network_burst_rate_per_min": 5.0 + index * 0.1,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def feature_row(**updates) -> dict:
    row = reference_table().iloc[10].to_dict()
    row.update(
        {
            "firing_stability_cv": 0.2,
            "activity_decay_log2_ratio": 0.0,
            "activity_trend_normalized_slope": 0.0,
            "avalanche_rate_per_min": 2.0,
            "avalanche_size_mean": 10.0,
            "avalanche_size_cv": 0.8,
            "avalanche_branching_ratio": 1.0,
            "avalanche_criticality_distance": 0.0,
            "mutual_information_mean_bits": 0.02,
            "transfer_entropy_mean_bits": 0.01,
            "transfer_entropy_asymmetry_mean_bits": 0.002,
            "granger_log_variance_ratio_mean": 0.03,
        }
    )
    row.update(updates)
    return row


def test_hyperactivity_goal_reports_aligned_reduction():
    model = fit_phenotype_model(reference_table())
    baseline = feature_row(firing_rate_mean_hz=9.0, firing_rate_median_hz=7.0, network_burst_rate_per_min=10.0)
    treatment = feature_row(firing_rate_mean_hz=5.0, firing_rate_median_hz=4.0, network_burst_rate_per_min=5.0)
    result = evaluate_functional_effect(
        baseline,
        treatment,
        model,
        goal="reduce_hyperactivity",
        baseline_quality=90,
        treatment_quality=90,
    )
    assert result.summary["goal_alignment_score"] > 50
    assert "可能有益" in result.summary["verdict"]
    assert len(result.domain_table) == 5
    assert set(result.advanced_table["domain"]) == {"stability", "criticality", "information_flow"}


def test_network_silencing_overrides_apparent_target_alignment():
    model = fit_phenotype_model(reference_table())
    baseline = feature_row(firing_rate_mean_hz=9.0, active_channel_fraction=0.8)
    treatment = feature_row(firing_rate_mean_hz=0.5, active_channel_fraction=0.05)
    result = evaluate_functional_effect(
        baseline,
        treatment,
        model,
        goal="reduce_hyperactivity",
        baseline_quality=90,
        treatment_quality=90,
    )
    assert result.summary["silencing_risk"] == "high"
    assert "可能不利" in result.summary["verdict"]


def test_reference_improvement_and_recovery_are_quantified():
    reference = reference_table()
    model = fit_phenotype_model(reference)
    target = reference.iloc[10].to_dict()
    baseline = feature_row(firing_rate_mean_hz=10.0, firing_rate_median_hz=8.0)
    treatment = feature_row(firing_rate_mean_hz=6.0, firing_rate_median_hz=5.0)
    recovery = feature_row(firing_rate_mean_hz=9.0, firing_rate_median_hz=7.5)
    result = evaluate_functional_effect(
        baseline,
        treatment,
        model,
        goal="toward_reference",
        reference=target,
        recovery=recovery,
    )
    assert result.summary["reference_improvement_percent"] > 0
    assert np.isfinite(result.summary["reversibility_percent"])
    assert result.summary["reversibility_label"] != "未提供恢复记录"


def test_failed_quality_blocks_good_bad_verdict():
    model = fit_phenotype_model(reference_table())
    result = evaluate_functional_effect(
        feature_row(),
        feature_row(firing_rate_mean_hz=7.0),
        model,
        goal="increase_hypoactivity",
        baseline_quality=45,
        treatment_quality=90,
    )
    assert result.summary["verdict"] == "不宜判断"
    assert result.summary["evidence_grade"] == "insufficient"


def test_quantify_only_report_uses_not_applicable_goal_score():
    model = fit_phenotype_model(reference_table())
    result = evaluate_functional_effect(feature_row(), feature_row(firing_rate_mean_hz=5.5), model)
    report = build_functional_effect_html(result, baseline_name="before.csv", treatment_name="after.csv")
    assert result.summary["goal_alignment_score"] is None
    assert "不适用" in report
    assert "公共功能参考" in report
    assert "辅助" not in result.summary["verdict"]
