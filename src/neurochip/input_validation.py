"""Preflight validation for user-supplied event recordings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .io import read_recording
from .standard import infer_event_columns


SUPPORTED_SUFFIXES = {".csv", ".mat", ".h5", ".hdf5"}
CSV_CHUNK_SIZE = 250_000


@dataclass(frozen=True)
class InputValidationResult:
    valid: bool
    format_name: str
    summary: dict[str, Any]
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def _csv_preflight(path: Path, duration_override_s: float | None) -> InputValidationResult:
    try:
        header = pd.read_csv(path, nrows=0, encoding="utf-8-sig")
        mapping = infer_event_columns(list(header.columns))
    except UnicodeDecodeError:
        return InputValidationResult(False, "CSV", {}, errors=("CSV 不是 UTF-8 编码；请另存为 UTF-8 或 UTF-8 with BOM。",))
    except (pd.errors.ParserError, ValueError) as error:
        return InputValidationResult(False, "CSV", {}, errors=(f"无法识别 CSV 表头：{error}",))
    except Exception as error:
        return InputValidationResult(False, "CSV", {}, errors=(f"无法读取 CSV：{error}",))

    source_columns = list(dict.fromkeys(mapping.values()))
    row_count = 0
    valid_event_count = 0
    invalid_time_count = 0
    negative_time_count = 0
    empty_channel_count = 0
    max_timestamp = 0.0
    channels: set[str] = set()
    wells: set[str] = set()
    declared_durations: list[float] = []
    try:
        chunks = pd.read_csv(
            path,
            usecols=source_columns,
            chunksize=CSV_CHUNK_SIZE,
            encoding="utf-8-sig",
        )
        for chunk in chunks:
            row_count += len(chunk)
            normalized = chunk.rename(columns={source: target for target, source in mapping.items()})
            times = pd.to_numeric(normalized["timestamp_s"], errors="coerce")
            channels_series = normalized["channel_id"].astype("string").str.strip()
            invalid_time = times.isna()
            negative_time = times.lt(0).fillna(False)
            empty_channel = channels_series.isna() | channels_series.eq("")
            invalid_time_count += int(invalid_time.sum())
            negative_time_count += int(negative_time.sum())
            empty_channel_count += int(empty_channel.sum())
            valid = ~(invalid_time | negative_time | empty_channel)
            valid_event_count += int(valid.sum())
            if valid.any():
                max_timestamp = max(max_timestamp, float(times[valid].max()))
                channels.update(channels_series[valid].astype(str).unique().tolist())
            if "well_id" in normalized:
                wells.update(
                    normalized.loc[valid, "well_id"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist()
                )
            if "duration_s" in normalized:
                durations = pd.to_numeric(normalized["duration_s"], errors="coerce")
                declared_durations.extend(durations.dropna().astype(float).tolist())
    except UnicodeDecodeError:
        return InputValidationResult(False, "CSV", {}, errors=("CSV 不是 UTF-8 编码；请另存为 UTF-8 或 UTF-8 with BOM。",))
    except (pd.errors.ParserError, ValueError) as error:
        return InputValidationResult(False, "CSV", {}, errors=(f"CSV 内容无法解析：{error}",))
    except Exception as error:
        return InputValidationResult(False, "CSV", {}, errors=(f"读取 CSV 数据失败：{error}",))

    errors: list[str] = []
    warnings: list[str] = []
    if valid_event_count == 0:
        errors.append("文件中没有可分析的有效事件；请检查时间和通道列。")
    if invalid_time_count:
        errors.append(f"有 {invalid_time_count} 行时间不是有效数字。")
    if negative_time_count:
        errors.append(f"有 {negative_time_count} 行时间为负数。")
    if empty_channel_count:
        warnings.append(f"有 {empty_channel_count} 行缺少通道编号，这些行将被忽略。")
    if max_timestamp > 10_000:
        warnings.append("最大事件时间超过 10,000 秒；请确认时间单位确实是秒，而不是毫秒或采样点。")
    if declared_durations:
        if any(value <= 0 for value in declared_durations):
            errors.append("duration_s 必须是正数。")
        if max(declared_durations) - min(declared_durations) > 1e-9:
            warnings.append("同一文件中存在多个记录时长，系统将使用第一条有效时长。")
        declared_duration = float(declared_durations[0])
    else:
        declared_duration = None
        if duration_override_s is None:
            warnings.append("文件未提供记录时长；系统将根据最大事件时间推断时长。")
    if duration_override_s is not None:
        if duration_override_s <= 0:
            errors.append("指定记录时长必须大于 0 秒。")
        elif max_timestamp > duration_override_s:
            warnings.append("有事件时间超过指定记录时长；请确认时长单位和截取范围。")
    if len(wells) > 1:
        warnings.append("检测到多个孔位；单记录上传会将它们作为一个记录分析，建议先按孔位拆分。")

    summary = {
        "rows": row_count,
        "events": valid_event_count,
        "channels": len(channels),
        "wells": len(wells),
        "max_timestamp_s": max_timestamp,
        "declared_duration_s": declared_duration,
    }
    return InputValidationResult(not errors, "CSV", summary, tuple(errors), tuple(warnings))


def validate_input_file(path: str | Path, duration_override_s: float | None = None) -> InputValidationResult:
    """Validate an upload before it enters the analysis pipeline."""

    source = Path(path)
    if source.suffix.lower() not in SUPPORTED_SUFFIXES:
        return InputValidationResult(False, "未知格式", {}, errors=(f"不支持的文件格式：{source.suffix or '无扩展名'}。",))
    if not source.exists() or source.stat().st_size == 0:
        return InputValidationResult(False, source.suffix.upper().lstrip("."), {}, errors=("文件不存在或为空。",))
    if source.suffix.lower() == ".csv":
        return _csv_preflight(source, duration_override_s)
    try:
        recording = read_recording(source, duration_s=duration_override_s)
    except (OSError, ValueError, KeyError, TypeError) as error:
        return InputValidationResult(
            False,
            source.suffix.upper().lstrip("."),
            {},
            errors=(f"无法识别此 {source.suffix.upper().lstrip('.')} 文件结构：{error}",),
        )
    warnings: list[str] = []
    if duration_override_s is None and recording.metadata.get("duration_inferred"):
        warnings.append("文件未提供明确记录时长；系统使用事件时间推断时长。")
    summary = {
        "events": recording.n_spikes,
        "channels": recording.n_channels,
        "wells": 1,
        "duration_s": float(recording.duration_s),
    }
    return InputValidationResult(True, source.suffix.upper().lstrip("."), summary, warnings=tuple(warnings))
