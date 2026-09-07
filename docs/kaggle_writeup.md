# NeuroChip Copilot

**Submission Category: End-to-End System**

**End-to-end scope:** detected MEA spike events -> scope-aware QC -> functional features -> interpretable AI evidence -> matched multidimensional intervention evaluation -> reports and project history.

**Team:** `NeuroChip` | **Members and roles:** `赵梦颖 (team leader, system development and validation), 席玉杰 (member)` | **Registration form completed:** `Yes`

## Required links

- **Public demo video (maximum 5 minutes):** `https://youtu.be/wQTmfQ155Zc` (4 min 30 s, 1280x720, Chinese subtitles; China mirror: `https://www.bilibili.com/video/BV11Zbc6WEuS/`)
- **Public code repository:** `https://github.com/ZHAOYING0717/NeuroChip_Copilot`
- **Technical report PDF:** Attached to this Writeup as NeuroChip_Copilot_Technical_Report.pdf (16 pages); mirrored in the public repository under output/pdf/
- **Optional public application:** Not deployed; the dashboard runs locally with python demo.py --demo-only after installing requirements.txt

All links must be publicly accessible without login, permission requests, or payment before the final Writeup is submitted.

## Project summary

Neural organ chips and brain organoids can generate long multichannel electrophysiology event streams, but researchers still need separate scripts for file conversion, quality review, functional metrics, anomaly detection, treatment comparison, and reporting. NeuroChip Copilot turns detected extracellular spike events into one auditable workflow. It reads MATLAB, HDF5, or event-table CSV files; standardizes vendor exports; audits channel status and recording stability; extracts firing, inter-spike interval, STTC, burst, graph, neuronal-avalanche, and information-flow descriptors; explains model scores; and returns reference-relative phenotype and multidimensional intervention evidence through an interactive dashboard, PDF reports, and persistent projects.

The project is validated on four licensed public resources. On 45 forebrain-organoid recordings, it reproduced publisher firing-rate and 20 ms STTC values with maximum absolute errors below `1.0e-15`. A five-fold source-group-held-out benchmark across 135 controlled event perturbations achieved AUROC `0.858` (cluster-bootstrap 95% CI `0.796-0.915`). On 19 diazepam conditions from four organoids, the auxiliary v2 response magnitude tracked dose with leave-one-organoid-out Spearman `rho=0.904` (95% CI `0.641-0.991`) and high-dose AUROC `0.964` (95% CI `0.850-1.000`). Without retraining, it separated active pharmacology from controls in 66 matched human/rat 2D wells (AUROC `0.952`) and six known suppressive cortical-organoid treatments from six contemporaneous controls (AUROC `0.889`). The system is a research prototype for spike-event analysis, not proof of raw-voltage quality, causal connectivity, clinical state, efficacy, or toxicological safety.

## The problem

A useful neural-chip analysis should answer four questions in sequence:

1. Are the detected events internally usable?
2. What functional state does the preparation express?
3. Is the recording unusual relative to an explicit reference?
4. How strongly did a paired intervention change multiple functional dimensions, did the direction match the prespecified goal, did it approach a declared reference, and did it create network-silencing risk?

Absolute thresholds are fragile across organoids, chips, durations, and devices. Random row-level train/test splits are also unsafe because multiple conditions from one organoid can leak biological identity into both partitions. NeuroChip Copilot treats quality scope, biological grouping, and matched controls as first-class design constraints.

## Data and compliance

### Reference cohort

