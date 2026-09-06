# NeuroChip Event Table 1.0

## Purpose

The NeuroChip event table is a vendor-neutral interchange format for detected extracellular spikes. It preserves recording, channel, timing, provenance, and optional amplitude information in a conventional CSV that can be inspected without proprietary software.

## Columns

| Column | Required | Type | Meaning |
|---|---|---|---|
| `recording_id` | Yes in canonical output | string | Stable identifier shared by all rows from one recording. |
| `timestamp_s` | Yes | float | Event time in seconds from recording start; must be finite and non-negative. |
| `channel_id` | Yes | string | Electrode, unit, or channel identifier. |
| `amplitude_uv` | No | float | Event amplitude in microvolts when the source scale is known. |
| `duration_s` | No | float | Protocol recording duration in seconds. |
| `well_id` | No | string | Plate-well identifier such as `A1`. |
| `source_vendor` | No | string | Source system, for example `Axion` or `unknown`. |
| `schema_version` | Yes in canonical output | string | Current value: `1.0`. |

Example:

```csv
recording_id,timestamp_s,channel_id,amplitude_uv,duration_s,well_id,source_vendor,schema_version
recording_001,0.102,11,35.2,180,A1,Axion,1.0
recording_001,0.151,12,42.0,180,A1,Axion,1.0
```

## Accepted aliases

The reader also accepts legacy names including `time_s`, `time`, `timestamp`, `channel`, `electrode`, `amplitude`, `well`, and Axion `Time`/`Channel`. A minimal legacy file therefore remains valid:

```csv
channel,time_s
A,0.102
B,0.151
```

## Axion conversion

```powershell
python scripts/convert_to_neurochip.py input_spikes.csv output_neurochip.csv --well A1 --resume
```

The converter processes large files in chunks, records the source SHA-256, writes progress after every completed chunk, truncates only uncommitted output bytes on resume, and emits `output_neurochip.csv.metadata.json` when complete. Omit `--well` to retain all wells in one standardized table.

## Scope boundary

This format stores detected events, not continuous voltage. It can support event-timing QC, activity, synchrony, connectivity descriptors, neuronal-avalanche analysis, and model input. It cannot by itself establish voltage noise, baseline drift, line interference, saturation, waveform quality, electrode impedance, or spike-sorting accuracy.

## Dashboard upload checks

The dashboard accepts `.csv`, `.mat`, `.h5`, and `.hdf5` files. Before analysis it checks that the file is readable, that the event table has usable time and channel values, and that the event count and channel count are non-zero. CSV uploads should use UTF-8 or UTF-8 with BOM and a comma delimiter. Invalid timestamps, negative timestamps, non-positive durations, empty files, and unrecognized MATLAB/HDF5 layouts are blocked with an explanatory message.

If `duration_s` is absent, the dashboard infers the duration from the latest event and marks this as a warning. If more than one `well_id` is present, the dashboard warns that a single-record upload will combine those wells; split wells first when they represent independent samples. A duration entered in the interface is an analysis override and should be in seconds.

For intervention evaluation, upload at least two event files from the same experimental object or matched well. The user must select which file is the baseline and which is the post-treatment record. The software reports a warning when the two files have different channel counts, but does not silently discard channels because a true biological change can also change the active-channel count.
