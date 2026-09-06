from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .gin_pharmacology import build_well_recording, load_gin_stage
from .io import read_recording
from .schema import SpikeRecording
from .trujillo import read_trujillo_well


@dataclass(frozen=True)
class PublicSample:
    key: str
    dataset_id: str
    dataset_label: str
    sample_label: str
    source_path: Path
    source_kind: str = "recording"
    duration_s: float | None = None
    data_doi: str = ""
    context: str = ""
    notice: str = ""
    well: str = ""
    start_s: float = 0.0
    experiment_log_path: Path | None = None
    noisy_channels_path: Path | None = None
    protocol_duration_s: float | None = None

    def source_files(self) -> tuple[Path, ...]:
        paths = [self.source_path]
        if self.experiment_log_path is not None:
            paths.append(self.experiment_log_path)
        if self.noisy_channels_path is not None:
            paths.append(self.noisy_channels_path)
        return tuple(paths)

    def cache_token(self) -> tuple[tuple[str, int, int], ...]:
        return tuple(
            (str(path), path.stat().st_size, path.stat().st_mtime_ns)
            for path in self.source_files()
        )


@dataclass(frozen=True)
class PublicPair:
    key: str
    label: str
    baseline: PublicSample
    treatment: PublicSample
    context: str


@dataclass(frozen=True)
class _GinSource:
    dataset_id: str
    stage: str
    spike_path: Path
    experiment_log_path: Path
    noisy_channels_path: Path
    protocol_duration_s: float


STAGE_LABELS = {
    "baseline": "基线",
    "pharma": "药物处理",
    "ttx": "TTX处理",
    "baseline_control": "基线1",
    "baseline_repeat": "基线2",
    "post_treatment": "处理后",
}


def _demo_samples(project_root: Path) -> dict[str, list[PublicSample]]:
    manifest_path = project_root / "data" / "demo" / "public_samples" / "manifest.csv"
    samples: list[PublicSample] = []
    if manifest_path.exists():
        manifest = pd.read_csv(manifest_path).fillna("")
        for row in manifest.itertuples(index=False):
            path = manifest_path.parent / str(row.file_name)
            if not path.exists():
                continue
            samples.append(
                PublicSample(
                    key=f"demo:{row.sample_id}",
                    dataset_id=str(row.dataset_id),
                    dataset_label=str(row.dataset_label),
                    sample_label=str(row.sample_label),
                    source_path=path,
                    duration_s=float(row.duration_s),
                    data_doi=str(row.data_doi),
                    context=str(row.context),
                    notice=str(row.notice),
                )
            )
    if samples:
        groups: dict[str, list[PublicSample]] = {}
        for sample in samples:
            groups.setdefault(sample.dataset_label, []).append(sample)
        return groups

    fallback = project_root / "data" / "demo" / "fs363-org0_events.csv"
    if not fallback.exists():
        return {}
    label = "前脑类器官参考"
    return {
        label: [
            PublicSample(
                key="demo:fs363-org0",
                dataset_id="forebrain_reference",
                dataset_label=label,
                sample_label="fs363-org0",
                source_path=fallback,
                data_doi="10.5281/zenodo.20286251",
                context="公开前脑类器官MEA记录",
            )
        ]
    }


def _forebrain_samples(project_root: Path) -> list[PublicSample]:
    source_dir = project_root / "data" / "interim" / "zenodo_20286251" / "individual"
    label = "前脑类器官参考"
    return [
        PublicSample(
            key=f"forebrain:{path.stem}",
            dataset_id="forebrain_reference",
            dataset_label=label,
            sample_label=path.stem,
            source_path=path,
            data_doi="10.5281/zenodo.20286251",
            context="公开前脑类器官MEA记录",
        )
        for path in sorted(source_dir.glob("*.mat"))
    ]


def _diazepam_label(path: Path) -> tuple[str, str]:
    condition, organoid = path.stem.rsplit("_", 1)
    if condition == "control":
        treatment = "匹配对照"
    else:
        dose = condition.removeprefix("diazepam").removesuffix("uM")
        treatment = f"地西泮 {dose} uM"
    return f"类器官 {organoid} | {treatment}", treatment