Naoya Itatani, *Spontaneous activity spike data and RNA-seq gene expression data from human forebrain organoids*, Zenodo, DOI [`10.5281/zenodo.20286251`](https://doi.org/10.5281/zenodo.20286251), CC BY 4.0. We use 45 individual eight-channel spike-event recordings and the publisher source table.

### External drug-response cohort

Tal Sharf, *Extracellular Recordings from Human Brain Organoids Using High-density CMOS Arrays*, Zenodo, DOI [`10.25349/D9031Z`](https://doi.org/10.25349/D9031Z), CC0 1.0. We use 19 three-minute conditions from four organoids across control and 3, 10, 30, and 50 uM diazepam. The associated study is Sharf et al., *Nature Communications* 13, 4403 (2022), DOI [`10.1038/s41467-022-32115-4`](https://doi.org/10.1038/s41467-022-32115-4), PMID 35906223.

### Frozen external stress-test cohort

Kapucu et al., *Comparative microelectrode array dataset of functional development of human PSC-derived and rat neuronal networks*, data DOI [`10.12751/g-node.wvr3jf`](https://doi.org/10.12751/g-node.wvr3jf), CC BY 4.0; *Scientific Data* 9, 120 (2022), DOI [`10.1038/s41597-022-01242-4`](https://doi.org/10.1038/s41597-022-01242-4), PMID 35354837. We match wells across baseline, pharmacology, and TTX stages in one human iPSC-derived and one rat embryonic cortical-neuron plate. The model remains frozen from the Sharf cohort.

These sources contain organoid or neuronal-culture research data and no personal or clinical information. URLs, checksums, licenses, and selective extraction rules are machine-readable in the repository manifests.

### Independent cortical-organoid cohort

Trujillo et al., *Complex Oscillatory Waves Emerging from Cortical Organoids Model Early Human Brain Network Development*, *Cell Stem Cell* 25, 558-569.e7 (2019), DOI [`10.1016/j.stem.2019.08.002`](https://doi.org/10.1016/j.stem.2019.08.002), PMID 31474560; data DOI [`10.5281/zenodo.4751759`](https://doi.org/10.5281/zenodo.4751759). The frozen model is evaluated on known spike/burst-suppressing interventions, contemporaneous untreated controls, and same-well natural drift. This is a small external organoid endpoint and is reported separately from the larger 2D GIN test.

## How it works

![NeuroChip Copilot architecture](https://raw.githubusercontent.com/ZHAOYING0717/NeuroChip_Copilot/master/docs/assets/figure0_architecture.png)

### 1. Scope-aware ingestion and QC

Every input becomes one device-neutral recording schema. The NeuroChip 1.0 table uses `recording_id,timestamp_s,channel_id` plus optional amplitude, duration, well, vendor, and schema fields; an Axion converter is chunked, checksummed, and resumable. A protocol duration may override an inferred duration without removing late events. Event QC reports active/inactive candidates, dominance, duplicates, refractory violations, out-of-range events, and six-segment firing stability. Inactive event channels are never silently called dead electrodes. A separate library API can screen true voltage arrays, but event uploads cannot establish voltage noise, saturation, or waveform quality.

### 2. Interpretable functional features

The system measures normalized firing statistics, ISI timing, 20 ms STTC synchrony, graph density and clustering, population entropy, network bursts, neuronal-avalanche size/duration/branching, bias-corrected mutual information and transfer entropy, and lag-1 predictive Granger direction. Information-flow direction is descriptive and not proof of synaptic causality. The phenotype model excludes duration, channel count, raw event count, amplitude scale, sampling rate, and QC score to reduce protocol leakage.

### 3. Reference-relative functional state and deviation evidence

Median imputation and robust scaling precede PCA and a 500-tree Isolation Forest. The functional-state-axis percentile reports the oriented first-PCA-axis position, while the reference-deviation percentile reports multivariate extremeness; neither is a health, maturity, disease, efficacy, or toxicity score. A deterministic Monte Carlo single-reference Shapley estimate explains the deviation-score difference from the robust training median. Evaluation preserves source groups and tests three defined event disruptions: half-channel dropout, added hyperactivity, and repeated hypersynchronous events. The primary model remains at 18 features because a 30-feature exploratory model reduced grouped-CV AUROC from `0.858` to `0.839`.

### 4. Multidimensional intervention evaluation

The user selects a baseline record, a treatment record, and an explicit goal. The evaluator robustly standardizes the 18 validated phenotype features and reports overall root-mean-square impact plus activity, timing, synchrony/network, organization, and bursting domains. Signed feature changes are scored against the selected goal; without a goal, the system quantifies change only. Distance to a user-supplied reference or the public cohort center is always reported, while the public center is explicitly not called a clinical healthy standard. Joint collapse of firing rate and active channels triggers a network-silencing warning that can override an apparently desirable suppression. An optional recovery record quantifies reversibility. Single-pair evidence is capped at moderate and advanced avalanche/information-flow changes remain exploratory.

### 5. Auxiliary matched-control response score

For each treatment, the model computes signed log feature changes from the same organoid's control. Version 2 combines mean ISI coefficient of variation and median ISI; exact squared-component fractions explain each score. It replaced the legacy timing-plus-burst model because internal leave-one-organoid-out performance and independent frozen-model stress tests both improved. This score answers how strongly a pair changed, not whether the change was beneficial or harmful. It appears in an auxiliary dashboard tab, and the isotonic dose estimate remains exploratory.

## Results and credibility

![Source reproduction and anomaly evaluation](https://raw.githubusercontent.com/ZHAOYING0717/NeuroChip_Copilot/master/docs/assets/figure1_validation.png)

- All 45 publisher rows matched.
- Anomaly AUROC: `0.858`; average precision: `0.927`.
- Per-perturbation AUROC: dropout `0.756`, hyperactivity `0.903`, hypersynchrony `0.914`.
- Fold AUROC range: `0.784-0.905`.
- Full-feature AUROC `0.858` versus network-only `0.827`, activity-only `0.735`, and spike-timing-only `0.546`.

![Matched-control diazepam response](https://raw.githubusercontent.com/ZHAOYING0717/NeuroChip_Copilot/master/docs/assets/figure2_drug_response.png)

- Held-out dose-response Spearman rho: `0.904` (cluster-bootstrap 95% CI `0.641-0.991`).
- Treated-only rho: `0.803`; blocked within-organoid permutation `p=0.0020`.
- High-dose, defined as at least 30 uM, AUROC: `0.964` (95% CI `0.850-1.000`).
- The legacy timing-plus-burst model reached rho `0.831`; the extended eight-feature research set reached `0.693`; the unpaired reference reversed the association at `-0.328`.
- Exploratory dose MAE was `7.16 uM`; response magnitude, not dose prediction, remains the supported endpoint.

![Frozen external response transfer](https://raw.githubusercontent.com/ZHAOYING0717/NeuroChip_Copilot/master/docs/assets/figure3_external_validation.png)

- Frozen active-pharmacology versus control AUROC: `0.952` (95% CI `0.881-0.997`; 55 active and 11 negative-control matched wells).
- Frozen TTX versus non-TTX AUROC: `0.950` (95% CI `0.865-1.000`; 26 TTX and 40 non-TTX matched wells).
- Human 2D AUROCs were `1.000/1.000`; rat 2D AUROCs were `0.931/0.903` for pharmacology/TTX.
- A 600 s sensitivity window retained pooled AUROCs `0.934/0.922`.

In the independent cortical-organoid test, six known suppressive treatment pairs had median auxiliary response `11.95` versus `1.01` in six contemporaneous untreated-control pairs (AUROC `0.889`, 95% CI `0.667-1.000`). All six active changes exceeded the same well's natural drift (one-sided paired Wilcoxon `p=0.0156`). The sample is small and tests change detection, not universal efficacy or toxicity.

## Runnable deliverable

The Streamlit application has three modes:

- **Recording analysis:** a dataset-grouped catalog exposes 45 forebrain-organoid records, 19 diazepam-organoid conditions, 198 GIN well-stage records, and 72 Trujillo cortical-organoid well-stage records when the full local data are present; uploaded MAT/HDF5/CSV files use the same QC, activity, network/criticality, Shapley, and PDF/HTML workflow. A data-domain notice states whether reference percentiles are within-domain or exploratory.
- **Intervention evaluation:** run a bundled matched public pair immediately, or upload two or more records; select baseline, treatment, goal, and optional reference/recovery; review multidimensional impact, goal alignment, reference distance, network-silencing risk, reversibility, uncertainty, and the auxiliary response score.
- **Project management:** SQLite-backed project and sample registration with persisted analysis summaries.

The public repository includes at least one lightweight licensed event CSV from each public source, matched diazepam-organoid and Trujillo cortical-organoid baseline-treatment pairs, trained models, and derived response tables, so both recording analysis and intervention evaluation start without the full source download. `python demo.py --demo-only` is the cross-platform judge entry point. The core checksummed pipeline is available through `python scripts/reproduce_all.py`; an optional flag recomputes external results only when the GIN files already exist locally. Automated tests cover schemas, readers, QC, advanced descriptors, models, reports, projects, the five-level evidence display, and all dashboard modes. Desktop and mobile browser checks verify that plots render and layouts do not overflow or overlap.

## Practical value

NeuroChip Copilot converts fragmented analysis into a repeatable assay review. Researchers can standardize vendor exports, inspect channel and stability evidence before interpreting biology, compare a recording with an explicit reference, identify which features drive a score, quantify a perturbation relative to its own baseline, evaluate whether its direction matches a prespecified experimental objective, screen for network silencing, export a report, and retain project history. The schema and project layer create a path toward larger multi-laboratory neural-chip data assets and prospective compound panels.

## Limitations

- Spike-event input cannot establish raw-voltage or spike-sorting quality; the optional raw-voltage API requires true voltage arrays.
- The phenotype percentile is relative to one 45-recording public cohort.
- Synthetic perturbations validate defined anomaly sensitivity, not disease or toxicity classification.
- The drug model is trained on four organoids and one compound; the external 2D data support response transfer but not cross-compound dose calibration.
- External wells come from one human and one rat plate, not a multi-site prospective study.
- Transfer entropy and predictive Granger direction do not establish causality.
- Intervention evaluation requires a biologically meaningful baseline. Favorable/unfavorable labels are conditional on the chosen goal, and one pair cannot replace matched vehicle/time controls, biological replicates, group uncertainty, or toxicology assays.
- No output constitutes clinical, efficacy, or toxicological safety advice.

## Reproduction

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python scripts/reproduce_all.py
python demo.py --demo-only
```

When checksummed GIN files are already present, add `--with-local-external-validation --resume`. This flag does not download data.

OpenAI Codex assisted code development, testing, and documentation. Every reported statistic is produced by the public local pipeline; the final application has no external AI API dependency.

## Competition alignment

- **Problem Importance and Potential Impact (30%):** reduces hidden format, duration, QC, matching, and interpretation decisions in a repeated neural-chip workflow.
- **Technical Approach and Innovation (30%):** combines leakage-resistant reference modeling, deterministic feature attribution, conservative feature selection, and goal-aware paired evaluation.
- **Results and Validation (20%):** separates source reproduction, grouped controlled testing, held-out organoid association, frozen cross-domain stress testing, and independent cortical-organoid transfer.
- **Reproducibility and Implementation Quality (10%):** public code, pinned environment, one-command Demo, checksums, checkpoints, tests, models, data/model cards, and report exports.
- **Presentation Quality (10%):** a maximum-five-minute real-operation video, concise Writeup, technical PDF, four figures, and an optional public application.
