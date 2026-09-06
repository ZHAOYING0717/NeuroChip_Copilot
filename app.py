from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from neurochip import assess_event_quality, extract_features, read_recording
from neurochip.cache_payload import recording_from_cache_payload, recording_to_cache_payload
from neurochip.drug_response import DrugResponseModel
from neurochip.evidence import load_evidence_ladder
from neurochip.functional_effect import GOAL_LABELS, build_functional_effect_html, evaluate_functional_effect
from neurochip.input_validation import InputValidationResult, validate_input_file
from neurochip.modeling import PhenotypeModel
from neurochip.project_store import ProjectStore
from neurochip.public_samples import (
    PublicPair,
    PublicSample,
    discover_public_pairs,
    discover_public_samples,
    load_public_sample,
)
from neurochip.report import build_html_report, build_pdf_report
from neurochip.visuals import channel_rate_figure, population_activity_figure, raster_figure, sttc_heatmap_figure


PROJECT_ROOT = Path(__file__).resolve().parent
DEMO_ONLY = os.environ.get("NEUROCHIP_DEMO_ONLY", "0") == "1"
PHENOTYPE_MODEL_PATH = PROJECT_ROOT / "models" / "phenotype_model.joblib"
DRUG_MODEL_PATH = PROJECT_ROOT / "models" / "drug_response_model.joblib"
UPLOAD_DIR = PROJECT_ROOT / "artifacts" / "uploads"
PROJECT_DATABASE_PATH = PROJECT_ROOT / "artifacts" / "projects" / "neurochip_projects.sqlite3"
PUBLIC_SAMPLE_GROUPS = discover_public_samples(PROJECT_ROOT, demo_only=DEMO_ONLY)
PUBLIC_PAIRS = discover_public_pairs(PUBLIC_SAMPLE_GROUPS)
PUBLIC_SAMPLES_BY_KEY = {
    sample.key: sample
    for samples in PUBLIC_SAMPLE_GROUPS.values()
    for sample in samples
}
PUBLIC_DATASET_TOTALS = {
    "前脑类器官参考": 45,
    "脑类器官地西泮": 19,
    "GIN二维神经网络": 198,
    "Trujillo皮层类器官": 72,
}
USING_LIGHTWEIGHT_PUBLIC_SAMPLES = bool(PUBLIC_SAMPLES_BY_KEY) and all(
    sample.key.startswith("demo:") for sample in PUBLIC_SAMPLES_BY_KEY.values()
)

REFERENCE_SCOPE_BY_DATASET = {
    "forebrain_reference": (
        "同域参考",
        "该记录来自模型的45条前脑类器官参考队列；两个分位数可按队列内相对位置解释。",
    ),
    "diazepam_organoid": (
        "类器官药理记录",
        "事件参数和质量控制可直接解释；分位数只表示相对前脑类器官参考队列的状态与偏离，不代表药效好坏。",
    ),
    "gin_comparative_mea": (
        "跨域二维神经元",
        "事件参数可直接分析；功能状态轴和参考偏离分位属于跨物种/二维培养探索，不用于健康或疾病判断。",
    ),
    "trujillo_cortical_organoid": (
        "外部类器官实验",
        "事件参数可直接分析；分位数属于跨实验室、跨方案探索，处理效应应在干预评价中与匹配基线比较。",
    ),
}

AnalysisSource = Path | PublicSample

