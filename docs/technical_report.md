# NeuroChip Copilot

## Quality-Aware Event-Level Functional Phenotyping and Multidimensional Intervention Evaluation for Neural Organ-Chip Electrophysiology

**Team:** NeuroChip Copilot Team  
**Submission category:** End-to-End System  
**Competition:** AI4S Open Innovation: AI for Life Science  
**Report version:** 4.0  
**Date:** 23 August 2026  
**Code license:** MIT  

## Abstract

Electrophysiology can provide a continuous functional readout from neural organ chips and brain organoids, but analysis is often fragmented across vendor formats, quality checks, descriptive metrics, models, and reports. NeuroChip Copilot is a runnable research system that converts detected extracellular spike events into an auditable functional assessment. It standardizes event tables, separates channel and recording-stability quality evidence from biological interpretation, reports classical and advanced network descriptors, explains model scores, and compares a treatment with a user-selected baseline across five validated functional domains. The intervention evaluator separates change magnitude from goal-dependent direction, always reports reference distance, screens network-silencing risk, optionally quantifies recovery, and caps single-pair evidence at moderate. On 45 public forebrain-organoid recordings, the pipeline reproduced publisher firing-rate and 20 ms spike time tiling coefficient values with maximum absolute errors of 8.88e-16 and 1.11e-16. Five-fold group-held-out anomaly detection reached AUROC 0.858 (cluster-bootstrap 95% CI 0.796-0.915). In 19 diazepam conditions from four organoids, an auxiliary two-feature response score tracked dose with leave-one-organoid-out Spearman rho 0.904 and transferred without retraining to human/rat 2D pharmacology (AUC 0.952) and a small independent cortical-organoid treatment endpoint (AUC 0.889). The evidence supports a reproducible research workflow for detected events, not proof of raw-voltage quality, causal connectivity, clinical state, efficacy, or toxicological safety.

## 1. Problem definition

The competition asks teams to define a meaningful AI and organ-on-a-chip problem and deliver a runnable, explainable, and reproducible system [1]. Neural organ chips and brain organoids are a strong setting for such a system because microelectrode arrays (MEAs) can generate long, multichannel event streams whose value depends on consistent processing and interpretable comparison. A scientist typically needs to answer four questions before acting on an experiment: whether the detected events are internally usable, what functional state the preparation expresses, whether the recording is unusual relative to an appropriate reference, and whether a paired treatment produces a reproducible functional change.

Existing study scripts commonly answer only one part of this sequence. Raw spike counts can confound recording duration and channel number. Synchrony can be confounded by firing rate when an unsuitable metric is used. An anomaly score can silently learn acquisition settings instead of biology. A drug-response model can appear accurate if control and treatment samples from the same organoid leak across training and test sets. The practical gap is therefore not another unconstrained classifier. It is a quality-aware, leakage-resistant workflow that connects event ingestion, functional measurements, model evidence, and reports.

NeuroChip Copilot addresses this gap for detected spike-event inputs. Its intended users are organ-chip researchers, neurophysiology laboratories, and preclinical assay teams who need rapid exploratory quality review, functional phenotyping, or paired perturbation assessment. The primary output is evidence that can guide review and experiment planning. The output is not an automated biological verdict.

### 1.1 Competition category and end-to-end scope

This submission declares the **End-to-End System** category. The system is end to end at the detected-event analysis level: heterogeneous MEA exports enter through a standard reader; event and recording-stability quality checks establish whether interpretation should proceed; normalized functional features describe the preparation; AI models provide reference-relative phenotype and deviation evidence; matched records enter a multidimensional intervention evaluator; and the same application exports reports and retains project history. It does not claim to be end to end from cell culture or raw electrode voltage because the public inputs are already detected spike events. That boundary is shown in the interface, report, data card, and model card.

The official evaluation uses a **30/30/20/10/10** weighting for Problem Importance and Potential Impact, Technical Approach and Innovation, Results and Validation, Reproducibility and Implementation Quality, and Presentation Quality, respectively [1]. The report follows that logic: Sections 1 and 8 establish the research need and workflow value; Sections 2 and 4 define the technical contribution; Sections 5 and 6 present the evidence hierarchy; Sections 7 and 10 cover implementation and reproduction; and the interface, figures, report, and video script support presentation quality.

The category choice matters because the contribution is not one leaderboard model. A model-only submission could expose an anomaly percentile or response magnitude while leaving researchers to reconstruct data conversion, quality scope, baseline matching, interpretation, and reporting. NeuroChip Copilot instead packages these dependent decisions into one reproducible workflow. The AI components are embedded where they add value: robust multivariate reference modeling prioritizes unusual patterns, feature attribution exposes why a score changed, and goal-aware paired reasoning separates impact magnitude from desired direction and risk.

### 1.2 Problem importance and potential impact

MEA analysis in neural organ-chip studies is vulnerable to three practical failure modes. First, incomparable vendor exports and implicit duration assumptions can change rates before modeling begins. Second, weak quality evidence can be mistaken for biology, particularly when event-only silence is called a dead electrode or when a recording decays during acquisition. Third, treatment effects can be overstated when unpaired controls or row-level random splits leak organoid identity. These failures affect experiment triage, assay iteration, and the credibility of conclusions even when the final classifier is technically accurate.

