# Model Card

## Overview

NeuroChip Copilot contains two fitted research models and one deterministic evaluator:

1. A reference-cohort functional phenotype and anomaly model.
2. A goal-aware multidimensional intervention evaluator built on the frozen phenotype scaler.
3. An auxiliary matched-control diazepam response model with exploratory dose calibration.

Version: `0.4.0`  
Released: 23 August 2026  
Runtime: Python 3.11-3.14  

## Phenotype and anomaly model

### Intended use

- Describe a spike-event recording relative to a documented public brain-organoid reference.
- Prioritize unusual event-level functional patterns for expert review.
- Support method development and research quality review.

### Architecture

- Median imputation
- Robust scaling with 10th-90th percentile range
- PCA with up to five components
- Isolation Forest with 500 trees
- Reference-percentile output for phenotype and anomaly evidence

### Features

Eighteen normalized measures spanning firing-rate distribution, active and dominant channels, ISI timing, STTC, graph topology, population entropy, and network bursts.

The model excludes duration, channel count, raw spike count, amplitude scale, sampling rate, out-of-range count, and event-quality score. These exclusions reduce acquisition-protocol and QC leakage.

The feature pipeline additionally reports stability, neuronal-avalanche, mutual-information, transfer-entropy, and predictive Granger descriptors. They are not inputs to the primary model: an exploratory 30-feature version reduced grouped-CV AUROC from 0.858 to 0.839, so version 2 retains the validated 18-feature set.

### Validation

- 45 clean reference recordings from 16 source groups
- 135 controlled event-level perturbations
- Five-fold GroupKFold by source `fs_id`
- Cluster bootstrap by source recording, 2,000 iterations

### Performance

- AUROC: 0.858
- Cluster-bootstrap 95% CI: 0.796-0.915
- Average precision: 0.927
- Channel-dropout AUROC: 0.756
- Hyperactivity AUROC: 0.903
- Hypersynchrony AUROC: 0.914
- Fold AUROC range: 0.784-0.905
- Balanced accuracy: 0.719 at the 90th percentile, 0.567 at the 95th percentile, and 0.519 at the 97.5th percentile

### Interpretation

The user-facing reference-deviation percentile states how extreme a multivariate feature pattern is relative to this reference cohort; its internal output field remains `anomaly_percentile`. It does not identify a disease, mechanism, toxicity, or data-invalidity cause. The functional-state axis percentile is the oriented first-PCA-axis position, not a health or maturity score. A deterministic 64-permutation Monte Carlo single-reference Shapley estimate decomposes the deviation-score difference from the robust training median. Contributions explain this model and reference point; they are not biological causal effects.

## Multidimensional intervention evaluator

### Intended use

- Compare a treatment record with a user-selected baseline across 18 validated functional features and five domains.
- Separate change magnitude from goal-dependent direction.
- Report reference distance, network-silencing risk, optional reversibility, and evidence limits.

### Architecture and interpretation

The evaluator uses the phenotype model's median imputer and robust scaler but fits no new classifier. Overall impact is the root mean square of the 18 standardized feature changes. Goal alignment is computed only for an explicit directional goal; quantify-only mode has no alignment score. Reference distance uses a supplied matched reference or the public training center, which is not a clinical healthy standard. A combined collapse of firing rate and active channels triggers a silencing warning. A recovery record, when present, is compared with the baseline in the same space. Event-quality failure blocks good/bad interpretation, and a single pair is never assigned more than moderate evidence.

Advanced stability, avalanche, and information-flow descriptors are reported separately and excluded from the verdict. Favorable/unfavorable labels are conditional on the selected goal and do not establish efficacy, toxicity, or safety.

## Auxiliary matched-control drug-response model

### Intended use

- Quantify how strongly a treatment recording differs from a matched zero-dose control from the same organoid or preparation.
- Support exploratory dose-response visualization and assay review.

### Architecture