def _diazepam_samples(project_root: Path) -> list[PublicSample]:
    source_dir = project_root / "data" / "interim" / "zenodo_6578989" / "kilosort2" / "drug" / "kilosort2"
    label = "脑类器官地西泮"
    samples = []
    for path in sorted(source_dir.glob("*.mat")):
        sample_label, treatment = _diazepam_label(path)
        samples.append(
            PublicSample(
                key=f"diazepam:{path.stem}",
                dataset_id="diazepam_organoid",
                dataset_label=label,
                sample_label=sample_label,
                source_path=path,
                data_doi="10.25349/D9031Z",
                context=f"脑类器官药理记录 | {treatment}",
                notice="该数据集用于配对响应建模；单条记录不能单独判断药物效果好坏。",
            )
        )
    return samples


def _gin_sources(project_root: Path) -> dict[tuple[str, str], _GinSource]:
    repository = project_root / "data" / "x" / "gin" / "comparative_mea_dataset"
    raw_dir = project_root / "data" / "raw" / "external" / "gin_comparative_mea"
    hpsc = repository / "Data" / "hPSC_MEA3_Pharmacology"
    rat = repository / "Data" / "Rat_MEA2_Pharmacology"

    def source(
        dataset_id: str,
        stage: str,
        duration_s: float,
        spike_path: Path,
        stage_dir: Path,
        stem: str,
    ) -> _GinSource:
        detail_dir = stage_dir / f"{stage_dir.name}_spikes_noise_explogs"
        return _GinSource(
            dataset_id=dataset_id,
            stage=stage,
            spike_path=spike_path,
            experiment_log_path=detail_dir / f"{stem}_expLog.csv",
            noisy_channels_path=detail_dir / f"noisy_electrodes_{stage_dir.name}.csv",
            protocol_duration_s=duration_s,
        )

    configs = (
        source(
            "hpsc_mea3",
            "baseline",
            1800.0,
            raw_dir / "hPSC_120618_MEA3Baseline_DIV29_spikes.csv",
            hpsc / "hPSC_MEA3Baseline_DIV29",
            "hPSC_120618_MEA3Baseline_DIV29",
        ),
        source(
            "hpsc_mea3",
            "pharma",
            1800.0,
            raw_dir / "hPSC_120618_MEA3Pharma_DIV29_spikes.csv",
            hpsc / "hPSC_MEA3Pharma_DIV29",
            "hPSC_120618_MEA3Pharma_DIV29",
        ),
        source(
            "hpsc_mea3",
            "ttx",
            600.0,
            hpsc
            / "hPSC_MEA3TTX_DIV29"
            / "hPSC_MEA3TTX_DIV29_spikes_noise_explogs"
            / "hPSC_120618_MEA3TTX_DIV29_spikes.csv",
            hpsc / "hPSC_MEA3TTX_DIV29",
            "hPSC_120618_MEA3TTX_DIV29",
        ),
        source(
            "rat_mea2",
            "baseline",
            1800.0,
            raw_dir / "Rat_50618_MEA2Baseline_DIV22_spikes.csv",
            rat / "Rat_MEA2Baseline_DIV22",
            "Rat_50618_MEA2Baseline_DIV22",
        ),
        source(
            "rat_mea2",
            "pharma",
            1800.0,
            raw_dir / "Rat_50618_MEA2Pharma_DIV22_spikes.csv",
            rat / "Rat_MEA2Pharma_DIV22",
            "Rat_50618_MEA2Pharma_DIV22",
        ),
        source(
            "rat_mea2",
            "ttx",
            600.0,
            rat
            / "Rat_MEA2TTX_DIV22"
            / "Rat_MEA2TTX_DIV22_spikes_noise_explogs"
            / "Rat_50618_MEA2TTX_DIV22_spikes.csv",
            rat / "Rat_MEA2TTX_DIV22",
            "Rat_50618_MEA2TTX_DIV22",
        ),
    )
    return {(item.dataset_id, item.stage): item for item in configs}


