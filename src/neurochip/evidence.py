from __future__ import annotations

import json
from pathlib import Path


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_evidence_ladder(project_root: Path) -> list[dict[str, str]]:
    """Build competition-facing evidence rows from the checked-in result files."""
    results = project_root / "artifacts" / "results"
    source = _read_json(results / "source_validation" / "validation_metrics.json")
    phenotype = _read_json(results / "phenotype" / "metrics.json")
    drug = _read_json(results / "drug_response" / "metrics.json")
    gin = _read_json(results / "external_validation" / "gin_metrics.json")
    trujillo = _read_json(results / "external_validation" / "trujillo_metrics.json")

    gin_primary = {
        item["comparison"]: item
        for item in gin["metrics"]
        if item["window_s"] == gin["primary_window_s"] and item["dataset_id"] == "pooled"
    }
    trujillo_primary = trujillo["primary_labeled_endpoint"]
    anomaly_ci = phenotype["roc_auc_cluster_bootstrap_95ci"]
    drug_ci = drug["response_magnitude_dose_spearman_cluster_bootstrap_95ci"]

    return [
        {
            "验证层级": "1 源值复现",
            "数据与隔离方式": f"{source['n_matched']}/{source['n_published']} 条前脑类器官记录",
            "主要结果": (
                f"放电率最大误差 {source['firing_rate_max_abs_error']:.2e}；"
                f"STTC 最大误差 {source['sttc_max_abs_error']:.2e}"
            ),
            "支持的结论": "读取、时间窗和核心特征实现与发布者结果一致",
            "不能支持": "不能证明疾病、药效或跨设备泛化",
        },
        {
            "验证层级": "2 分组异常检验",
            "数据与隔离方式": (
                f"{phenotype['n_reference_recordings']} 条原始记录 + 135 个受控扰动；"
                f"按 {phenotype['n_unique_fs_groups']} 个来源组五折留出"
            ),
            "主要结果": (
                f"AUROC {phenotype['roc_auc']:.3f} "
                f"(95% CI {anomaly_ci[0]:.3f}-{anomaly_ci[1]:.3f})"
            ),
            "支持的结论": "模型能识别预定义的事件层异常变化，并减少同源数据泄漏",
            "不能支持": "受控扰动不是疾病、毒性或临床异常标签",
        },
        {
            "验证层级": "3 真实类器官剂量关联",
            "数据与隔离方式": (
                f"{drug['n_conditions']} 个地西泮条件、{drug['n_organoids']} 个类器官；"
                "每次完整留出一个类器官"
            ),
            "主要结果": (
                f"Spearman rho {drug['response_magnitude_dose_spearman']:.3f} "
                f"(95% CI {drug_ci[0]:.3f}-{drug_ci[1]:.3f})；"
                f"高剂量 AUROC {drug['high_dose_auc']:.3f}"
            ),
            "支持的结论": "匹配对照的变化幅度与该队列中的剂量次序相关",
            "不能支持": "一个化合物和四个类器官不足以建立通用剂量或疗效模型",
        },
        {
            "验证层级": "4 冻结跨域压力测试",
            "数据与隔离方式": "GIN 人源/大鼠二维网络，66 个匹配孔；模型不重训",
            "主要结果": (
                f"药理处理 AUROC {gin_primary['pharma_vs_baseline']['roc_auc']:.3f}；"
                f"TTX AUROC {gin_primary['ttx_vs_pharma']['roc_auc']:.3f}"
            ),
            "支持的结论": "辅助变化幅度可迁移到不同物种和二维培养中的强扰动",
            "不能支持": "二维培养不是类器官，也不能解释外部化合物剂量和机制",
        },
        {
            "验证层级": "5 独立类器官协议",
            "数据与隔离方式": (
                f"Trujillo 皮层类器官：{trujillo_primary['n_active']} 个处理对、"
                f"{trujillo_primary['n_control']} 个同期对照对；模型不重训"
            ),
            "主要结果": (
                f"AUROC {trujillo_primary['roc_auc']:.3f} "
                f"(95% CI {trujillo_primary['roc_auc_stratified_bootstrap_95ci'][0]:.3f}-"
                f"{trujillo_primary['roc_auc_stratified_bootstrap_95ci'][1]:.3f})；"
                "6/6 处理变化超过同孔自然漂移"
            ),
            "支持的结论": "冻结模型可在一个独立类器官实验方案中检测强功能变化",
            "不能支持": "样本量小，不能证明多中心、跨化合物疗效或毒性泛化",
        },
    ]