- Signed `log1p` treatment-minus-control components
- Training interquartile-range scaling with standard-deviation fallback
- Root-mean-square standardized response magnitude
- Isotonic regression for an explicitly exploratory dose display

### Features

- Mean ISI coefficient of variation
- Median ISI

Version 1 also included mean network-burst duration. Version 2 uses the simpler spike-timing pair because it improved leave-one-organoid-out dose association, high-dose discrimination, and both independent frozen-model stress tests. Response magnitude is unsigned and is an auxiliary change-detection endpoint. Exact squared-component fractions explain how much each feature contributes to a paired score.

### Validation

- 19 conditions from four organoids
- LeaveOneGroupOut by organoid
- Test treatments paired only with the held-out organoid's control
- Cluster bootstrap by organoid, 3,000 iterations
- Treated-dose permutation within organoid, 5,000 iterations

### Performance

- Dose-response Spearman rho: 0.904
- Cluster-bootstrap 95% CI: 0.641-0.991
- Treated-only rho: 0.803
- Blocked permutation p-value: 0.0020
- High-dose AUROC, at least 30 uM: 0.964
- High-dose 95% CI: 0.850-1.000
- Exploratory dose MAE: 7.16 uM
- Exploratory dose RMSE: 12.68 uM
- Exploratory dose R-squared: 0.562

### Frozen external stress tests

The saved v2 model was not retrained on the external GIN data. At a primary 180 s window, 66 matched wells from human iPSC-derived and rat 2D neuronal networks were assessed in each comparison:

- Active pharmacology versus negative controls: pooled AUROC 0.952, stratified-bootstrap 95% CI 0.881-0.997.
- TTX versus non-TTX wells: pooled AUROC 0.950, stratified-bootstrap 95% CI 0.865-1.000.
- Human 2D AUROCs: 1.000 and 1.000; rat 2D AUROCs: 0.931 and 0.903.
- A 600 s sensitivity analysis retained pooled AUROCs of 0.934 and 0.922.

This is a transfer test for unsigned response magnitude. The external cultures are not organoids, and their compounds are not interpreted through the diazepam dose calibrator.

The frozen model was also evaluated on an independent cortical-organoid MEA protocol. Six known suppressive treatment pairs were separated from six contemporaneous untreated-control pairs with AUROC 0.889 (95% CI 0.667-1.000). All six active responses exceeded the same well's natural drift (one-sided paired Wilcoxon p=0.0156). The small endpoint supports external change detection, not universal efficacy, toxicity, or dose calibration.

### Interpretation

The model requires a matched baseline from the same preparation. Its response magnitude is suitable as auxiliary comparative evidence when the paired event-quality gate is reviewed. It does not determine whether a change is beneficial or harmful. The dose estimate is too cohort specific for operational dosing decisions.

## Limitations and risks

- Inputs are detected events, not raw voltages or waveforms.
- The training cohorts are small; external tests add two 2D culture domains and one small retrospective organoid endpoint, but no prospective multi-site cohort.
- Synthetic anomaly labels cannot validate disease, toxicity, or clinical performance.
- The response model is trained on one compound and has no blinded prospective dose cohort.
- Mutual information, transfer entropy, and predictive Granger descriptors are statistical associations, not proof of synaptic causality.
- Percentiles can shift under domain change.
- Joblib artifacts are Python pickles and can execute code when loaded. Do not load untrusted files.

## Human oversight

Every score must be reviewed with channel status, recording stability, the pair quality gate, the selected experimental goal, feature evidence, experimental design, matched time/vehicle controls, and biological repeats. Event-only inputs cannot distinguish an inactive channel from a dead electrode. Researchers remain responsible for biological interpretation and decisions.

## Retraining requirements

Before deployment in a new laboratory or device, collect local reference and matched-control data, preserve biological grouping during validation, predefine endpoints and thresholds, and test raw-voltage quality separately when available.
