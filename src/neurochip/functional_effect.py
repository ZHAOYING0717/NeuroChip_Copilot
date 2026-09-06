from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Mapping

import numpy as np
import pandas as pd

from .modeling import PhenotypeModel


GOAL_LABELS = {
    "quantify_only": "仅量化影响",
    "reduce_hyperactivity": "降低过度活动与爆发",
    "increase_hypoactivity": "增强低活动网络",
    "reduce_hypersynchrony": "降低过度同步",
    "preserve_function": "保持功能稳定与安全",
    "toward_reference": "向参考功能状态靠近",
}

DOMAIN_FEATURES = {
    "activity": (
        "firing_rate_mean_hz",
        "firing_rate_median_hz",
        "firing_rate_std_hz",
        "firing_rate_max_hz",
        "firing_rate_cv",
        "active_channel_fraction",
        "dominant_channel_fraction",
    ),
    "timing": ("isi_median_s", "isi_cv_mean"),
    "synchrony_network": (
        "sttc_mean",
        "sttc_median",
        "sttc_max",
        "network_density",
        "network_clustering",
    ),
    "organization": ("population_entropy",),
    "bursting": (
        "network_burst_rate_per_min",
        "network_burst_mean_duration_s",
        "network_burst_participation",
    ),
}

ADVANCED_DOMAIN_FEATURES = {
    "stability": (
        "firing_stability_cv",
        "activity_decay_log2_ratio",
        "activity_trend_normalized_slope",
    ),
    "criticality": (
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

DOMAIN_LABELS = {
    "activity": "活动水平",
    "timing": "放电时序",
    "synchrony_network": "同步与网络",
    "organization": "活动组织",
    "bursting": "网络爆发",
    "stability": "记录稳定性",
    "criticality": "雪崩与临界性",
    "information_flow": "信息流",
}

FEATURE_LABELS = {
    "firing_rate_mean_hz": "平均放电率",
    "firing_rate_median_hz": "放电率中位数",
    "firing_rate_std_hz": "放电率离散度",
    "firing_rate_max_hz": "最大通道放电率",
    "firing_rate_cv": "通道放电率CV",
    "active_channel_fraction": "活跃通道比例",
    "dominant_channel_fraction": "优势通道占比",
    "isi_median_s": "ISI中位数",
    "isi_cv_mean": "ISI CV",
    "sttc_mean": "平均STTC",
    "sttc_median": "STTC中位数",
    "sttc_max": "最大STTC",
    "network_density": "网络密度",
    "network_clustering": "网络聚类",
    "population_entropy": "群体活动熵",
    "network_burst_rate_per_min": "网络爆发率",
    "network_burst_mean_duration_s": "网络爆发持续时间",
    "network_burst_participation": "网络爆发参与度",
    "firing_stability_cv": "时间稳定性CV",
    "activity_decay_log2_ratio": "首末活动变化",
    "activity_trend_normalized_slope": "活动趋势斜率",
    "avalanche_rate_per_min": "雪崩率",
    "avalanche_size_mean": "雪崩平均大小",
    "avalanche_size_cv": "雪崩大小CV",
    "avalanche_branching_ratio": "雪崩分支比",
    "avalanche_criticality_distance": "临界点距离",
    "mutual_information_mean_bits": "互信息",
    "transfer_entropy_mean_bits": "传递熵",
    "transfer_entropy_asymmetry_mean_bits": "传递熵不对称性",
    "granger_log_variance_ratio_mean": "预测性Granger指标",
}

GOAL_DIRECTIONS = {
    "reduce_hyperactivity": {
        "firing_rate_mean_hz": -1,
        "firing_rate_median_hz": -1,
        "firing_rate_max_hz": -1,
        "dominant_channel_fraction": -1,
        "isi_median_s": 1,
        "isi_cv_mean": -1,
        "network_burst_rate_per_min": -1,
        "network_burst_mean_duration_s": -1,
    },
    "increase_hypoactivity": {
        "firing_rate_mean_hz": 1,
        "firing_rate_median_hz": 1,
        "active_channel_fraction": 1,
        "isi_median_s": -1,
        "network_burst_rate_per_min": 1,
        "network_burst_participation": 1,
    },
    "reduce_hypersynchrony": {
        "sttc_mean": -1,
        "sttc_median": -1,
        "sttc_max": -1,
        "network_density": -1,
        "network_clustering": -1,
        "network_burst_participation": -1,
    },
}


@dataclass(frozen=True)
class FunctionalEffectEvaluation:
    summary: dict[str, float | str | bool | None]
    feature_table: pd.DataFrame
    domain_table: pd.DataFrame
    advanced_table: pd.DataFrame


def _numeric(features: Mapping[str, float | str], name: str) -> float:
    value = pd.to_numeric(pd.Series([features.get(name, np.nan)]), errors="coerce").iloc[0]
    return float(value) if pd.notna(value) else float("nan")


def _scaled_vector(features: Mapping[str, float | str], model: PhenotypeModel) -> np.ndarray:
    row = pd.DataFrame([features]).reindex(columns=model.feature_names).apply(pd.to_numeric, errors="coerce")
    return model.scaler.transform(model.imputer.transform(row))[0]


def _symmetric_change(baseline: float, treatment: float) -> float:
    if not np.isfinite(baseline) or not np.isfinite(treatment):
        return float("nan")
    denominator = abs(baseline) + abs(treatment)
    return float(2.0 * (treatment - baseline) / denominator) if denominator > 1e-12 else 0.0


def _change_direction(value: float, tolerance: float = 0.05) -> str:
    if not np.isfinite(value):
        return "不可用"
    if value > tolerance:
        return "升高"
    if value < -tolerance:
        return "降低"
    return "基本稳定"


def _silencing_risk(
    baseline: Mapping[str, float | str],
    treatment: Mapping[str, float | str],
) -> tuple[str, str]:
    baseline_rate = _numeric(baseline, "firing_rate_mean_hz")
    treatment_rate = _numeric(treatment, "firing_rate_mean_hz")
    baseline_active = _numeric(baseline, "active_channel_fraction")
    treatment_active = _numeric(treatment, "active_channel_fraction")
    rate_drop = 1.0 - treatment_rate / max(baseline_rate, 1e-12) if baseline_rate > 0 else 0.0
    active_drop = 1.0 - treatment_active / max(baseline_active, 1e-12) if baseline_active > 0 else 0.0
    if rate_drop >= 0.80 and (active_drop >= 0.50 or treatment_active < 0.10):
        return "high", "放电率下降至少80%，且活跃通道明显减少，可能是网络沉默或毒性抑制"
    if rate_drop >= 0.50 and (active_drop >= 0.25 or treatment_active < 0.20):
        return "moderate", "放电率和活跃通道同时下降，需要排查过度抑制"
    return "low", "未发现放电率与活跃通道同时崩落的模式"


def _evidence_grade(minimum_quality: float, changed_features: int) -> tuple[str, str]:
    if minimum_quality < 50:
        return "insufficient", "至少一份记录未通过事件质量门控，不应判断效应好坏"
    if minimum_quality < 75 or changed_features < 3:
        return "low", "单对记录且质量或多指标一致性有限，需要重复实验复核"
    return "moderate", "记录质量可接受，但只有单对记录，不能代替生物学重复和置信区间"


def _goal_alignment(goal: str, delta_by_feature: dict[str, float]) -> tuple[float | None, float | None]:
    directions = GOAL_DIRECTIONS.get(goal)
    if not directions:
        return None, None
    values = []
    weights = []
    for feature, desired_direction in directions.items():
        delta = delta_by_feature.get(feature, float("nan"))
        if np.isfinite(delta):
            values.append(float(desired_direction * delta))
            weights.append(abs(float(delta)))
    total = float(np.sum(weights))
    if total <= 1e-12:
        return 0.0, 50.0
    alignment = float(np.clip(np.sum(values) / total, -1.0, 1.0))
    return alignment, float((alignment + 1.0) * 50.0)


def evaluate_functional_effect(
    baseline: Mapping[str, float | str],
    treatment: Mapping[str, float | str],
    model: PhenotypeModel,
    *,
    goal: str = "quantify_only",
    baseline_quality: float = 100.0,
    treatment_quality: float = 100.0,
    reference: Mapping[str, float | str] | None = None,
    reference_label: str = "公共功能参考",
    recovery: Mapping[str, float | str] | None = None,
) -> FunctionalEffectEvaluation:
    if goal not in GOAL_LABELS:
        raise ValueError(f"Unknown functional-effect goal: {goal}")
    baseline_scaled = _scaled_vector(baseline, model)
    treatment_scaled = _scaled_vector(treatment, model)
    delta_scaled = treatment_scaled - baseline_scaled
    delta_by_feature = dict(zip(model.feature_names, delta_scaled, strict=True))
    impact_magnitude = float(np.sqrt(np.mean(np.square(delta_scaled))))

    feature_rows: list[dict[str, float | str | int]] = []
    feature_domain = {
        feature: domain for domain, features in DOMAIN_FEATURES.items() for feature in features
    }
    goal_directions = GOAL_DIRECTIONS.get(goal, {})
    for name, scaled_delta in zip(model.feature_names, delta_scaled, strict=True):
        baseline_value = _numeric(baseline, name)
        treatment_value = _numeric(treatment, name)
        symmetric_change = _symmetric_change(baseline_value, treatment_value)
        desired = int(goal_directions.get(name, 0))
        if desired == 0 or not np.isfinite(scaled_delta):
            alignment = "非目标指标"
        elif abs(scaled_delta) < 0.05:
            alignment = "变化很小"
        else:
            alignment = "符合目标" if desired * scaled_delta > 0 else "偏离目标"
        feature_rows.append(
            {
                "domain": feature_domain.get(name, "other"),
                "domain_label": DOMAIN_LABELS.get(feature_domain.get(name, "other"), "其他"),
                "feature": name,
                "feature_label": FEATURE_LABELS.get(name, name),
                "baseline": baseline_value,
                "treatment": treatment_value,
                "symmetric_change_percent": symmetric_change * 100.0,
                "robust_standardized_change": float(scaled_delta),
                "direction": _change_direction(float(scaled_delta)),
                "goal_alignment": alignment,
            }
        )
    feature_table = pd.DataFrame(feature_rows)

    domain_rows: list[dict[str, float | str]] = []
    for domain, names in DOMAIN_FEATURES.items():
        available = feature_table.loc[feature_table["feature"].isin(names)]
        values = available["robust_standardized_change"].to_numpy(float)
        domain_rows.append(
            {
                "domain": domain,
                "domain_label": DOMAIN_LABELS[domain],
                "impact_magnitude": float(np.sqrt(np.mean(np.square(values)))) if values.size else np.nan,
                "mean_signed_change": float(np.mean(values)) if values.size else np.nan,
                "dominant_direction": _change_direction(float(np.mean(values))) if values.size else "不可用",
                "n_features": int(values.size),
            }
        )
    domain_table = pd.DataFrame(domain_rows)

    advanced_rows: list[dict[str, float | str]] = []
    for domain, names in ADVANCED_DOMAIN_FEATURES.items():
        for name in names:
            baseline_value = _numeric(baseline, name)
            treatment_value = _numeric(treatment, name)
            change = _symmetric_change(baseline_value, treatment_value)
            advanced_rows.append(
                {
                    "domain": domain,
                    "domain_label": DOMAIN_LABELS[domain],
                    "feature": name,
                    "feature_label": FEATURE_LABELS.get(name, name),
                    "baseline": baseline_value,
                    "treatment": treatment_value,
                    "symmetric_change_percent": change * 100.0,
                    "direction": _change_direction(change),
                    "evidence_scope": "探索性，不参与效应好坏总分",
                }
            )
    advanced_table = pd.DataFrame(advanced_rows)

    alignment, goal_score = _goal_alignment(goal, delta_by_feature)
    reference_scaled = _scaled_vector(reference, model) if reference is not None else np.zeros_like(baseline_scaled)
    baseline_reference_distance = float(np.sqrt(np.mean(np.square(baseline_scaled - reference_scaled))))
    treatment_reference_distance = float(np.sqrt(np.mean(np.square(treatment_scaled - reference_scaled))))
    if baseline_reference_distance < 1e-9:
        reference_improvement_percent = 0.0 if treatment_reference_distance < 1e-9 else -100.0
    else:
        reference_improvement_percent = float(
            (baseline_reference_distance - treatment_reference_distance) / baseline_reference_distance * 100.0
        )
    if goal == "toward_reference":
        alignment = float(np.clip(reference_improvement_percent / 100.0, -1.0, 1.0))
        goal_score = float(np.clip(50.0 + reference_improvement_percent / 2.0, 0.0, 100.0))

    silencing_risk, silencing_note = _silencing_risk(baseline, treatment)
    changed_features = int(np.sum(np.abs(delta_scaled) >= 0.25))
    minimum_quality = float(min(baseline_quality, treatment_quality))
    evidence_grade, uncertainty_note = _evidence_grade(minimum_quality, changed_features)

    reversibility_percent: float | None = None
    recovery_distance: float | None = None
    reversibility_label = "未提供恢复记录"
    if recovery is not None:
        recovery_scaled = _scaled_vector(recovery, model)
        treatment_distance = float(np.sqrt(np.mean(np.square(treatment_scaled - baseline_scaled))))
        recovery_distance = float(np.sqrt(np.mean(np.square(recovery_scaled - baseline_scaled))))
        reversibility_percent = float(
            np.clip(1.0 - recovery_distance / max(treatment_distance, 1e-12), -1.0, 1.0) * 100.0
        )
        if reversibility_percent >= 50:
            reversibility_label = "明显恢复"
        elif reversibility_percent >= 15:
            reversibility_label = "部分恢复"
        elif reversibility_percent > -15:
            reversibility_label = "未见明确恢复"
        else:
            reversibility_label = "进一步偏离基线"

    if evidence_grade == "insufficient":
        verdict = "不宜判断"
    elif goal == "quantify_only":
        verdict = "仅量化变化"
    elif silencing_risk == "high":
        verdict = "可能不利：网络沉默风险"
    elif goal == "preserve_function":
        verdict = "符合稳定目标" if impact_magnitude < 0.25 else (
            "轻度偏离稳定目标" if impact_magnitude < 0.75 else "可能不利：功能变化明显"
        )
        goal_score = float(np.clip(100.0 - impact_magnitude * 50.0, 0.0, 100.0))
        alignment = float(np.clip(1.0 - impact_magnitude, -1.0, 1.0))
    elif alignment is not None and alignment >= 0.35 and impact_magnitude >= 0.25:
        verdict = "可能有益：变化符合所选目标"
    elif alignment is not None and alignment <= -0.35 and impact_magnitude >= 0.25:
        verdict = "可能不利：变化偏离所选目标"
    else:
        verdict = "效应混合或不明确"

    phenotype = model.transform(pd.DataFrame([baseline, treatment]))
    summary: dict[str, float | str | bool | None] = {
        "goal": goal,
        "goal_label": GOAL_LABELS[goal],
        "verdict": verdict,
        "impact_magnitude": impact_magnitude,
        "goal_alignment": alignment,
        "goal_alignment_score": goal_score,
        "silencing_risk": silencing_risk,
        "silencing_note": silencing_note,
        "minimum_event_quality_score": minimum_quality,
        "evidence_grade": evidence_grade,
        "uncertainty_note": uncertainty_note,
        "changed_features_over_0_25_robust_scale": changed_features,
        "reference_label": reference_label,
        "baseline_reference_distance": baseline_reference_distance,
        "treatment_reference_distance": treatment_reference_distance,
        "reference_improvement_percent": reference_improvement_percent,
        "phenotype_rescue_percent": reference_improvement_percent,
        "reversibility_percent": reversibility_percent,
        "recovery_distance_from_baseline": recovery_distance,
        "reversibility_label": reversibility_label,
        "baseline_anomaly_percentile": float(phenotype.iloc[0]["anomaly_percentile"]),
        "treatment_anomaly_percentile": float(phenotype.iloc[1]["anomaly_percentile"]),
        "interpretation_boundary": (
            "效应好坏仅相对于用户选择的目标；单对记录不能替代生物学重复。"
            "公共功能参考来自训练队列的稳健中心，不等同于临床健康标准。"
        ),
    }
    return FunctionalEffectEvaluation(summary, feature_table, domain_table, advanced_table)


def build_functional_effect_html(
    evaluation: FunctionalEffectEvaluation,
    *,
    baseline_name: str,
    treatment_name: str,
) -> str:
    summary = evaluation.summary

    def table_html(table: pd.DataFrame) -> str:
        return table.to_html(index=False, border=0, classes="data", float_format=lambda value: f"{value:.4f}")

    goal_score = summary["goal_alignment_score"]
    goal_score_label = f"{float(goal_score):.0f}/100" if goal_score is not None else "不适用"
    recovery_value = summary["reversibility_percent"]
    recovery_label = f"{float(recovery_value):+.1f}%" if recovery_value is not None else "未提供"
    domain_report = evaluation.domain_table.rename(
        columns={
            "domain_label": "功能维度",
            "impact_magnitude": "变化幅度",
            "mean_signed_change": "平均变化方向",
            "dominant_direction": "主要方向",
            "n_features": "指标数",
        }
    )[["功能维度", "变化幅度", "平均变化方向", "主要方向", "指标数"]]
    feature_report = evaluation.feature_table.rename(
        columns={
            "domain_label": "功能维度",
            "feature_label": "指标",
            "baseline": "基线",
            "treatment": "处理后",
            "symmetric_change_percent": "对称变化率(%)",
            "robust_standardized_change": "稳健标准化变化",
            "direction": "方向",
            "goal_alignment": "目标关系",
        }
    )[["功能维度", "指标", "基线", "处理后", "对称变化率(%)", "稳健标准化变化", "方向", "目标关系"]]
    advanced_report = evaluation.advanced_table.rename(
        columns={
            "domain_label": "功能维度",
            "feature_label": "指标",
            "baseline": "基线",
            "treatment": "处理后",
            "symmetric_change_percent": "对称变化率(%)",
            "direction": "方向",
            "evidence_scope": "证据范围",
        }
    )[["功能维度", "指标", "基线", "处理后", "对称变化率(%)", "方向", "证据范围"]]

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>NeuroChip多维功能效应报告</title>
<style>
body{{font-family:Arial,'Microsoft YaHei',sans-serif;color:#20262a;margin:32px;line-height:1.55}}
h1{{font-size:24px}} h2{{font-size:17px;color:#147f7a;margin-top:26px}}
.summary{{display:grid;grid-template-columns:repeat(3,minmax(160px,1fr));gap:10px}}
.item{{border:1px solid #d9dee2;padding:12px;border-radius:6px}}
.label{{color:#667078;font-size:12px}} .value{{font-weight:700;font-size:18px}}
table.data{{border-collapse:collapse;width:100%;font-size:12px}} table.data th,table.data td{{border-bottom:1px solid #e3e7e9;padding:6px;text-align:right}}
table.data th:first-child,table.data td:first-child{{text-align:left}} .note{{color:#667078;font-size:12px}}
</style></head><body>
<h1>NeuroChip多维功能效应报告</h1>
<p>基线：{escape(baseline_name)}<br>处理：{escape(treatment_name)}</p>
<div class="summary">
<div class="item"><div class="label">目标相关结论</div><div class="value">{escape(str(summary['verdict']))}</div></div>
<div class="item"><div class="label">多维影响幅度</div><div class="value">{float(summary['impact_magnitude']):.2f}</div></div>
<div class="item"><div class="label">目标一致性</div><div class="value">{goal_score_label}</div></div>
<div class="item"><div class="label">网络沉默风险</div><div class="value">{escape(str(summary['silencing_risk']))}</div></div>
<div class="item"><div class="label">证据等级</div><div class="value">{escape(str(summary['evidence_grade']))}</div></div>
<div class="item"><div class="label">可逆性/恢复程度</div><div class="value">{recovery_label}</div></div>
</div>
<h2>参考与恢复</h2>
<p>评价目标：{escape(str(summary['goal_label']))}<br>
参考来源：{escape(str(summary['reference_label']))}<br>
基线距参考：{float(summary['baseline_reference_distance']):.3f}；处理后距参考：{float(summary['treatment_reference_distance']):.3f}；向参考变化：{float(summary['reference_improvement_percent']):+.1f}%<br>
恢复判断：{escape(str(summary['reversibility_label']))}</p>
<h2>维度汇总</h2>{table_html(domain_report)}
<h2>验证特征变化</h2>{table_html(feature_report)}
<h2>探索性特征</h2>{table_html(advanced_report)}
<h2>风险与解释边界</h2><p class="note">{escape(str(summary['silencing_note']))}<br>{escape(str(summary['interpretation_boundary']))}<br>{escape(str(summary['uncertainty_note']))}</p>
</body></html>"""