The system addresses these failure modes without requiring paid services or proprietary cloud models. A laboratory can inspect one recording, compare a treatment with its own baseline, export a structured report, and retain an audit history from the same interface. The expected impact is therefore workflow-level: fewer hidden preprocessing choices, clearer evidence boundaries, and faster movement from detected events to a reviewable analysis package. We do not claim a measured reduction in labor time because no prospective time-and-motion study was performed. The present evidence instead demonstrates reproducibility, discrimination under defined tests, external transfer of change detection, and immediate usability.

## 2. Contribution and system overview

The project contributes six linked capabilities:

- A NeuroChip 1.0 event schema and device-neutral readers for MATLAB v7.3, legacy MATLAB, HDF5, and CSV, plus a checksummed resumable Axion converter.
- Event-level channel status, six-segment recording stability, and an optional raw-voltage screening API with explicit scope boundaries.
- Classical activity/network features plus neuronal-avalanche and statistical information-flow descriptors.
- A conservative reference-cohort anomaly model with single-reference Monte Carlo Shapley explanations.
- A goal-aware multidimensional intervention evaluator with reference distance, network-silencing risk, optional reversibility, evidence grading, and an auxiliary matched-control response score.
- A three-mode Streamlit application with PDF/HTML reports and SQLite project/sample persistence.

![Figure 1. NeuroChip Copilot connects spike-event input, quality scope, functional features, interpretable models, validation, and reusable outputs.](assets/figure0_architecture.png)

The one-sentence argument is: NeuroChip Copilot combines standardized spike-event ingestion, explicit quality boundaries, conservative model selection, feature-level explanations, and goal-aware baseline comparison into an auditable neural electrophysiology workflow supported by source reproduction, group-isolated validation, and frozen cross-domain stress tests.

### 2.1 Technical innovation relative to conventional analysis

The technical innovation is the coupling of scope-aware measurement, leakage-resistant AI evaluation, and target-aware paired interpretation. Conventional MEA scripts often compute firing rate, burst statistics, or correlation independently. Those summaries remain useful, but they do not answer whether a score is unusual relative to a documented cohort, which features produced that result, whether the model learned acquisition proxies, or whether a treatment moved function in the desired direction without silencing the network.

NeuroChip Copilot makes five design moves beyond a descriptive script. First, it separates event-level quality evidence from raw-voltage claims, preventing timestamp tables from being overinterpreted. Second, it excludes acquisition and QC variables from the phenotype model and preserves biological source groups during validation. Third, it retains advanced avalanche and information-flow descriptors for scientific review but refuses to add them to the primary model when held-out performance declines. Fourth, it explains reference deviation with deterministic Shapley contributions and paired response with exact component fractions. Fifth, it treats intervention assessment as a multidimensional, goal-conditional decision problem rather than equating any large change with success.

These moves produce an auditable system rather than a black-box score. The main novelty claim is therefore bounded: the project integrates conservative model selection, explicit quality scope, interpretable reference-relative phenotyping, and goal-aware paired intervention evaluation in one runnable event-level neural-chip workflow. It does not claim a new foundational machine-learning architecture or causal discovery method.

## 3. Data, licensing, and compliance

### 3.1 Reference phenotype cohort

The reference cohort is *Spontaneous activity spike data and RNA-seq gene expression data from human forebrain organoids*, deposited by Naoya Itatani on Zenodo under CC BY 4.0 [2]. The analysis uses 45 individual MATLAB v7.3 recordings represented in the publisher source table. Each file contains eight channels of detected spike times and amplitudes plus recording metadata. Recording durations vary across the cohort. The pipeline uses the declared duration for every rate, occupancy, and time-window calculation.

This cohort serves three roles: source-value reproduction, model fitting for a functional reference distribution, and controlled perturbation evaluation. No age label was inferred because a per-recording age mapping was not available in the extracted individual files. RNA sequencing data were not used.

### 3.2 Diazepam response cohort

The external response cohort is *Extracellular Recordings from Human Brain Organoids Using High-density CMOS Arrays*, deposited by Tal Sharf on Zenodo under CC0 1.0 [3]. Its associated peer-reviewed study reported high-density CMOS MEA recordings and diazepam-induced changes in inter-spike intervals, burst dynamics, and functional connectivity [4]. The project uses 19 unique three-minute Kilosort2 recordings from four organoids: four controls; four conditions each at 3, 10, and 50 uM; and three conditions at 30 uM.

The paper defines each recording as three minutes. Six files contained a small number of event timestamps at or beyond 180 s, consistent with a boundary or alignment tail. The pipeline therefore fixes the protocol duration at 180 s, preserves all input events for audit, and excludes out-of-range events from every feature. Across the six affected files, 47 events were excluded; the largest file-level fraction was 0.702%, and the other affected fractions were below 0.1%.

### 3.3 Frozen external pharmacology cohort

The external stress-test resource is *Comparative microelectrode array dataset of functional development of human pluripotent stem cell-derived and rat neuronal networks* by Kapucu and colleagues, released under CC BY 4.0 with data DOI 10.12751/g-node.wvr3jf [5]. The project uses detected-spike tables, experiment logs, and noisy-electrode declarations from one human iPSC-derived cortical-neuron plate and one rat embryonic cortical-neuron plate. Wells are matched across baseline, pharmacology, and TTX stages.