def _gin_samples(project_root: Path) -> list[PublicSample]:
    feature_path = project_root / "data" / "processed" / "external_gin_features_180s.csv"
    if not feature_path.exists():
        return []
    sources = _gin_sources(project_root)
    if not all(path.exists() for item in sources.values() for path in (
        item.spike_path,
        item.experiment_log_path,
        item.noisy_channels_path,
    )):
        return []
    table = pd.read_csv(
        feature_path,
        usecols=["dataset_id", "culture_type", "stage", "well", "treatment", "dose_um"],
    ).drop_duplicates()
    culture_labels = {
        "hpsc_mea3": "人源iPSC二维神经元",
        "rat_mea2": "大鼠二维神经元",
    }
    label = "GIN二维神经网络"
    samples = []
    for row in table.sort_values(["dataset_id", "well", "stage"]).itertuples(index=False):
        config = sources[(str(row.dataset_id), str(row.stage))]
        treatment = str(row.treatment)
        dose = "" if pd.isna(row.dose_um) else f" {float(row.dose_um):g} uM"
        culture = culture_labels[str(row.dataset_id)]
        stage_label = STAGE_LABELS[str(row.stage)]
        samples.append(
            PublicSample(
                key=f"gin:{row.dataset_id}:{row.stage}:{row.well}",
                dataset_id="gin_comparative_mea",
                dataset_label=label,
                sample_label=f"{culture} | 孔 {row.well} | {stage_label} | {treatment}{dose}",
                source_path=config.spike_path,
                source_kind="gin_well",
                duration_s=180.0,
                data_doi="10.12751/g-node.wvr3jf",
                context=f"{culture} | {stage_label} | 孔 {row.well}",
                notice="这是二维神经元外部验证数据；功能状态轴和参考偏离分位仅作跨数据域探索。",
                well=str(row.well),
                experiment_log_path=config.experiment_log_path,
                noisy_channels_path=config.noisy_channels_path,
                protocol_duration_s=config.protocol_duration_s,
            )
        )
    return samples


def _trujillo_samples(project_root: Path) -> list[PublicSample]:
    feature_path = project_root / "data" / "processed" / "external_trujillo_features.csv"
    raw_dir = project_root / "data" / "raw" / "external" / "zenodo_4751759"
    if not feature_path.exists():
        return []
    table = pd.read_csv(
        feature_path,
        usecols=[
            "analysis_window_s",
            "recording_date",
            "well",
            "stage",
            "treatment",
            "window_start_s",
            "source_file",
        ],
    )
    table = table.loc[table["analysis_window_s"] == 120].drop_duplicates()
    label = "Trujillo皮层类器官"
    samples = []
    for row in table.sort_values(["recording_date", "well", "stage"]).itertuples(index=False):
        source_path = raw_dir / str(row.source_file)
        if not source_path.exists():
            continue
        stage_label = STAGE_LABELS[str(row.stage)]
        date = str(row.recording_date)
        display_date = f"20{date[0:2]}-{date[2:4]}-{date[4:6]}"
        samples.append(
            PublicSample(
                key=f"trujillo:{date}:{int(row.well)}:{row.stage}",
                dataset_id="trujillo_cortical_organoid",
                dataset_label=label,
                sample_label=f"{display_date} | 孔 {int(row.well)} | {stage_label} | {row.treatment}",
                source_path=source_path,
                source_kind="trujillo_well",
                duration_s=120.0,
                data_doi="10.5281/zenodo.4751759",
                context=f"皮层类器官 | {stage_label} | 孔 {int(row.well)} | {row.treatment}",
                notice="该公开数据用于不同实验方案下的外部验证；单条记录不等于处理效应判断。",
                well=str(int(row.well)),
                start_s=float(row.window_start_s),
            )
        )
    return samples


def discover_public_samples(project_root: str | Path, demo_only: bool = False) -> dict[str, list[PublicSample]]:
    root = Path(project_root)
    if demo_only:
        return _demo_samples(root)

    groups: dict[str, list[PublicSample]] = {}
    for samples in (
        _forebrain_samples(root),
        _diazepam_samples(root),
        _gin_samples(root),
        _trujillo_samples(root),
    ):
        if samples:
            groups[samples[0].dataset_label] = samples
    return groups or _demo_samples(root)


