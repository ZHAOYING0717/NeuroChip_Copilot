# Terminology Ledger

| Canonical term | First-use definition | Avoided variants | Decision |
|---|---|---|---|
| NeuroChip Copilot | The complete event-level analysis and dashboard system | Neuro Chip, NeuroChip AI | Use the product name exactly. |
| End-to-End System | Competition category covering the detected-event path from ingestion through QC, models, intervention evaluation, reports, and projects | full laboratory automation, raw-to-result system | Always state that the scope begins with detected MEA spike events, not cell culture or raw voltage. |
| evidence hierarchy | Five validation levels: source reproduction, grouped controlled testing, held-out real-organoid association, frozen 2D transfer, and frozen independent-organoid transfer | universal validation, five datasets prove generalization | Each level has a different supported and unsupported conclusion. |
| spike event | A detected extracellular action-potential timestamp | spike signal, raw spike | Use `spike event` when raw voltage is unavailable. |
| event-level quality control | Quality audit derived from event timestamps | preprocessing, signal QC | Never call it complete raw-signal preprocessing. |
| event channel status | Event-derived label: `good`, `inactive_candidate`, `review_event_proxy`, or `excluded_event_invalid` | dead channel, noisy channel | Event timestamps can flag review candidates but cannot prove hardware failure or voltage noise. |
| raw-voltage quality control | Optional audit of continuous voltage for noise, drift, line interference, saturation, and near-dead activity | event QC | Use only when a real voltage matrix and sampling rate are supplied. |
| microelectrode array (MEA) | Multichannel extracellular recording platform | electrode chip | Define MEA once, then use MEA. |
| inter-spike interval (ISI) | Time between adjacent events in one channel or unit | interspike gap | Define ISI once, then use ISI. |
| spike time tiling coefficient (STTC) | Firing-rate-aware pairwise spike-train association | STCC, spike correlation | Use STTC and a 20 ms window throughout. |
| functional-state axis percentile | Reference-percentile position on the oriented first PCA component; internal field `functional_phenotype_index` | maturity score, health score | Do not imply age, health, or clinical function. |
| reference-deviation percentile | Reference-relative extremeness from Isolation Forest; internal field `anomaly_percentile` | abnormality probability | It is a percentile, not a calibrated disease, efficacy, toxicity, or safety probability. |
| reference-deviation Shapley contribution | Deterministic Monte Carlo single-reference Shapley attribution of the Isolation Forest score | exact SHAP value, causal importance | Report the approximation method and seed; it explains this model output only. |
| controlled event perturbation | Synthetic change applied to timestamps for sensitivity testing | synthetic disease, toxic event | Keep the event-level scope visible. |
| multidimensional intervention impact | Root-mean-square robust-standardized change across 18 validated functional features | treatment success score, efficacy score | Reports how much function changed; direction and value require a declared goal. |
| goal alignment | Agreement between signed feature changes and the user-selected experimental objective | efficacy probability | Conditional decision support, not a biological truth label. Quantify-only mode has no alignment score. |
| public functional reference | Robust center of the 45-recording training distribution | healthy standard, normal brain | A statistical cohort center, not a clinical or certified healthy reference. |
| network-silencing risk | Joint collapse of firing rate and active-channel fraction after treatment | toxicity diagnosis | A review warning that can override desirable suppression; confirm with viability/toxicity assays. |
| reversibility | Fraction of treatment displacement that returns toward baseline in an optional recovery record | recovery proof | Descriptive single-pair measure requiring repeats and time controls. |
| matched-control response magnitude | Root-mean-square standardized paired change in two ISI features | drug efficacy score, toxicity score | Use as an auxiliary change-detection endpoint, not the main intervention verdict. |
| paired component contribution | Exact squared standardized feature contribution to response magnitude | feature importance | Contributions sum to one for a non-zero paired response and describe score composition. |
| exploratory dose estimate | Isotonic mapping from response magnitude to dose | predicted dose | Always include `exploratory`. |
| neuronal avalanche descriptor | Event-bin cascade size, duration, and branching summaries | proof of criticality | Treat these as descriptive proxies; finite event data do not establish a critical phase transition. |
| predictive Granger direction | Lag-1 out-of-sample predictive direction score | Granger causality, causal connectivity | Never claim biological causality from this descriptor. |
| transfer entropy | Directed lagged information statistic between binned channel activity | causal information flow | Describe as directed statistical dependence, not causal influence. |
| NeuroChip 1.0 event format | Device-neutral CSV with `timestamp_s`, `channel_id`, and optional `amplitude` | universal raw format | It standardizes detected events, not proprietary raw-voltage containers. |
| frozen external stress test | Evaluation of an unchanged model on human and rat 2D neuronal-network pharmacology data | independent organoid validation | State the 2D-culture domain shift and do not relabel it as organoid evidence. |
| source group | `fs_id` used to isolate related reference recordings | subject, patient | These are organoid source groups, not people. |
| organoid group | Organoid identifier used for leave-one-group-out drug validation | subject ID | Use `organoid`, never `patient`. |
| high dose | Diazepam concentration at least 30 uM in this evaluation | therapeutic dose | Definition is benchmark specific, not clinical. |