The primary window is the first 180 s so that the external input duration matches the response model's organoid training protocol; 600 s is a duration sensitivity analysis. Each stage comparison contains 66 matched wells. Pharmacology versus baseline includes 55 active treatments and 11 negative controls. TTX versus pharmacology includes 26 TTX and 40 non-TTX wells. These are 2D cultures rather than organoids, and the two comparisons reuse wells; they test transfer of unsigned response magnitude, not organoid identity, drug mechanism, or dose.

### 3.4 Independent cortical-organoid pharmacology cohort

The second frozen external resource uses cortical-organoid MEA files associated with Trujillo et al. [6], released under CC BY 4.0 with data DOI 10.5281/zenodo.4751759. The validation uses paired same-date baseline and pharmacology recordings from two labeled dates. Six known spike/burst-suppressing treatment pairs are compared with six contemporaneous untreated-control pairs. A second baseline window from each active well estimates same-well natural drift. The primary window is 120 s and a prespecified 90 s window tests duration sensitivity. The frozen model is never refit on this cohort.

### 3.5 Compliance and privacy

All four sources are public research datasets with explicit licenses. Checksummed source URLs, creators, byte sizes, extraction destinations, and MD5 values are recorded in `data/manifests/datasets.json` and `data/manifests/external_validation.json`. The included lightweight event CSV is an attributed derivative of the Itatani source; response summaries derive from the Sharf source; external summaries retain Kapucu and Trujillo dataset attribution.

The data contain organoid electrophysiology and no personal, clinical, or identifying information. The project does not use protected health information. It does not infer patient state or make clinical decisions. Third-party Python packages and licenses are listed in `THIRD_PARTY_NOTICES.md`.

## 4. Methods

### 4.1 Input normalization and duration guard

All readers return one `SpikeRecording` object containing a recording identifier, one sorted finite timestamp vector per channel or unit, a positive duration, optional amplitudes, channel identifiers, and metadata. Legacy MATLAB sample indices are converted to seconds using `sampling_rate` or `fs`. MATLAB empty-array markers are interpreted as empty event trains instead of numeric placeholders.

A protocol duration can override a reader-inferred duration without deleting late events. Quality control evaluates the original vectors. Functional features use a derived valid window with `0 <= t < duration`. This design makes boundary handling reviewable and prevents a few late timestamps from silently extending a nominal 180 s experiment to 190 s.

### 4.2 Event-level quality control

For event input, per-channel checks include event count, firing rate, active status, out-of-range fraction, exact-duplicate fraction, refractory-interval violation fraction below 1 ms, and median inter-spike interval (ISI). Channel status is `good`, `inactive_candidate`, `review_event_proxy`, or `excluded_event_invalid`. Inactive channels are candidates rather than dead electrodes because detected events cannot distinguish biological silence, disconnection, or hardware failure.

Recording stability divides the protocol into six equal segments and reports population-rate coefficient of variation, last-to-first activity log2 ratio, and a normalized trend. The quality score begins at 100 and applies bounded penalties for low active-channel fraction, dominant-channel concentration, invalid events, refractory violations, and instability. Grades are `pass` at 75 or above, `review` from 50 to below 75, and `fail` below 50. The score is not a phenotype-model input.

When a true channels-by-samples voltage array and sampling frequency are supplied programmatically, a separate module estimates robust noise, baseline drift, line-noise ratio, saturation, and near-dead channels. This API does not convert event uploads into voltage evidence and has not been validated as a device-specific regulatory QC procedure.

### 4.3 Functional feature extraction

The feature table covers seven complementary views of function:

- Activity: mean, median, standard deviation, maximum, and coefficient of variation of per-channel firing rates; active-channel and dominant-channel fractions.
- Spike timing: median ISI and mean per-channel ISI coefficient of variation.
- Synchrony: mean, median, and maximum pairwise STTC with a 20 ms coincidence window. STTC was selected because it controls for firing-rate effects in pairwise spike-train association [7].
- Network topology: density at STTC greater than or equal to 0.1 and weighted clustering.
- Population dynamics: binned population entropy, network-burst rate, mean burst duration, and mean participating-channel fraction.
- Criticality descriptors: neuronal-avalanche rate, size, duration, branching ratio, and distance from branching ratio one. The adaptive bin equals the mean positive inter-event interval clipped to 1-100 ms; consecutive nonempty bins form one avalanche, following the general avalanche framework [8].
- Statistical information flow: bias-corrected pairwise mutual information, first-order binary transfer entropy, and lag-1 predictive Granger log-variance ratio using 50 ms bins and at most 24 active channels.

Network bursts are identified from 50 ms population bins using a robust threshold based on the median and median absolute deviation. This rule is deterministic and used consistently across cohorts. Burst and avalanche definitions are engineering operationalizations. Mutual information, transfer entropy, and predictive Granger direction describe dependence or predictability; they do not establish synaptic causality.

### 4.4 Functional phenotype and anomaly model