st.set_page_config(page_title="NeuroChip Copilot", page_icon=None, layout="wide", initial_sidebar_state="auto")
st.markdown(
    """
    <style>
    :root { --ink:#20262a; --muted:#667078; --teal:#147f7a; --line:#d9dee2; --soft:#f4f6f7; }
    .stApp { background:#ffffff; color:var(--ink); }
    [data-testid="stSidebar"] { background:var(--soft); border-right:1px solid var(--line); }
    [data-testid="stMetric"] { border:1px solid var(--line); border-radius:6px; padding:10px 12px; background:#fff; min-height:92px; }
    [data-testid="stMetricLabel"] { color:var(--muted); }
    .block-container { padding-top:1.25rem; padding-bottom:2rem; max-width:1500px; }
    h1 { font-size:1.55rem !important; letter-spacing:0 !important; margin-bottom:0.1rem !important; }
    h2 { font-size:1.05rem !important; letter-spacing:0 !important; }
    h3 { font-size:0.92rem !important; letter-spacing:0 !important; }
    .scope { color:var(--muted); font-size:0.86rem; margin-bottom:0.9rem; }
    .status-pass { color:#147f7a; font-weight:650; }
    .status-review { color:#b77c14; font-weight:650; }
    .status-fail { color:#bd473e; font-weight:650; }
    button { border-radius:6px !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def load_phenotype_model() -> PhenotypeModel | None:
    return PhenotypeModel.load(PHENOTYPE_MODEL_PATH) if PHENOTYPE_MODEL_PATH.exists() else None


@st.cache_resource
def load_drug_model() -> DrugResponseModel | None:
    return DrugResponseModel.load(DRUG_MODEL_PATH) if DRUG_MODEL_PATH.exists() else None


@st.cache_resource
def load_project_store() -> ProjectStore:
    return ProjectStore(PROJECT_DATABASE_PATH)


@st.cache_data(show_spinner=False)
def analyze_path(path_string: str, modified_ns: int, duration_s: float | None = None):
    del modified_ns
    recording = read_recording(path_string, duration_s=duration_s)
    return analysis_to_cache_payload(analyze_recording(recording))


def analyze_recording(recording):
    features = extract_features(recording)
    quality, channels = assess_event_quality(recording)
    model = load_phenotype_model()
    model_result = model.transform(pd.DataFrame([features])).iloc[0].to_dict() if model is not None else None
    deviations: list[dict[str, float | str]] = []
    explanation = pd.DataFrame()
    if model is not None:
        row = pd.DataFrame([features]).reindex(columns=model.feature_names).apply(pd.to_numeric, errors="coerce")
        scaled = model.scaler.transform(model.imputer.transform(row))[0]
        indices = np.argsort(np.abs(scaled))[::-1][:6]
        deviations = [
            {
                "指标": model.feature_names[index],
                "稳健尺度偏离": float(scaled[index]),
                "方向": "偏高" if scaled[index] >= 0 else "偏低",
            }
            for index in indices
        ]
        explanation = model.explain(pd.DataFrame([features]), n_permutations=64)
    return recording, features, quality, channels, model_result, deviations, explanation


def analysis_to_cache_payload(result):
    recording, *analysis = result
    return recording_to_cache_payload(recording), *analysis


def analysis_from_cache_payload(result):
    recording_payload, *analysis = result
    return recording_from_cache_payload(recording_payload), *analysis


def analyze_source(source: AnalysisSource, duration_s: float | None = None):
    if isinstance(source, PublicSample):
        return analysis_from_cache_payload(analyze_public_sample(source.key, source.cache_token()))
    return analysis_from_cache_payload(analyze_path(str(source), source.stat().st_mtime_ns, duration_s))


def source_name(source: AnalysisSource) -> str:
    return source.sample_label if isinstance(source, PublicSample) else source.name


@st.cache_data(show_spinner=False)
def analyze_public_sample(sample_key: str, cache_token: tuple[tuple[str, int, int], ...]):
    del cache_token
    recording = load_public_sample(PUBLIC_SAMPLES_BY_KEY[sample_key])
    return analysis_to_cache_payload(analyze_recording(recording))


def save_upload(uploaded, role: str) -> Path:
    payload = uploaded.getvalue()
    digest = hashlib.sha256(payload).hexdigest()[:16]
    safe_name = Path(uploaded.name).name
    target = UPLOAD_DIR / f"{role}_{digest}_{safe_name}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(payload)
    return target


def render_input_template_download(key: str) -> None:
    template_path = PROJECT_ROOT / "data" / "demo" / "neurochip_event_template.csv"
    if template_path.exists():
        st.download_button(
            "下载标准 CSV 模板",
            data=template_path.read_bytes(),
            file_name="neurochip_event_template.csv",
            mime="text/csv",
            key=key,
            icon=":material/download:",
        )


def render_input_validation(result: InputValidationResult, label: str) -> bool:
    if not result.valid:
        for error in result.errors:
            st.error(f"{label}：{error}")
        return False
    summary = result.summary
    if result.format_name == "CSV":
        st.success(
            f"{label}格式预检通过：{int(summary['events']):,} 个事件、{int(summary['channels'])} 个通道。"
        )
    else:
        st.success(
            f"{label}格式预检通过：{int(summary['events']):,} 个事件、{int(summary['channels'])} 个通道、"
            f"{float(summary['duration_s']):g} 秒。"
        )
    for warning in result.warnings:
        st.warning(f"{label}：{warning}")
    return True


def render_metric_summary(recording, features, quality, model_result) -> None:
    columns = st.columns(6)
    columns[0].metric("事件质量", f"{quality['quality_score']:.0f}", help="事件级质量分数，满分 100")
    columns[1].metric("通道数", recording.n_channels)
    columns[2].metric("有效事件", f"{int(features['total_spikes']):,}")
    columns[3].metric("平均率 (Hz)", f"{features['firing_rate_mean_hz']:.3f}")
    columns[4].metric("平均 STTC", f"{features['sttc_mean']:.3f}")
    columns[5].metric(
        "参考偏离分位",
        f"P{model_result['anomaly_percentile']:.0f}" if model_result else "N/A",
        help="相对45条前脑类器官参考记录的偏离程度；越高表示越少见，不等于疾病或毒性。",
    )
    grade_class = f"status-{quality['quality_grade']}"
    grade_label = {"pass": "通过", "review": "需要复核", "fail": "未通过"}[quality["quality_grade"]]
    st.markdown(f'<p class="{grade_class}">事件级质量状态：{grade_label}</p>', unsafe_allow_html=True)


def render_reference_scope(public_sample: PublicSample | None) -> None:
    if public_sample is None:
        label = "待确认数据域"
        note = "基础事件参数可以分析；两个参考分位是否适用取决于上传记录与45条前脑类器官参考队列的可比性。"
    else:
        label, note = REFERENCE_SCOPE_BY_DATASET.get(
            public_sample.dataset_id,
            ("待确认数据域", "事件参数可以分析；参考分位需要结合实验对象、平台和方案判断。"),
        )
    st.info(f"参考适用范围：{label}。{note}")


def render_single_recording(
    path: Path | None = None,
    duration_s: float | None = None,
    project_name: str | None = None,
    sample_name: str | None = None,
    public_sample: PublicSample | None = None,
) -> dict[str, float | str]:
    with st.spinner("正在分析电生理事件..."):
        if public_sample is not None:
            result = analyze_source(public_sample)
        elif path is not None:
            result = analyze_source(path, duration_s)
        else:
            raise ValueError("A file path or public sample is required")
        recording, features, quality, channel_table, model_result, deviations, explanation = result
    render_metric_summary(recording, features, quality, model_result)
    render_reference_scope(public_sample)

    overview, qc_tab, activity, network, evidence = st.tabs(
        ["总览", "质量控制", "放电活动", "网络与临界性", "模型解释"]
    )
    with overview:
        left, right = st.columns([1.45, 1])
        with left:
            st.subheader("Spike raster")
            st.plotly_chart(raster_figure(recording), width="stretch", config={"displaylogo": False})
        with right:
            st.subheader("参考相对功能状态")
            if model_result:
                st.metric(
                    "功能状态轴分位",
                    f"P{model_result['functional_phenotype_index']:.1f}",
                    help="18项功能特征第一主轴在前脑类器官参考队列中的相对位置；不是健康分数。",
                )
                st.progress(int(np.clip(model_result["functional_phenotype_index"], 0, 100)))
                st.metric(
                    "参考偏离分位",
                    f"P{model_result['anomaly_percentile']:.1f}",
                    help="相对参考队列的多特征少见程度；不是疾病、疗效或毒性概率。",
                )
                st.progress(int(np.clip(model_result["anomaly_percentile"], 0, 100)))
            st.dataframe(
                pd.DataFrame(
                    {
                        "指标": ["记录时长", "活跃通道比例", "网络爆发率", "群体活动熵", "越界事件"],
                        "结果": [
                            f"{recording.duration_s:.1f} s",
                            f"{features['active_channel_fraction']:.1%}",
                            f"{features['network_burst_rate_per_min']:.3f} /min",
                            f"{features['population_entropy']:.3f}",
                            f"{int(features['excluded_out_of_range_spikes'])}",
                        ],
                    }
                ),
                hide_index=True,
                width="stretch",
            )

    with qc_tab:
        columns = st.columns(5)
        columns[0].metric("稳定性", str(quality.get("stability_grade", "N/A")).upper())
        columns[1].metric("稳定性 CV", f"{features.get('firing_stability_cv', 0):.3f}")
        columns[2].metric("末段/首段", f"{features.get('activity_decay_log2_ratio', 0):+.2f} log2")
        columns[3].metric("待复核通道", int(quality.get("review_channel_candidates", 0)))
        columns[4].metric("建议排除", int(quality.get("excluded_channel_candidates", 0)))
        st.dataframe(
            channel_table.style.format(
                {
                    "firing_rate_hz": "{:.4f}",
                    "out_of_range_fraction": "{:.2%}",
                    "duplicate_fraction": "{:.2%}",
                    "refractory_violation_fraction": "{:.2%}",
                    "segment_rate_cv": "{:.3f}",
                    "event_rate_robust_z": "{:+.2f}",
                }
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "静默通道只标为 inactive candidate；只有原始电压或阻抗数据才能确认硬件死通道、噪声与基线漂移。"
        )

    with activity:
        st.subheader("群体活动")
        st.plotly_chart(population_activity_figure(recording), width="stretch", config={"displaylogo": False})
        st.subheader("通道放电率")
        st.plotly_chart(channel_rate_figure(recording), width="stretch", config={"displaylogo": False})

    with network:
        left, right = st.columns([1.05, 1])
        with left:
            st.subheader("STTC 功能连接")
            st.plotly_chart(sttc_heatmap_figure(recording), width="stretch", config={"displaylogo": False})
        with right:
            st.subheader("网络与临界性指标")
            network_table = pd.DataFrame(
                {
                    "指标": [
                        "平均 STTC",
                        "网络密度",
                        "加权聚类系数",
                        "雪崩率 (/min)",
                        "雪崩平均大小",
                        "分支比",
                        "距临界点 |ratio-1|",
                        "互信息 (bits)",
                        "传递熵 (bits)",
                        "方向性预测 GC",
                    ],
                    "结果": [
                        features["sttc_mean"],
                        features["network_density"],
                        features["network_clustering"],
                        features.get("avalanche_rate_per_min", 0),
                        features.get("avalanche_size_mean", 0),
                        features.get("avalanche_branching_ratio", 0),
                        features.get("avalanche_criticality_distance", 0),
                        features.get("mutual_information_mean_bits", 0),
                        features.get("transfer_entropy_mean_bits", 0),
                        features.get("granger_log_variance_ratio_mean", 0),
                    ],
                }
            )
            st.dataframe(network_table.style.format({"结果": "{:.6f}"}), hide_index=True, width="stretch")
            st.caption("传递熵与 GC 表示统计信息流或预测方向，不等同于已证实的突触因果关系。")

    with evidence:
        left, right = st.columns([1.05, 1])
        with left:
            st.subheader("参考偏离 Shapley 贡献")
            if not explanation.empty:
                ranked = explanation.assign(abs_value=explanation["anomaly_shap_value"].abs()).nlargest(8, "abs_value")
                st.dataframe(
                    ranked[["feature", "value", "scaled_value", "anomaly_shap_value"]].style.format(
                        {"value": "{:.4f}", "scaled_value": "{:+.2f}", "anomaly_shap_value": "{:+.5f}"}
                    ),
                    hide_index=True,
                    width="stretch",
                )
                st.caption("相对训练队列稳健中位数；64 次固定随机种子的 Monte Carlo Shapley 估计。")
        with right:
            st.subheader("相对参考队列的主要偏离")
            if deviations:
                st.dataframe(pd.DataFrame(deviations).style.format({"稳健尺度偏离": "{:.2f}"}), hide_index=True)
        st.subheader("系统级验证证据")
        try:
            evidence_rows = load_evidence_ladder(PROJECT_ROOT)
        except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
            st.caption("完整验证结果未随当前部署提供；请查看技术报告和公开仓库中的结果文件。")
        else:
            for row in evidence_rows:
                with st.container(border=True):
                    st.markdown(f"**{row['验证层级']}** · {row['主要结果']}")
                    st.caption(row["数据与隔离方式"])
                    st.markdown(f"支持：{row['支持的结论']}  ")
                    st.markdown(f"不支持：{row['不能支持']}")
            st.caption("每一层只支持表中限定的结论；外部压力测试不等于通用药效、毒性或临床验证。")

    report_deviations = [
        {
            "feature": row["指标"],
            "robust_z": row["稳健尺度偏离"],
            "direction": "higher" if row["方向"] == "偏高" else "lower",
        }
        for row in deviations
    ]
    report = build_html_report(recording, features, quality, model_result, report_deviations)
    pdf_report = build_pdf_report(
        recording,
        features,
        quality,
        model_result,
        explanation,
        project_name=project_name,
        sample_name=sample_name,
    )
    downloads = st.columns(2)
    downloads[0].download_button(
        "下载 PDF 报告",
        pdf_report,
        file_name=f"{recording.recording_id}_neurochip_report.pdf",
        mime="application/pdf",
        type="primary",
        icon=":material/download:",
    )
    downloads[1].download_button(
        "下载 HTML 报告",
        report,
        file_name=f"{recording.recording_id}_neurochip_report.html",
        mime="text/html",
        icon=":material/download:",
    )
    return {
        "recording_id": recording.recording_id,
        "quality_score": float(quality["quality_score"]),
        "quality_grade": str(quality["quality_grade"]),
        "stability_grade": str(quality.get("stability_grade", "unknown")),
        "anomaly_percentile": float(model_result["anomaly_percentile"]) if model_result else float("nan"),
        "functional_phenotype_index": float(model_result["functional_phenotype_index"]) if model_result else float("nan"),
        "feature_schema_version": float(features.get("feature_schema_version", 1.0)),
    }


def render_multidimensional_effect(
    baseline_source: AnalysisSource,
    treatment_source: AnalysisSource,
    duration_s: float,
    goal: str,
    *,
    reference_source: AnalysisSource | None = None,
    recovery_source: AnalysisSource | None = None,
) -> None:
    phenotype_model = load_phenotype_model()
    if phenotype_model is None:
        st.error("功能表型模型尚未生成。")
        return

    with st.spinner("正在提取前后记录特征并进行多维功能评价..."):
        baseline = analyze_source(baseline_source, duration_s)
        treatment = analyze_source(treatment_source, duration_s)
        reference = (
            analyze_source(reference_source, duration_s)
            if reference_source is not None
            else None
        )
        recovery = (
            analyze_source(recovery_source, duration_s)
            if recovery_source is not None
            else None
        )

    baseline_recording, baseline_features, baseline_quality = baseline[:3]
    treatment_recording, treatment_features, treatment_quality = treatment[:3]
    reference_label = source_name(reference_source) if reference_source is not None else "公共功能参考（训练队列稳健中心）"
    evaluation = evaluate_functional_effect(
        baseline_features,
        treatment_features,
        phenotype_model,
        goal=goal,
        baseline_quality=float(baseline_quality["quality_score"]),
        treatment_quality=float(treatment_quality["quality_score"]),
        reference=reference[1] if reference is not None else None,
        reference_label=reference_label,
        recovery=recovery[1] if recovery is not None else None,
    )
    summary = evaluation.summary

    verdict = str(summary["verdict"])
    verdict_class = "status-pass" if "有益" in verdict or "符合" in verdict else (
        "status-fail" if "不利" in verdict or "不宜" in verdict else "status-review"
    )
    st.markdown(f'<h2 class="{verdict_class}">{verdict}</h2>', unsafe_allow_html=True)
    metric_columns = st.columns(3)
    metric_columns[0].metric("多维影响幅度", f"{float(summary['impact_magnitude']):.2f}")
    goal_score = summary["goal_alignment_score"]
    metric_columns[1].metric("目标一致性", f"{float(goal_score):.0f}/100" if goal_score is not None else "不适用")
    risk_labels = {"low": "低", "moderate": "中", "high": "高"}
    metric_columns[2].metric("网络沉默风险", risk_labels[str(summary["silencing_risk"])])
    quality_columns = st.columns(3)
    quality_columns[0].metric("基线质量", f"{baseline_quality['quality_score']:.0f}/100")
    quality_columns[1].metric("处理质量", f"{treatment_quality['quality_score']:.0f}/100")
    evidence_labels = {"insufficient": "不足", "low": "低", "moderate": "中等"}
    quality_columns[2].metric("证据等级", evidence_labels[str(summary["evidence_grade"])])
    st.caption(f"评价目标：{summary['goal_label']}。{summary['uncertainty_note']}")
    if summary["silencing_risk"] != "low":
        st.warning(str(summary["silencing_note"]))
    if summary["evidence_grade"] == "insufficient":
        st.error("至少一份记录没有通过事件质量门控，本页仅展示变化，不应据此判断处理好坏。")

    dimensions_tab, features_tab, reference_tab, advanced_tab, response_tab, export_tab = st.tabs(
        ["维度概览", "特征变化", "参考与恢复", "高级探索", "辅助响应分数", "导出"]
    )
    with dimensions_tab:
        domain_display = evaluation.domain_table.rename(
            columns={
                "domain_label": "功能维度",
                "impact_magnitude": "变化幅度",
                "mean_signed_change": "平均变化方向",
                "dominant_direction": "主要方向",
                "n_features": "指标数",
            }
        )[["功能维度", "变化幅度", "平均变化方向", "主要方向", "指标数"]]
        figure = go.Figure()
        figure.add_bar(
            name="变化幅度",
            x=domain_display["功能维度"],
            y=domain_display["变化幅度"],
            marker_color="#147F7A",
        )
        figure.add_scatter(
            name="平均变化方向",
            x=domain_display["功能维度"],
            y=domain_display["平均变化方向"],
            mode="markers",
            marker={"color": "#C55A2A", "size": 10, "symbol": "diamond"},
        )
        figure.add_hline(y=0, line_color="#6C7880", line_width=1)
        figure.update_layout(
            height=390,
            margin={"l": 48, "r": 16, "t": 30, "b": 70},
            yaxis_title="相对公共队列稳健尺度",
            plot_bgcolor="white",
            paper_bgcolor="white",
            legend={"orientation": "h", "y": 1.1},
        )
        figure.update_yaxes(showgrid=True, gridcolor="#EDF0F2")
        st.plotly_chart(figure, width="stretch", config={"displaylogo": False})
        st.dataframe(
            domain_display.style.format({"变化幅度": "{:.3f}", "平均变化方向": "{:+.3f}"}),
            hide_index=True,
            width="stretch",
        )
        st.caption("变化幅度表示改变了多少；平均变化方向只表示该维度总体升高或降低，不等于自动判断有益或有害。")

    with features_tab:
        feature_display = evaluation.feature_table.rename(
            columns={
                "domain_label": "功能维度",
                "feature_label": "指标",
                "baseline": "基线",
                "treatment": "处理后",
                "symmetric_change_percent": "对称变化率",
                "robust_standardized_change": "稳健标准化变化",
                "direction": "方向",
                "goal_alignment": "目标关系",
            }
        )[["功能维度", "指标", "基线", "处理后", "对称变化率", "稳健标准化变化", "方向", "目标关系"]]
        st.dataframe(
            feature_display.style.format(
                {"基线": "{:.4f}", "处理后": "{:.4f}", "对称变化率": "{:+.1f}%", "稳健标准化变化": "{:+.3f}"}
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption("对称变化率适合处理接近零的指标；稳健标准化变化用于在不同量纲指标之间比较。")

    with reference_tab:
        reference_columns = st.columns(4)
        reference_columns[0].metric("基线距参考", f"{float(summary['baseline_reference_distance']):.2f}")
        reference_columns[1].metric("处理后距参考", f"{float(summary['treatment_reference_distance']):.2f}")
        reference_columns[2].metric("向参考变化", f"{float(summary['reference_improvement_percent']):+.1f}%")
        reversibility = summary["reversibility_percent"]
        reference_columns[3].metric("恢复程度", f"{float(reversibility):+.1f}%" if reversibility is not None else "未提供")
        st.write(f"参考来源：{summary['reference_label']}")
        st.write(f"可逆性判断：{summary['reversibility_label']}")
        st.info("公共功能参考是公开训练队列的统计中心，不是经过临床认证的健康标准。只有提供可信的匹配健康参考且基线代表疾病状态时，向参考改善才可作为探索性表型挽救指标。")

    with advanced_tab:
        advanced_display = evaluation.advanced_table.rename(
            columns={
                "domain_label": "功能维度",
                "feature_label": "指标",
                "baseline": "基线",
                "treatment": "处理后",
                "symmetric_change_percent": "对称变化率",
                "direction": "方向",
                "evidence_scope": "证据范围",
            }
        )[["功能维度", "指标", "基线", "处理后", "对称变化率", "方向", "证据范围"]]
        st.dataframe(
            advanced_display.style.format({"基线": "{:.4f}", "处理后": "{:.4f}", "对称变化率": "{:+.1f}%"}),
            hide_index=True,
            width="stretch",
        )
        st.caption("稳定性、神经雪崩和信息流指标用于机制探索，当前不参与处理效应好坏总评。")

    with response_tab:
        drug_model = load_drug_model()
        if drug_model is None:
            st.info("辅助药理响应模型尚未生成。")
        else:
            response = drug_model.score_pair(treatment_features, baseline_features)
            contribution = drug_model.explain_pair(treatment_features, baseline_features)
            dose_calibration_applicable = (
                isinstance(baseline_source, PublicSample)
                and isinstance(treatment_source, PublicSample)
                and baseline_source.dataset_id == "diazepam_organoid"
                and treatment_source.dataset_id == "diazepam_organoid"
            )
            response_columns = st.columns(3)
            response_columns[0].metric("配对响应幅度", f"{response['response_magnitude']:.2f}")
            response_columns[1].metric("训练响应分位", f"P{response['response_percentile']:.0f}")
            response_columns[2].metric(
                "地西泮剂量映射",
                f"{response['predicted_dose_um_exploratory']:.1f} uM" if dose_calibration_applicable else "不适用",
                help="只在公开地西泮类器官配对中显示探索性映射；不能用于给药决策。",
            )
            feature_labels = {"isi_cv_mean": "ISI CV", "isi_median_s": "ISI中位数"}
            response_display = pd.DataFrame(
                {
                    "指标": [feature_labels.get(name, name) for name in drug_model.feature_names],
                    "基线": [baseline_features[name] for name in drug_model.feature_names],
                    "处理后": [treatment_features[name] for name in drug_model.feature_names],
                    "对数差": [response[f"delta_log__{name}"] for name in drug_model.feature_names],
                    "响应贡献": contribution["response_squared_contribution_fraction"].to_numpy(float),
                }
            )
            st.dataframe(
                response_display.style.format(
                    {"基线": "{:.4f}", "处理后": "{:.4f}", "对数差": "{:+.4f}", "响应贡献": "{:.1%}"}
                ),
                hide_index=True,
                width="stretch",
            )
            dose_note = (
                "地西泮剂量映射仅用于公开训练域内的方法演示。"
                if dose_calibration_applicable
                else "当前不是明确的地西泮训练域，剂量映射已禁用。"
            )
            st.caption(
                "此分数只回答处理前后差异有多明显，是辅助证据；它不单独判断疗效、毒性或处理好坏。"
                + dose_note
            )

    with export_tab:
        html_report = build_functional_effect_html(
            evaluation,
            baseline_name=source_name(baseline_source),
            treatment_name=source_name(treatment_source),
        )
        export_columns = st.columns(4)
        export_columns[0].download_button(
            "下载综合 HTML 报告",
            html_report,
            file_name="neurochip_multidimensional_effect_report.html",
            mime="text/html",
            type="primary",
            icon=":material/download:",
        )
        export_columns[1].download_button(
            "下载结果 JSON",
            json.dumps(summary, ensure_ascii=False, indent=2),
            file_name="neurochip_multidimensional_effect_summary.json",
            mime="application/json",
            icon=":material/download:",
        )
        export_columns[2].download_button(
            "下载特征变化 CSV",
            evaluation.feature_table.to_csv(index=False),
            file_name="neurochip_multidimensional_feature_changes.csv",
            mime="text/csv",
            icon=":material/download:",
        )
        export_columns[3].download_button(
            "下载维度汇总 CSV",
            evaluation.domain_table.to_csv(index=False),
            file_name="neurochip_multidimensional_domain_summary.csv",
            mime="text/csv",
            icon=":material/download:",
        )
        reports = st.columns(2)
        for column, label, recording, features, quality, model_result, explanation in (
            (reports[0], "基线", baseline_recording, baseline_features, baseline_quality, baseline[4], baseline[6]),
            (reports[1], "处理后", treatment_recording, treatment_features, treatment_quality, treatment[4], treatment[6]),
        ):
            pdf_report = build_pdf_report(recording, features, quality, model_result, explanation=explanation)
            column.download_button(
                f"下载{label}单记录 PDF",
                pdf_report,
                file_name=f"{recording.recording_id}_neurochip_report.pdf",
                mime="application/pdf",
                icon=":material/download:",
            )


def render_project_manager() -> None:
    store = load_project_store()
    header_left, header_right = st.columns([1, 1.35])
    with header_left:
        st.subheader("新建项目")
        with st.form("create_project", clear_on_submit=True):
            project_name = st.text_input("项目名称", placeholder="Drug screening 2026")
            project_description = st.text_area("项目备注", height=84)
            create_submitted = st.form_submit_button("新建项目", type="primary")
        if create_submitted:
            try:
                store.create_project(project_name, project_description)
                st.rerun()
            except (ValueError, sqlite3.IntegrityError) as error:
                st.error(f"项目未创建：{error}")

    projects = store.list_projects()
    with header_right:
        st.subheader("项目概览")
        if projects.empty:
            st.info("当前没有项目。")
        else:
            st.dataframe(projects[["name", "description", "created_utc"]], hide_index=True, width="stretch")
    if projects.empty:
        return

    project_map = dict(zip(projects["name"], projects["project_id"], strict=True))
    selected_project_name = st.selectbox("当前项目", list(project_map), key="project_selector")
    selected_project_id = project_map[selected_project_name]
    st.divider()
    upload_left, upload_right = st.columns([1, 1.25])
    with upload_left:
        st.subheader("登记样本")
        sample_upload = st.file_uploader(
            "事件文件",
            type=["mat", "h5", "hdf5", "csv"],
            key=f"project_upload_{selected_project_id}",
        )
        sample_name = st.text_input("样本名称", placeholder="Organoid001")
        sample_role = st.selectbox("样本角色", ["sample", "control", "treatment", "reference"])
        if st.button("登记样本", type="primary", disabled=sample_upload is None):
            if sample_upload is not None:
                path = save_upload(sample_upload, f"project_{selected_project_id[:8]}")
                try:
                    store.add_sample(selected_project_id, sample_name or path.stem, path, sample_role)
                    st.rerun()
                except (ValueError, sqlite3.IntegrityError) as error:
                    st.error(f"样本未登记：{error}")

    samples = store.list_samples(selected_project_id)
    with upload_right:
        st.subheader("样本清单")
        if samples.empty:
            st.info("该项目还没有样本。")
        else:
            display = samples[["sample_name", "sample_role", "file_path", "added_utc"]].copy()
            display["analysis_status"] = np.where(samples["latest_analysis_json"].notna(), "analyzed", "pending")
            st.dataframe(display, hide_index=True, width="stretch")
    if samples.empty:
        return

    sample_map = dict(zip(samples["sample_name"], samples["sample_id"], strict=True))
    selected_sample_name = st.selectbox("选择样本分析", list(sample_map), key="project_sample_selector")
    selected_sample_id = sample_map[selected_sample_name]
    if st.button("运行样本分析", icon=":material/play_arrow:"):
        st.session_state["active_project_sample_id"] = selected_sample_id
    if st.session_state.get("active_project_sample_id") == selected_sample_id:
        sample = samples.loc[samples["sample_id"] == selected_sample_id].iloc[0]
        path = Path(sample["file_path"])
        if not path.exists():
            st.error(f"样本文件不存在：{path}")
            return
        result = render_single_recording(path, project_name=selected_project_name, sample_name=selected_sample_name)
        store.record_analysis(selected_sample_id, result)


st.title("NeuroChip Copilot")
st.markdown(
    '<div class="scope">End-to-End System · 检测后 MEA 事件 → 质量控制 → 功能表型 → 可解释偏离 → 多维干预评价 → 报告</div>',
    unsafe_allow_html=True,
)

baseline_source: AnalysisSource | None = None
treatment_source: AnalysisSource | None = None
reference_source: AnalysisSource | None = None
recovery_source: AnalysisSource | None = None
selected_public_sample: PublicSample | None = None
selected_public_pair: PublicPair | None = None
selected_path: Path | None = None
selected_duration: float | None = None
paired_goal = "quantify_only"
paired_duration = 180.0
with st.sidebar:
    st.subheader("工作模式")
    mode = st.segmented_control(
        "选择任务",
        ["单记录", "干预评价", "项目"],
        default="单记录",
        label_visibility="collapsed",
    )
    st.divider()

    if mode == "单记录":
        source_mode = st.radio("数据来源", ["公共数据集（仅供示例）", "上传数据"], horizontal=True)
        if source_mode == "公共数据集（仅供示例）":
            if PUBLIC_SAMPLE_GROUPS:
                dataset_options = {
                    (
                        f"{label}（演示{len(samples)}/完整{PUBLIC_DATASET_TOTALS[label]}）"
                        if USING_LIGHTWEIGHT_PUBLIC_SAMPLES
                        else f"{label}（{len(samples)}条）"
                    ): label
                    for label, samples in PUBLIC_SAMPLE_GROUPS.items()
                }
                dataset_display = st.selectbox("公共数据集（仅供示例）", list(dataset_options), key="public_dataset")
                dataset_label = dataset_options[dataset_display]
                sample_options = {
                    sample.sample_label: sample
                    for sample in PUBLIC_SAMPLE_GROUPS[dataset_label]
                }
                selected_label = st.selectbox(
                    "公开记录",
                    list(sample_options),
                    key=f"public_record_{dataset_label}",
                )
                selected_public_sample = sample_options[selected_label]
                st.caption(f"{selected_public_sample.context} | DOI: {selected_public_sample.data_doi}")
            else:
                st.error("示例数据尚未准备完成。")
        else:
            render_input_template_download("single_template")
            uploaded = st.file_uploader("MAT / HDF5 / CSV", type=["mat", "h5", "hdf5", "csv"], key="single")
            use_duration = st.checkbox("指定记录时长", value=False)
            if use_duration:
                selected_duration = float(st.number_input("记录时长（秒）", min_value=1.0, value=180.0, step=1.0))
            if uploaded is not None:
                candidate_path = save_upload(uploaded, "single")
                validation = validate_input_file(candidate_path, selected_duration)
                if render_input_validation(validation, "上传记录"):
                    selected_path = candidate_path

    elif mode == "干预评价":
        paired_source_mode = st.radio("评价数据", ["公共数据集（仅供示例）", "上传数据"], horizontal=True)
        if paired_source_mode == "公共数据集（仅供示例）":
            if PUBLIC_PAIRS:
                pair_groups: dict[str, list[PublicPair]] = {}
                for pair in PUBLIC_PAIRS:
                    pair_groups.setdefault(pair.baseline.dataset_label, []).append(pair)
                pair_dataset = st.selectbox(
                    "公共数据集（仅供示例）",
                    list(pair_groups),
                    key="paired_public_dataset",
                )
                dataset_pairs = pair_groups[pair_dataset]
                baseline_options = {
                    pair.baseline.sample_label: pair.baseline
                    for pair in dataset_pairs
                }
                baseline_label = st.selectbox(
                    "选择基线记录",
                    list(baseline_options),
                    key="paired_public_baseline",
                )
                baseline_pairs = [
                    pair for pair in dataset_pairs if pair.baseline.sample_label == baseline_label
                ]
                treatment_options = {
                    pair.treatment.sample_label: pair
                    for pair in baseline_pairs
                }
                treatment_label = st.selectbox(
                    "选择处理后记录",
                    list(treatment_options),
                    key="paired_public_treatment",
                )
                selected_public_pair = treatment_options[treatment_label]
                baseline_source = selected_public_pair.baseline
                treatment_source = selected_public_pair.treatment
                paired_duration = float(selected_public_pair.baseline.duration_s or 180.0)
                st.caption(selected_public_pair.context)
                st.caption("公共示例用于展示流程；正式分析建议上传同一实验对象的前后记录。")
            else:
                st.error("公开配对示例尚未准备完成。")
        else:
            st.caption("上传同一实验对象的前后记录，并指定基线、处理后记录和评价目标。")
            render_input_template_download("paired_template")
            paired_uploads = st.file_uploader(
                "前后记录（至少2份）",
                type=["mat", "h5", "hdf5", "csv"],
                accept_multiple_files=True,
                key="paired_files",
            )
            paired_duration = float(st.number_input("每条记录时长（秒）", min_value=1.0, value=180.0, step=1.0))
            if len(paired_uploads) >= 2:
                paired_labels = [f"{index + 1}. {uploaded.name}" for index, uploaded in enumerate(paired_uploads)]
                paired_paths = {}
                validation_results = {}
                for index, (label, uploaded) in enumerate(zip(paired_labels, paired_uploads, strict=True), start=1):
                    path = save_upload(uploaded, f"paired_{index}")
                    validation = validate_input_file(path, paired_duration)
                    validation_results[label] = validation
                    render_input_validation(validation, label)
                    if validation.valid:
                        paired_paths[label] = path
                if len(paired_paths) == len(paired_labels):
                    baseline_label = st.selectbox("选择基线记录", paired_labels, key="paired_baseline")
                    treatment_choices = [label for label in paired_labels if label != baseline_label]
                    treatment_label = st.selectbox("选择处理后记录", treatment_choices, key="paired_treatment")
                    baseline_source = paired_paths[baseline_label]
                    treatment_source = paired_paths[treatment_label]
                    baseline_summary = validation_results[baseline_label].summary
                    treatment_summary = validation_results[treatment_label].summary
                    if baseline_summary.get("channels") != treatment_summary.get("channels"):
                        st.warning("基线与处理后记录的通道数不同；请确认这是实验对象变化，而不是导出配置不一致。")
                    remaining_labels = [label for label in paired_labels if label not in {baseline_label, treatment_label}]
                    public_reference_label = "公共功能参考（非临床健康标准）"
                    reference_label = st.selectbox(
                        "参考记录（可选）",
                        [public_reference_label, *remaining_labels],
                        key="paired_reference",
                        help="如有匹配健康对照，建议选它；否则使用公开训练队列的统计中心。",
                    )
                    recovery_choices = [
                        label for label in remaining_labels if reference_label == public_reference_label or label != reference_label
                    ]
                    recovery_label = st.selectbox(
                        "恢复期或洗脱后记录（可选）",
                        ["不提供", *recovery_choices],
                        key="paired_recovery",
                    )
                    reference_source = paired_paths.get(reference_label)
                    recovery_source = paired_paths.get(recovery_label)
                else:
                    st.info("请先修正格式预检未通过的文件，之后才能选择基线和处理后记录。")
        if baseline_source is not None and treatment_source is not None:
            paired_goal = st.selectbox(
                "本次处理的预期目标",
                list(GOAL_LABELS),
                format_func=lambda value: GOAL_LABELS[value],
                key="paired_goal",
            )

    st.divider()
    st.caption("参考队列：45 条公开前脑类器官 MEA 记录")
    if USING_LIGHTWEIGHT_PUBLIC_SAMPLES:
        st.caption("当前为轻量演示数据；模型开发与外部检验使用完整公开数据，详见技术报告。")
    st.caption(f"可直接运行的公开配对：{len(PUBLIC_PAIRS)} 组")
    st.caption("STTC 重合窗口：20 ms")
    st.caption("NeuroChip 标准输入：timestamp_s + channel_id")
    st.caption("事件输入不等同于原始电压波形 QC")

if mode == "干预评价":
    if baseline_source is None or treatment_source is None:
        st.info("请选择公开配对，或上传至少两份记录后指定基线和处理后记录。")
    else:
        render_multidimensional_effect(
            baseline_source,
            treatment_source,
            paired_duration,
            paired_goal,
            reference_source=reference_source,
            recovery_source=recovery_source,
        )
elif mode == "项目":
    render_project_manager()
else:
    if selected_path is None and selected_public_sample is None:
        st.info("请选择一条公开记录或上传数据。")
    else:
        if selected_public_sample is not None:
            if selected_public_sample.notice:
                st.info(selected_public_sample.notice)
            render_single_recording(public_sample=selected_public_sample)
        else:
            render_single_recording(selected_path, selected_duration)

st.divider()
st.caption("结果仅用于研究与方法验证，不构成临床、药理疗效或毒理安全结论。")
