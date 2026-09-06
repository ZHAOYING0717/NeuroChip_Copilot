# Data Card

## Scope

NeuroChip Copilot uses two public brain-organoid electrophysiology resources for model development, one public 2D neuronal-network MEA resource for frozen external stress testing, and one independent cortical-organoid resource for external protocol transfer. The analyzed inputs are detected extracellular spike events rather than participant-level clinical records. The repository contains six attributed lightweight event exports: at least one record from each source plus matched diazepam-organoid and Trujillo cortical-organoid baseline-treatment pairs. Small derived result tables are also included for immediate Demo use; full source recordings are not redistributed.

## Dataset A: reference phenotype cohort

- **Title:** Spontaneous activity spike data and RNA-seq gene expression data from human forebrain organoids
- **Creator:** Naoya Itatani, ORCID 0000-0003-3662-3499
- **DOI:** https://doi.org/10.5281/zenodo.20286251
- **License:** CC BY 4.0
- **Files used:** 45 individual MATLAB v7.3 spike-event recordings, publisher source-data spreadsheet, and analysis scripts
- **Representation:** Eight channels per recording, detected spike times, amplitudes, declared duration, and source metadata
- **Use:** Publisher-value reproduction, reference phenotype fitting, and controlled event-perturbation evaluation
- **Excluded material:** RNA sequencing data and population-level MATLAB data not required by the final pipeline

### Known limitations

- The 45-recording cohort originates from one public resource and may not represent other laboratories, devices, chip geometries, cultures, or protocols.
- Per-recording age labels were not inferred because a verified mapping was not available in the individual files used here.
- Amplitude is retained for descriptive output but excluded from phenotype-model input because scale can be device dependent.

## Dataset B: diazepam response cohort

- **Title:** Extracellular Recordings from Human Brain Organoids Using High-density CMOS Arrays
- **Creator:** Tal Sharf, ORCID 0000-0002-7899-2818
- **DOI:** https://doi.org/10.25349/D9031Z
- **License:** CC0 1.0
- **Associated paper:** Sharf et al., *Nature Communications* 13, 4403 (2022), DOI 10.1038/s41467-022-32115-4, PMID 35906223
- **Files used:** 19 unique Kilosort2 MATLAB recordings from four organoids
- **Conditions:** Four controls; four each at 3, 10, and 50 uM diazepam; three at 30 uM
- **Protocol duration:** 180 s per recording, as stated in the associated paper
- **Use:** Matched-control response modeling and leave-one-organoid-out validation

### Boundary handling

Six files contain small event tails at or beyond 180 s. The original events remain available to QC, but features use only `0 <= time < 180`. Forty-seven events are excluded in total. The largest affected file fraction is 0.702%; the remaining affected fractions are below 0.1%.

### Known limitations

- Four organoids and one compound are insufficient for broad compound generalization.
- One dose is missing for one organoid.
- Kilosort2 unit events do not permit independent raw-voltage or spike-sorting validation in this project.

## Dataset C: frozen external pharmacology stress test

- **Title:** Comparative microelectrode array dataset of functional development of human pluripotent stem cell-derived and rat neuronal networks
- **Creators:** Fikret Emre Kapucu, Andrey Vinogradov, Tanja Hyvärinen, Laura Ylä-Outinen, and Susanna Narkilahti
- **Data DOI:** https://doi.org/10.12751/g-node.wvr3jf
- **License:** CC BY 4.0
- **Associated data paper:** Kapucu et al., *Scientific Data* 9, 120 (2022), DOI 10.1038/s41597-022-01242-4, PMID 35354837
- **Files used:** detected-spike CSV tables, experiment logs, and noisy-electrode declarations for one human iPSC-derived cortical-neuron plate and one rat embryonic cortical-neuron plate
- **Stages:** baseline, pharmacology, and TTX
- **Primary analysis window:** first 180 s; 600 s is a prespecified duration sensitivity analysis
- **Use:** external evaluation of the already frozen v2 response magnitude, never model fitting or dose calibration

### Pair definitions

Each plate well is matched across stages. The pharmacology comparison contains 66 well pairs: 55 active treatments and 11 negative controls. The TTX comparison contains 66 well pairs: 26 TTX and 40 non-TTX controls. Human and rat domains are reported separately and pooled. The same wells contribute to both stage comparisons, so the two 66-pair analyses are not 132 independent biological preparations.

### Known limitations

- These are 2D neuronal cultures, not brain organoids or organ-on-chip devices.
- The evaluation tests whether an unsigned paired response is larger under active perturbation; it does not infer compound identity, mechanism, efficacy, toxicity, or a diazepam-equivalent dose.
- Well-level observations share plates and experimental context; the reported stratified bootstrap resamples class observations but is not a multi-plate prospective validation.

## Dataset D: independent cortical-organoid pharmacology stress test

- **Title:** Complex Oscillatory Waves Emerging from Cortical Organoids Model Early Human Brain Network Development
- **Creators:** Cleber A. Trujillo et al.
- **Data DOI:** https://doi.org/10.5281/zenodo.4751759
- **License:** CC BY 4.0
- **Associated paper:** Trujillo et al., *Cell Stem Cell* 25, 558-569.e7 (2019), DOI 10.1016/j.stem.2019.08.002, PMID 31474560
- **Files used:** six large MATLAB baseline/pharmacology files; two labeled dates define the primary endpoint and one additional date remains unlabeled
- **Primary analysis window:** first 120 s; 90 s is a duration sensitivity analysis
- **Use:** frozen-model evaluation only, never fitting or external dose calibration

### Pair definitions and limitations

The primary endpoint compares six known spike/burst-suppressing treatment pairs with six contemporaneous untreated-control pairs. A second baseline window in each active well estimates natural drift. This small retrospective endpoint contains strongly suppressive interventions and supports external change detection only. It does not establish compound identity, mechanism, efficacy, toxicity, safety, or a transferable diazepam-equivalent dose.

## Processing

1. Verify source byte size and MD5 from `data/manifests/datasets.json` or `data/manifests/external_validation.json`.
2. Reject unsafe ZIP paths and extract only declared members.
3. Convert events to seconds and sort finite timestamps.
4. Preserve protocol duration and all original events for audit.
5. Derive a valid event window for functional features.
6. Save per-recording JSON checkpoints and combined CSV tables.
7. Preserve biological source groups for all validation splits and freeze the response model before external evaluation.

## Privacy, ethics, and prohibited use

No personal identifiers, protected health information, or clinical labels are present. The data must not be used to infer individual health status. Project outputs must not be represented as clinical diagnosis, drug efficacy, toxicity, or safety decisions.

## Demo derivatives

`data/demo/fs363-org0_events.csv` is a NeuroChip 1.0 event-table derivative of the CC BY 4.0 reference dataset and retains its attribution requirement. `data/demo/public_samples/` contains six event-table derivatives from the four declared public sources, including the two matched pairs used by the intervention Demo; source licenses are documented in `data/demo/README.md` and the machine-readable source manifests. Files under `data/demo/drug_response/` are derived summaries of the CC0 resource. External GIN and Trujillo result tables under `artifacts/results/external_validation/` retain CC BY attribution. Their purpose is immediate public review; full recomputation requires the checksummed source files.