def _normalized_key(sample: PublicSample) -> str:
    key = sample.key.removeprefix("demo:")
    return key.replace("__", ":")


def _diazepam_dose(sample: PublicSample) -> float:
    condition = _normalized_key(sample).split(":")[-1].rsplit("_", 1)[0]
    try:
        return float(condition.removeprefix("diazepam").removesuffix("uM"))
    except ValueError:
        return -1.0


def discover_public_pairs(groups: dict[str, list[PublicSample]]) -> list[PublicPair]:
    """Find matched public baseline-treatment pairs suitable for the intervention view."""
    samples = [sample for dataset_samples in groups.values() for sample in dataset_samples]
    pairs: list[PublicPair] = []

    diazepam = [sample for sample in samples if sample.dataset_id == "diazepam_organoid"]
    by_organoid: dict[str, list[PublicSample]] = {}
    for sample in diazepam:
        organoid = _normalized_key(sample).rsplit("_", 1)[-1]
        by_organoid.setdefault(organoid, []).append(sample)
    for organoid, organoid_samples in sorted(by_organoid.items()):
        baseline = next(
            (sample for sample in organoid_samples if "control_" in _normalized_key(sample)),
            None,
        )
        if baseline is None:
            continue
        for treatment in sorted(
            (sample for sample in organoid_samples if sample != baseline),
            key=_diazepam_dose,
            reverse=True,
        ):
            treatment_name = treatment.sample_label.split("|")[-1].strip()
            pairs.append(
                PublicPair(
                    key=f"diazepam:{organoid}:{treatment.key}",
                    label=f"地西泮类器官 {organoid} | 对照 -> {treatment_name}",
                    baseline=baseline,
                    treatment=treatment,
                    context="同一类器官的匹配对照与处理记录；默认仅量化影响，不自动判断疗效。",
                )
            )

    trujillo = [sample for sample in samples if sample.dataset_id == "trujillo_cortical_organoid"]
    by_well: dict[tuple[str, str], dict[str, PublicSample]] = {}
    for sample in trujillo:
        parts = _normalized_key(sample).split(":")
        if len(parts) < 4:
            continue
        _, recording_date, well, stage = parts[-4:]
        by_well.setdefault((recording_date, well), {})[stage] = sample
    for (recording_date, well), stages in sorted(by_well.items()):
        baseline = stages.get("baseline_control")
        treatment = stages.get("post_treatment")
        if baseline is None or treatment is None:
            continue
        treatment_name = treatment.sample_label.split("|")[-1].strip()
        display_date = f"20{recording_date[0:2]}-{recording_date[2:4]}-{recording_date[4:6]}"
        pairs.append(
            PublicPair(
                key=f"trujillo:{recording_date}:{well}",
                label=f"Trujillo {display_date} | 孔 {well} | 基线 -> {treatment_name}",
                baseline=baseline,
                treatment=treatment,
                context="同一孔位的基线与处理后记录；用于外部类器官变化演示，不等于疗效或毒性结论。",
            )
        )
    return pairs


def load_public_sample(sample: PublicSample) -> SpikeRecording:
    if sample.source_kind == "recording":
        return read_recording(sample.source_path, duration_s=sample.duration_s)
    if sample.source_kind == "gin_well":
        if sample.experiment_log_path is None or sample.protocol_duration_s is None:
            raise ValueError("GIN public sample is missing stage metadata")
        stage = load_gin_stage(
            sample.source_path,
            sample.experiment_log_path,
            sample.protocol_duration_s,
            sample.noisy_channels_path,
        )
        return build_well_recording(
            stage,
            sample.well,
            float(sample.duration_s or 180.0),
            sample.key.replace(":", "__"),
        )
    if sample.source_kind == "trujillo_well":
        return read_trujillo_well(
            sample.source_path,
            int(sample.well),
            start_s=sample.start_s,
            duration_s=sample.duration_s,
            recording_id=sample.key.replace(":", "__"),
        )
    raise ValueError(f"Unsupported public sample kind: {sample.source_kind}")