The phenotype model uses the previously validated 18 normalized functional features. It excludes duration, channel count, raw event count, amplitude scale, sampling rate, event-quality score, and out-of-range count. Median imputation, robust scaling, PCA, and a 500-tree Isolation Forest produce reference percentiles [9]. A 30-feature exploratory variant that added stability, avalanche, and information-flow descriptors reduced grouped-CV AUROC to 0.839 versus 0.858; the 18-feature model therefore remains primary while advanced descriptors remain visible for research review.

For a new sample, deterministic Monte Carlo single-reference Shapley values decompose the anomaly-score difference from the robust training median. Sixty-four fixed-seed feature permutations are used in the interface. The contributions telescope to the model-score difference but are model explanations, not causal biological effects.

The evaluation creates three controlled event-level perturbations for each held-out recording. Channel dropout removes events from half the channels. Hyperactivity adds uniformly distributed events at three times the baseline rate. Hypersynchrony injects eight events per channel around common centers every 10 s with 3 ms jitter. These perturbations are used only for sensitivity testing; they are not presented as biological disease or toxicity labels.

### 4.5 Multidimensional intervention evaluation

The dashboard accepts at least two records and requires the user to assign baseline and treatment roles. Six goals are available: quantify only, reduce hyperactivity, increase hypoactivity, reduce hypersynchrony, preserve function, or move toward a reference state. Good/bad interpretation is therefore conditional on an explicit experimental objective; quantify-only mode produces no target-alignment score.

Baseline and treatment are transformed by the fitted phenotype model's median imputer and robust scaler. For the 18 validated features, the overall impact is the root mean square of treatment-minus-baseline standardized changes. Five domain summaries cover activity, spike timing, synchrony/network, population organization, and network bursting. Signed feature changes are compared with a prespecified direction map for the selected goal. The score reports alignment rather than biological truth.

Distance to a user-supplied matched reference is always reported. If none is supplied, the zero point of the public robust-scaled training distribution is used and labeled as a public functional reference, not a clinical healthy standard. A combined drop of at least 80% in mean firing rate and marked active-channel loss triggers high network-silencing risk and overrides an apparently desirable suppressive direction. An optional recovery or washout record is projected into the same space; recovery toward baseline is expressed as a percentage of the treatment displacement. Event-quality failure blocks good/bad interpretation. A single pair is capped at moderate evidence because it lacks biological-replicate uncertainty.

Stability, neuronal-avalanche, and information-flow descriptors are shown in an advanced table but do not enter the intervention verdict. This keeps mechanism-oriented descriptors visible without silently enlarging the validated primary feature set.

### 4.6 Auxiliary matched-control response score

For each organoid and each selected feature `x`, the paired component is

`d(x) = signed_log1p(x_treatment) - signed_log1p(x_control)`.

Version 2 uses mean ISI coefficient of variation and median ISI. Version 1 additionally used mean network-burst duration. The source study reported longer ISIs, lower ISI variability, and shorter bursts at 50 uM [4], but the two-feature timing model improved leave-one-organoid-out and frozen external metrics. Each component is divided by its training interquartile range, with a standard-deviation fallback. The response magnitude is the root mean square of standardized paired components. Exact squared-component fractions sum to one and explain each paired score. The response magnitude quantifies how strongly two timing features changed; it does not determine whether the change was beneficial or harmful and is now presented as auxiliary evidence.

An isotonic regression maps response magnitude to diazepam dose for an exploratory display. Because the cohort is small and contains one compound, the calibrated dose is not the primary output. The dashboard displays this mapping only for explicitly identified public diazepam pairs and disables it for other compounds, external domains, and generic uploads.

### 4.7 Reports, standardization, and projects

Single-recording workflows export PDF and HTML reports. Paired intervention workflows export a comprehensive HTML report plus JSON and CSV tables containing goal, multidimensional impact, feature direction, reference distance, silencing risk, reversibility, evidence grade, and interpretation boundaries. The NeuroChip 1.0 CSV schema preserves recording, timestamp, channel, optional amplitude/duration/well, vendor, and schema version. A local SQLite store records projects, samples, and append-oriented analysis summaries. It is a research organizer rather than a regulated laboratory information system.

## 5. Experimental design and statistics

### 5.1 Source-data reproduction

Extracted mean firing rate and mean STTC were joined by recording identifier to the 45 rows in publisher source-data sheet `ST1`. Reproduction passed only if every extracted row matched and both maximum absolute errors were below 1e-10.

### 5.2 Anomaly evaluation

Five-fold GroupKFold used source `fs_id` as the group, yielding 16 unique source groups. No source group appeared in both train and test partitions. Each held-out clean recording and its three perturbations were scored by a model fit only on clean recordings from training groups. AUROC and average precision were computed over all held-out observations. The AUROC interval used 2,000 bootstrap resamples clustered by source recording. Performance was also reported separately by perturbation, fold, feature ablation, and alert threshold.

### 5.3 Drug-response evaluation

LeaveOneGroupOut used organoid identifier as the group. In each fold, the response model and isotonic calibration were fit on three organoids and evaluated on the fourth. Treatment samples in the test organoid were paired only with that held-out organoid's control, matching the intended assay workflow without using held-out treatment labels for feature scaling.

The primary association was Spearman correlation between dose and held-out response magnitude. A 95% interval used 3,000 bootstrap resamples clustered by organoid. The treated-only test permuted nonzero dose labels within organoid 5,000 times while keeping each zero-dose control fixed. High dose was defined prospectively as at least 30 uM. Model and matching ablations used the same outer folds.

