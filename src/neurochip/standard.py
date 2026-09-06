from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .schema import SpikeRecording


NEUROCHIP_SCHEMA_VERSION = "1.0"
REQUIRED_COLUMNS = ("recording_id", "timestamp_s", "channel_id")
OPTIONAL_COLUMNS = ("amplitude_uv", "duration_s", "well_id", "source_vendor", "schema_version")


def _normalized_column(name: str) -> str:
    return "".join(character for character in name.casefold() if character.isalnum())


def infer_event_columns(columns: list[str]) -> dict[str, str]:
    normalized = {_normalized_column(column): column for column in columns}

    def find(*aliases: str) -> str | None:
        for alias in aliases:
            if _normalized_column(alias) in normalized:
                return normalized[_normalized_column(alias)]
        return None

    mapping = {
        "timestamp_s": find("timestamp_s", "time_s", "time", "time (s)", "timestamp"),
        "channel_id": find("channel_id", "channel", "electrode", "electrode_id"),
        "amplitude_uv": find("amplitude_uv", "amplitude", "amplitude (uv)", "amplitude (uV)"),
        "duration_s": find("duration_s", "recording_duration", "recording duration (s)"),
        "recording_id": find("recording_id", "recording", "file_id"),
        "well_id": find("well_id", "well"),
    }
    missing = [name for name in ("timestamp_s", "channel_id") if mapping[name] is None]
    if missing:
        raise ValueError(f"Could not identify required event columns: {', '.join(missing)}")
    return {target: source for target, source in mapping.items() if source is not None}


def standardize_event_table(
    table: pd.DataFrame,
    recording_id: str,
    source_vendor: str = "unknown",
    well: str | None = None,
) -> pd.DataFrame:
    mapping = infer_event_columns(list(table.columns))
    renamed = table.rename(columns={source: target for target, source in mapping.items()}).copy()
    renamed["timestamp_s"] = pd.to_numeric(renamed["timestamp_s"], errors="coerce")
    renamed = renamed.dropna(subset=["timestamp_s", "channel_id"])
    renamed = renamed.loc[renamed["timestamp_s"] >= 0].copy()
    raw_channel = renamed["channel_id"].astype(str).str.strip()
    inferred_well = raw_channel.str.extract(r"^([A-Za-z]+\d+)[_\-]", expand=False)
    if "well_id" not in renamed:
        renamed["well_id"] = inferred_well
    else:
        renamed["well_id"] = renamed["well_id"].fillna(inferred_well).astype(str)
    if well is not None:
        renamed = renamed.loc[renamed["well_id"].astype(str).str.casefold() == well.casefold()].copy()
        raw_channel = renamed["channel_id"].astype(str).str.strip()
        renamed["channel_id"] = raw_channel.str.replace(r"^[A-Za-z]+\d+[_\-]", "", regex=True)
    else:
        renamed["channel_id"] = raw_channel
    if "amplitude_uv" in renamed:
        renamed["amplitude_uv"] = pd.to_numeric(renamed["amplitude_uv"], errors="coerce")
    else:
        renamed["amplitude_uv"] = np.nan
    if "duration_s" in renamed:
        renamed["duration_s"] = pd.to_numeric(renamed["duration_s"], errors="coerce")
    else:
        renamed["duration_s"] = np.nan
    if "recording_id" not in renamed:
        renamed["recording_id"] = recording_id
    else:
        renamed["recording_id"] = renamed["recording_id"].fillna(recording_id).astype(str)
    renamed["source_vendor"] = source_vendor
    renamed["schema_version"] = NEUROCHIP_SCHEMA_VERSION
    return renamed.loc[:, [*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS]]


def recording_to_event_table(recording: SpikeRecording, source_vendor: str = "unknown") -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for index, (channel_id, times) in enumerate(zip(recording.channel_ids, recording.spike_times, strict=True)):
        data: dict[str, Any] = {
            "recording_id": recording.recording_id,
            "timestamp_s": times,
            "channel_id": channel_id,
            "duration_s": recording.duration_s,
            "well_id": recording.metadata.get("well_id"),
            "source_vendor": source_vendor,
            "schema_version": NEUROCHIP_SCHEMA_VERSION,
        }
        if recording.amplitudes is not None and recording.amplitudes[index].size == times.size:
            data["amplitude_uv"] = recording.amplitudes[index]
        else:
            data["amplitude_uv"] = np.full(times.size, np.nan)
        rows.append(pd.DataFrame(data))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=[*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS])


def file_sha256(path: Path, block_size: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def convert_axion_csv(
    source: str | Path,
    output: str | Path,
    well: str | None = None,
    chunksize: int = 500_000,
    resume: bool = False,
) -> dict[str, Any]:
    source_path = Path(source)
    output_path = Path(output)
    checkpoint_path = output_path.with_suffix(output_path.suffix + ".checkpoint.json")
    sidecar_path = output_path.with_suffix(output_path.suffix + ".metadata.json")
    if output_path.exists() and not resume:
        raise FileExistsError(f"Output already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source_hash = file_sha256(source_path)
    checkpoint: dict[str, Any] = {}
    if resume and checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if checkpoint.get("source_sha256") != source_hash:
            raise ValueError("Source file changed since the conversion checkpoint was created")
        if checkpoint.get("complete"):
            return json.loads(sidecar_path.read_text(encoding="utf-8"))
        completed_chunks = int(checkpoint.get("completed_chunks", 0))
        committed_size = int(checkpoint.get("output_bytes", 0))
        if output_path.exists() and output_path.stat().st_size > committed_size:
            with output_path.open("r+b") as handle:
                handle.truncate(committed_size)
    else:
        completed_chunks = 0
    column_mapping = infer_event_columns(list(pd.read_csv(source_path, nrows=0).columns))
    total_rows = int(checkpoint.get("output_rows", 0))
    recording_id = source_path.stem if well is None else f"{source_path.stem}__{well}"
    for chunk_index, chunk in enumerate(pd.read_csv(source_path, chunksize=chunksize)):
        if chunk_index < completed_chunks:
            continue
        standardized = standardize_event_table(chunk, recording_id, source_vendor="Axion", well=well)
        standardized.to_csv(
            output_path,
            mode="a" if output_path.exists() and output_path.stat().st_size else "w",
            header=not output_path.exists() or output_path.stat().st_size == 0,
            index=False,
        )
        total_rows += len(standardized)
        checkpoint = {
            "source_path": str(source_path.resolve()),
            "source_sha256": source_hash,
            "output_path": str(output_path.resolve()),
            "completed_chunks": chunk_index + 1,
            "output_rows": total_rows,
            "output_bytes": output_path.stat().st_size,
            "complete": False,
        }
        checkpoint_path.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")
        print(f"[chunk {chunk_index + 1}] {total_rows:,} standardized rows", flush=True)
    metadata = {
        **checkpoint,
        "complete": True,
        "schema_name": "NeuroChip event table",
        "schema_version": NEUROCHIP_SCHEMA_VERSION,
        "source_vendor": "Axion",
        "well_filter": well,
        "column_mapping": column_mapping,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    checkpoint_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    sidecar_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata
