# Trujillo cortical organoid external validation

## Design

- Frozen NeuroChip v2 model; no retraining or threshold tuning on this dataset.
- Independent human cortical organoid MEA dataset: DOI 10.5281/zenodo.4751759.
- Primary endpoint: known CNQX+AP5/baclofen wells versus contemporaneous untreated control wells.
- Bicuculline is reported separately because the source paper describes little change in spike/burst counts.
- The 170303 well identities are not public in the located source code, so they remain unlabeled and exploratory.

## Primary result

- AUC: 0.889 (95% bootstrap CI 0.667-1.000)
- Active wells: 6; control wells: 6
- Frozen p95 sensitivity: 1.000
- Frozen p95 specificity: 0.833
- Mann-Whitney p: 0.02597

## Natural-drift check

- Matched active wells: 6
- Active median response: 11.947
- Same-well baseline drift median: 0.330
- Fraction active response above its own drift: 1.000
- One-sided paired Wilcoxon p: 0.01562

## Interpretation boundary

This test supports or challenges transfer to one additional cortical-organoid protocol. It does not by itself prove universal applicability to every organoid type, laboratory, MEA platform, maturation stage, or drug. The original diazepam dose estimate is not interpreted for these external compounds.