### 5.4 Frozen external stress test

The final v2 joblib artifact was trained only on the Sharf organoid cohort and hashed before external scoring. For each GIN well, pharmacology was paired to its baseline and TTX to its pharmacology stage. Active treatments were compared with declared negative controls by AUROC, a 3,000-iteration class-stratified bootstrap interval, Mann-Whitney test, and rank-biserial effect. Results were reported pooled and separately for human and rat domains. Diazepam dose outputs were not interpreted for external compounds.

### 5.5 Independent cortical-organoid stress test

The same frozen artifact scored 120 s baseline-to-treatment pairs and baseline-to-second-baseline natural drift pairs. Known spike/burst-suppressing treatments were compared with contemporaneous untreated controls by AUROC, a 3,000-iteration class-stratified bootstrap interval, Mann-Whitney test, and rank-biserial effect. A one-sided paired Wilcoxon test compared each active well's treatment response with its own natural drift. The 90 s sensitivity window repeated the labeled endpoint. External dose estimates were not interpreted.

### 5.6 Evidence hierarchy and leakage controls

The experiments form a five-level evidence hierarchy. Level 1 reproduces two publisher values for all 45 source records and verifies that parsing, duration handling, empty channels, and STTC are implemented as intended. Level 2 evaluates controlled perturbation sensitivity while isolating source groups. Level 3 tests a real dose association while leaving one complete organoid out. Level 4 freezes the response model before scoring matched wells from different species and a different 2D culture protocol. Level 5 applies the same frozen model to an independent cortical-organoid protocol and compares treatment change with both contemporaneous controls and same-well drift.

Each level addresses a different failure mode and cannot substitute for the next. Exact reproduction does not establish biological discrimination. Controlled perturbation AUROC does not validate disease labels. A dose association in four organoids does not establish cross-compound calibration. A frozen 2D stress test tests transfer but not organoid performance. The small cortical-organoid endpoint is closer to the target application but remains retrospective and underpowered for universal claims. The report, dashboard evidence table, and claim-evidence map preserve these distinctions.

Leakage controls follow the biological unit rather than the row. Related forebrain records remain together through `fs_id`; all conditions from one organoid remain together in drug-response folds; held-out treatments are paired only to the held-out organoid's control; and external data never update the model, scaler, feature list, or dose calibration. Confidence intervals resample the declared grouping unit when available. These choices reduce optimistic performance caused by shared preparation identity, but they do not remove dependence among wells from the same plate or replace multi-site prospective validation.

## 6. Results

### 6.1 Exact source reproduction and anomaly sensitivity

All 45 reference recordings matched the source table. The maximum absolute firing-rate error was 8.88e-16, and the maximum absolute STTC error was 1.11e-16. This test validates file interpretation, empty-channel handling, declared durations, and the 20 ms STTC implementation against independently published values.

The functional anomaly model achieved AUROC 0.858 with cluster-bootstrap 95% CI 0.796-0.915 and average precision 0.927. Per-perturbation AUROC was 0.756 for channel dropout, 0.903 for hyperactivity, and 0.914 for hypersynchrony. Fold AUROCs ranged from 0.784 to 0.905. A 90th-percentile alert threshold gave balanced accuracy 0.719; a more conservative 95th-percentile threshold gave 0.567. The dashboard therefore reports continuous evidence and does not hide threshold sensitivity.

![Figure 2. Publisher-value reproduction and group-held-out anomaly validation. The benchmark contains 45 clean recordings and 135 controlled perturbations.](assets/figure1_validation.png)

Feature ablation supported the multiscale design. Full functional features achieved AUROC 0.858, network-only features 0.827, activity-only features 0.735, and two spike-timing features 0.546. Network organization carried substantial signal, while the complete model performed best.

### 6.2 Leave-one-organoid-out diazepam response

Held-out v2 response magnitude increased with dose at Spearman rho 0.904 (cluster-bootstrap 95% CI 0.641-0.991). After controls were removed, the treated-only association remained rho 0.803 with blocked-permutation p=0.0020. High-dose discrimination reached AUROC 0.964 (95% CI 0.850-1.000). Exploratory isotonic calibration had mean absolute error 7.16 uM, root mean squared error 12.68 uM, R-squared 0.562, and Spearman rho 0.857. Response magnitude remains the supported auxiliary endpoint for this fitted model.

