# Demo data attribution

`fs363-org0_events.csv` is a lightweight event-table export of `fs363-org0.mat` from:

Itatani, N. (2026). *Spontaneous activity spike data and RNA-seq gene expression data from human forebrain organoids*. Zenodo. https://doi.org/10.5281/zenodo.20286251

The source record is licensed under CC BY 4.0. The exported table contains detected spike times, channel identifiers, and the declared recording duration. It contains no personal, clinical, or identifying information.

Files under `drug_response/` are derived result tables from the CC0 dataset:

Sharf, T. (2022). *Extracellular Recordings from Human Brain Organoids Using High-density CMOS Arrays*. Zenodo. https://doi.org/10.25349/D9031Z

`public_samples/` contains at least one lightweight NeuroChip event-table example from each public source used by the application, plus matched diazepam-organoid and Trujillo cortical-organoid baseline-treatment pairs for the intervention Demo:

- forebrain organoid reference data, DOI `10.5281/zenodo.20286251`, CC BY 4.0;
- brain-organoid diazepam data, DOI `10.25349/D9031Z`, CC0 1.0;
- comparative human/rat 2D neuronal MEA data, DOI `10.12751/g-node.wvr3jf`, CC BY 4.0;
- Trujillo cortical-organoid MEA data, DOI `10.5281/zenodo.4751759`, CC BY 4.0.

The exports contain detected spike events and experimental labels, with no personal, clinical, or identifying information. They are included only to keep all four public sources and two paired workflows runnable without distributing the multi-gigabyte originals. Full checksummed source-data reproduction is handled by the dataset-specific download and reproduction scripts.