![Figure 3. Real diazepam response across four organoids. The primary two-feature score is evaluated by leaving one complete organoid out and pairing test treatments only to that organoid's held-out control.](assets/figure2_drug_response.png)

The primary two-feature model improved on the legacy timing-plus-burst model (rho 0.831; AUROC 0.929), the extended eight-feature research model (rho 0.693; AUROC 0.845), ISI CV alone (rho 0.794; AUROC 0.881), and burst duration alone (rho 0.672; AUROC 0.821). An unpaired training-control reference reversed the association (rho -0.328; AUROC 0.286). The external frozen test below reduces, but does not eliminate, the risk that selecting v2 on this small internal cohort overfit the model choice.

### 6.3 Frozen external 2D response transfer

At 180 s, active pharmacology versus negative controls reached pooled AUROC 0.952 (95% CI 0.881-0.997; 55 active and 11 negative wells), two-sided Mann-Whitney p=2.64e-6, and rank-biserial effect 0.904. Human and rat AUROCs were 1.000 and 0.931. TTX versus non-TTX reached pooled AUROC 0.950 (95% CI 0.865-1.000; 26 TTX and 40 negative wells), p=8.51e-10, and rank-biserial effect 0.900; domain AUROCs were 1.000 and 0.903.

The 600 s sensitivity analysis retained pooled AUROCs of 0.934 for pharmacology and 0.922 for TTX. These results show that the frozen two-feature distance responds to strong perturbations in two additional culture domains. They do not show that external compounds share a dose scale, that 2D cultures are organoids, or that response magnitude measures efficacy or toxicity.

![Figure 4. The two-feature v2 model improves internal held-out metrics and, without retraining, separates active pharmacology and TTX in matched human and rat 2D neuronal-network wells.](assets/figure3_external_validation.png)

### 6.4 Independent cortical-organoid response transfer

At 120 s, six known suppressive treatment pairs had median response magnitude 11.95 versus 1.01 in six contemporaneous untreated-control pairs. AUROC was 0.889 (stratified-bootstrap 95% CI 0.667-1.000), two-sided Mann-Whitney p=0.0260, and rank-biserial effect 0.778. Active-treatment response exceeded same-well natural drift in all six active wells; median natural-drift magnitude was 0.33 and the one-sided paired Wilcoxon p=0.0156. The 90 s sensitivity endpoint retained AUROC 0.861. The sample size is small and the treatments are strongly suppressive, so this evidence supports cross-organoid-protocol change detection but not compound-general efficacy, toxicity, or dose calibration.

### 6.5 What the combined results establish

The strongest system-level conclusion comes from agreement among different tests rather than one high AUC. Source reproduction shows that core measurements are faithful. Group-held-out evaluation shows sensitivity to defined event disruptions without placing related source groups in both train and test sets. Leave-one-organoid-out validation shows that a simple paired timing score follows diazepam dose across held-out preparations in the available cohort. Frozen external tests then show that the same change magnitude responds to strong perturbations in other cultures and in a small independent organoid protocol.

The external results are informative because the model is unchanged and negative controls are included. A model that simply returns a large score for every new file would fail these comparisons. At the same time, active treatments were expected to alter activity, so high discrimination alone is not the final scientific contribution. Their value is narrower: they show that the paired representation is not limited to identifying the files on which it was trained and that it can separate biological change from matched-control or natural-drift change under several acquisition contexts.

The results do not validate the dashboard's favorable or unfavorable intervention language as a biological endpoint. That language remains conditional on a user-declared experimental goal and a deterministic set of feature directions. The multidimensional evaluator is supported as transparent computation and workflow logic, while efficacy, toxicity, rescue, and safety require future labels, biological replicates, matched vehicle and time controls, and dedicated assays. This separation prevents the auxiliary response AUC from being mistaken for validation of the complete decision-support output.

## 7. Software implementation and user workflow

The implementation uses Python 3.11-3.14, NumPy, SciPy, pandas, h5py, scikit-learn, NetworkX, Plotly, Matplotlib, ReportLab, Joblib, Streamlit, and SQLite. Randomized operations use fixed seeds. Feature batches write per-recording JSON checkpoints and support `--resume`. Downloads preserve partial files, verify byte size and MD5, reject unsafe ZIP paths, and selectively extract declared content.

The dashboard provides three workflows. Recording analysis groups all available public recordings by source dataset and displays channel/stability QC, activity, network/criticality descriptors, functional-state-axis and reference-deviation percentiles, Shapley evidence, and PDF/HTML reports; uploaded records use the same workflow. A source-specific notice distinguishes within-domain from cross-domain percentile interpretation. Intervention evaluation can run a bundled matched public pair immediately or accept user uploads with assigned baseline, treatment, goal, and optional reference/recovery records; it returns multidimensional impact, goal alignment, reference-distance change, network-silencing risk, reversibility, uncertainty, and the auxiliary response score. Project management creates projects and samples and persists analysis summaries in SQLite.

The interface is exercised with Streamlit's application test framework in all three modes and with a lightweight deployment bundle containing at least one runnable record from each public source plus matched diazepam-organoid and Trujillo cortical-organoid pairs. Browser checks cover desktop and mobile viewports, rendered Plotly canvases, page errors, horizontal overflow, and overlap. Automated tests cover schemas, readers, QC, advanced descriptors, Shapley/component explanations, paired modeling, standard conversion, PDF generation, project persistence, the public-sample catalog, and dashboard modes.

The model-explanation page also presents the five-level evidence hierarchy directly from checked-in JSON results. Each row states the dataset and split, quantitative result, supported conclusion, and unsupported conclusion. This makes system validation visible during a live demonstration without reintroducing a separate public-cohort screen or turning one recording into a claim about treatment value.

## 8. Practical value

NeuroChip Copilot targets repeated research workflows rather than a single benchmark label. A laboratory can standardize vendor event exports, inspect channel and stability evidence before interpreting biology, compare a preparation with a documented reference, inspect which features drive a score, evaluate a treatment against its own control, export a report, and retain project history. This reduces manual spreadsheet work and makes assumptions visible at interpretation time.

For drug discovery, a target-aware multidimensional comparison is more informative than treating any large change as a success. Matching each treatment to its own baseline controls part of the preparation-to-preparation variation, while the silencing screen helps distinguish desired normalization from functional collapse. For experiment operations, continuous reference-deviation percentiles can prioritize review without declaring recordings invalid. The NeuroChip schema, data cards, manifests, reports, and project database provide a foundation for future neural-chip cohorts and multimodal measurements.

### 8.1 Representative use cases

In assay quality review, a researcher can open a detected-event file and inspect channel balance, invalid timestamps, refractory violations, and six-segment activity stability before reading a phenotype percentile. The same page then exposes the raster, population activity, firing-rate distribution, network associations, avalanche descriptors, information-flow descriptors, and score contributions. This ordering reduces the risk that a visually striking model output distracts from unstable or incomplete event data.

In perturbation screening, the researcher assigns a baseline and treatment from the same preparation and states the intended objective. The system reports overall impact separately from goal alignment, then shows which functional domains and individual features changed. A matched reference can answer whether the treatment moved toward or away from a declared target state. A recovery recording can assess return toward baseline, while the silencing screen flags a collapse in firing and active channels. The auxiliary two-feature response magnitude remains available for comparison with the validated diazepam and external change-detection evidence, but it is not the verdict.

In collaborative or repeated work, the NeuroChip event schema and converter reduce format-specific code, PDF/HTML/CSV/JSON exports create reviewable artifacts, and the SQLite project view preserves sample and analysis history. These functions target the handoff between computational and experimental team members. The software does not replace a laboratory information-management system, versioned raw-data archive, or regulated decision process.

### 8.2 Adoption and extension path

The immediate deployment path is local and offline. The lightweight repository includes six public examples, two matched pairs, model artifacts, and derived validation results, so judges and laboratories can inspect the complete interface without downloading large raw archives. A full installation can discover locally downloaded records automatically. No account, external API, or paid inference service is required.

For a new laboratory, responsible adoption requires a local reference panel and matched controls. The existing feature and report pipeline can run immediately, but reference percentiles and intervention goals should be recalibrated under the local device, culture, duration, and protocol. Future versions can add raw-voltage adapters, plate-level hierarchical uncertainty, prospective compound panels, multimodal molecular measurements, and role-based project storage. These are extensions of the current architecture, not capabilities claimed by this submission.

## 9. Credibility, failure modes, and boundaries

The project includes safeguards against overclaiming. Source values are reproduced before models are evaluated. Acquisition and QC variables are excluded from phenotype input. Biological groups are isolated in cross-validation. Drug effects are paired within organoid. Advanced features are not added to the primary model when held-out performance falls. External data are scored by a frozen artifact. Ablations include a failed unpaired reference. Every report states the event-level scope.

Important limitations remain:

- Event-table workflows cannot establish raw-voltage or spike-sorting quality. The optional voltage-array API is a generic screen and has not been validated against every MEA device.
- The phenotype reference is 45 recordings from one public forebrain-organoid resource. Percentiles are reference-relative and may shift with laboratory, device, culture, geometry, or protocol.
- The anomaly labels are synthetic event perturbations. They validate sensitivity to defined disruptions, not disease, toxicity, efficacy, or biological abnormality.
- The diazepam training/validation contains four organoids and one compound. External evidence adds one human and one rat 2D plate plus a 12-pair cortical-organoid endpoint, but neither is a prospective multi-site or cross-compound efficacy validation.
- The burst detector is a deterministic cross-cohort approximation, not a reproduction of every source study's burst method.
- Avalanche bins and first-order information-flow estimators are operational descriptors; transfer entropy and predictive Granger direction do not prove causality.
- A biologically meaningful baseline is required for intervention evaluation. Favorable/unfavorable labels are conditional on the selected goal. One pair cannot replace matched vehicle/time controls, biological replicates, group-level confidence intervals, or dedicated toxicity assays.
- Model artifacts are Python pickles and must not be loaded from untrusted sources.

The next scientifically necessary validation is prospective testing on independently generated neural organ-chip cohorts with raw voltage, prespecified QC criteria, multiple plates and laboratories, multiple compounds, replicate chips, and blinded labels. Until then, the system should be used as a transparent research assistant.

## 10. Reproducibility and artifact availability

The public repository includes a lightweight standardized event table, derived response summaries, external result tables, and both trained models so evaluators can start immediately. Full raw datasets are not duplicated. `scripts/download_data.py` retrieves the two core Zenodo resources and verifies checksums. `scripts/reproduce_all.py` executes the core pipeline. External GIN and Trujillo validations have separate checksummed resumable scripts because their raw files are large. Exact package versions are pinned.

Primary evidence is stored in CSV and JSON. Figures are exported as editable-text SVG, PDF, 600 dpi TIFF, and PNG. Single-recording reports are available as PDF and HTML. The report source, data/model cards, format specification, claim-evidence map, terminology ledger, video script, and checklist are versioned under `docs/`. No external API or commercial model is required at runtime.

### 10.1 Evaluator reproduction path

The fastest evaluation path is `python demo.py --demo-only`. This cross-platform entry point launches the same Streamlit application against the lightweight public bundle. A judge can select one record from each declared source, run the bundled diazepam or Trujillo matched pair, inspect the evidence hierarchy, and export a report without network access after dependencies are installed. Windows users can alternatively double-click `start_dashboard.cmd`.

The full core evidence path is `python scripts/reproduce_all.py --resume`. It verifies source downloads, extracts declared members, rebuilds features, reproduces publisher values, trains and evaluates both model artifacts, exports figures and public examples, builds reports, and runs the test suite. `--skip-download` uses existing files. GIN and Trujillo have separate resumable pipelines because the source archives are large; their checksummed metadata and derived outputs remain in the repository. The top-level README lists exact commands, supported Python versions, input schemas, expected data size, and scope boundaries.

Reproducibility is also checked at artifact level. Fixed seeds control randomized evaluation and explanations. Source and model hashes are recorded. Batch features use per-record checkpoints. ZIP extraction rejects unsafe paths. The submission audit checks headline metrics, report length, video constraints, public-link placeholders, archive integrity, credential patterns, and official competition declarations. Public repository, report, video, and optional application URLs still require the entrant's own accounts and must be tested in a logged-out browser.

### 10.2 Team, registration, and AI disclosure

The Kaggle Writeup declares **End-to-End System** at its beginning. The team must also complete the competition registration form before submission and ensure that each member belongs to only one team. Final member names, affiliations, and roles must replace the placeholders in the submission handoff. If the team truthfully includes both AI/computer-science and biology, bioengineering, or clinical expertise, that composition will be stated here and in the Writeup for the competition's cross-disciplinary bonus; no bonus will be claimed without real members covering both areas.

**Final team declaration status:** entrant names, affiliations, and roles are pending account-owner confirmation before final submission.  
**Cross-disciplinary bonus status:** not claimed in this draft; claim only after the real team composition is confirmed.

OpenAI Codex assisted code development, testing, and documentation. All statistics in this report were produced by checked-in local scripts from the declared public data. AI assistance did not supply experimental labels or replace the reproducibility checks.

## 11. Conclusion

NeuroChip Copilot provides an end-to-end event-level path from heterogeneous neural MEA files to standardized data, channel/stability evidence, classical and advanced descriptors, explainable anomaly prioritization, goal-aware multidimensional intervention evaluation, reports, and project history. Its strongest evidence is exact source reproduction, group-held-out anomaly AUROC 0.858, leave-one-organoid-out auxiliary response rho 0.904, and frozen external change-detection AUROCs 0.952 in 2D pharmacology and 0.889 in an independent cortical-organoid endpoint. The result is a credible research prototype whose raw-voltage, causal, clinical, efficacy, and toxicity boundaries remain explicit.

## References

1. 5th Pazhou Algorithm Competition Organizing Committee. *AI4S Open Innovation: AI for Life Science*. Kaggle competition overview and submission requirements, accessed 23 August 2026. https://www.kaggle.com/competitions/ai-4-s-open-innovation-artificial-intelligence-for-life-scien/overview
2. Itatani, N. *Spontaneous activity spike data and RNA-seq gene expression data from human forebrain organoids*. Zenodo (2026). https://doi.org/10.5281/zenodo.20286251
3. Sharf, T. *Extracellular Recordings from Human Brain Organoids Using High-density CMOS Arrays*. Zenodo (2022). https://doi.org/10.25349/D9031Z
4. Sharf, T. et al. Functional neuronal circuitry and oscillatory dynamics in human brain organoids. *Nature Communications* 13, 4403 (2022). https://doi.org/10.1038/s41467-022-32115-4. PMID: 35906223.
5. Kapucu, F. E., Vinogradov, A., Hyvärinen, T., Ylä-Outinen, L. & Narkilahti, S. Comparative microelectrode array dataset of functional development of human PSC-derived and rat neuronal networks. *Scientific Data* 9, 120 (2022). https://doi.org/10.1038/s41597-022-01242-4. PMID: 35354837. Data DOI: https://doi.org/10.12751/g-node.wvr3jf.
6. Trujillo, C. A. et al. Complex oscillatory waves emerging from cortical organoids model early human brain network development. *Cell Stem Cell* 25, 558-569.e7 (2019). https://doi.org/10.1016/j.stem.2019.08.002. PMID: 31474560. Data DOI: https://doi.org/10.5281/zenodo.4751759.
7. Cutts, C. S. & Eglen, S. J. Detecting pairwise correlations in spike trains: an objective comparison of methods and application to the study of retinal waves. *Journal of Neuroscience* 34, 14288-14303 (2014). https://doi.org/10.1523/JNEUROSCI.2767-14.2014. PMID: 25339742.
8. Beggs, J. M. & Plenz, D. Neuronal avalanches in neocortical circuits. *Journal of Neuroscience* 23, 11167-11177 (2003). https://doi.org/10.1523/JNEUROSCI.23-35-11167.2003. PMID: 14657176.
9. Liu, F. T., Ting, K. M. & Zhou, Z.-H. Isolation Forest. *2008 Eighth IEEE International Conference on Data Mining*, 413-422 (2008). https://doi.org/10.1109/ICDM.2008.17
