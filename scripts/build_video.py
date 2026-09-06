"""Build the narrated, captioned competition demo video."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg

from make_video_slides import make_slides


ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "output" / "video"
NARRATION_DIR = VIDEO_DIR / "narration"
SLIDE_DIR = VIDEO_DIR / "slides"
SCREEN_DIR = VIDEO_DIR / "screen"
SEGMENT_DIR = VIDEO_DIR / "segments"
FINAL_VIDEO = VIDEO_DIR / "NeuroChip_Copilot_Demo_zh.mp4"
CLEAN_VIDEO = VIDEO_DIR / "NeuroChip_Copilot_Demo_zh_clean.mp4"
SUBTITLES = VIDEO_DIR / "NeuroChip_Copilot_Demo_zh.srt"
METADATA = VIDEO_DIR / "video_metadata.json"

NARRATION = json.loads((ROOT / "scripts" / "video_narration_zh.json").read_text(encoding="utf-8"))

ORDER = [
    "01_intro",
    "04_single",
    "06_drug",
    "02_results",
    "05_model",
    "03_data",
    "07_reproduce",
    "08_close",
]
STATIC = {"01_intro", "02_results", "03_data", "05_model", "07_reproduce", "08_close"}


def run(command: list[str]) -> None:
    printable = " ".join(command[:5])
    print(f"Running: {printable} ...", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / handle.getframerate()


def timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    whole_seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def caption_chunks(text: str, limit: int = 26) -> list[str]:
    sentences = [part.strip() for part in re.split(r"(?<=[。！？；])", text) if part.strip()]
    chunks: list[str] = []
    for sentence in sentences:
        clauses = [part for part in re.split(r"(?<=[，、：])", sentence) if part]
        current = ""
        for clause in clauses:
            if current and len(current) + len(clause) > limit:
                chunks.append(current)
                current = clause
            else:
                current += clause
        if current:
            chunks.append(current)
    return chunks


def build_subtitles(durations: dict[str, float]) -> None:
    cues: list[str] = []
    cue_number = 1
    segment_start = 0.0
    for key in ORDER:
        chunks = caption_chunks(NARRATION[key])
        weights = [max(1, len(re.sub(r"\s", "", chunk))) for chunk in chunks]
        total_weight = sum(weights)
        cursor = segment_start
        for index, (chunk, weight) in enumerate(zip(chunks, weights, strict=True)):
            if index == len(chunks) - 1:
                cue_end = segment_start + durations[key]
            else:
                cue_end = cursor + durations[key] * weight / total_weight
            cues.extend(
                [
                    str(cue_number),
                    f"{timestamp(cursor)} --> {timestamp(cue_end)}",
                    chunk,
                    "",
                ]
            )
            cue_number += 1
            cursor = cue_end
        segment_start += durations[key]
    SUBTITLES.write_text("\ufeff" + "\n".join(cues), encoding="utf-8")


def encode_segment(ffmpeg: str, key: str, duration: float) -> Path:
    narration = NARRATION_DIR / f"{key}.wav"
    target = SEGMENT_DIR / f"{key}.mp4"
    common_output = [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-video_track_timescale",
        "15360",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        "-shortest",
        str(target),
    ]
    if key in STATIC:
        source = SLIDE_DIR / f"{key}.png"
        command = [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-loop",
            "1",
            "-framerate",
            "30",
            "-i",
            str(source),
            "-i",
            str(narration),
            "-t",
            f"{duration:.6f}",
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-tune",
            "stillimage",
            *common_output,
        ]
    else:
        source = SCREEN_DIR / f"{key}_screen.mp4"
        command = [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-i",
            str(narration),
            "-filter_complex",
            "[0:v]scale=1280:720,format=yuv420p,tpad=stop_mode=clone:stop_duration=3[v]",
            "-map",
            "[v]",
            "-map",
            "1:a:0",
            *common_output,
        ]
    run(command)
    return target


def build_video() -> dict[str, object]:
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    SEGMENT_DIR.mkdir(parents=True, exist_ok=True)
    make_slides()

    missing = []
    for key in ORDER:
        narration = NARRATION_DIR / f"{key}.wav"
        source = (SLIDE_DIR / f"{key}.png") if key in STATIC else (SCREEN_DIR / f"{key}_screen.mp4")
        if not narration.exists():
            missing.append(narration)
        if not source.exists():
            missing.append(source)
    if missing:
        raise FileNotFoundError("Missing video inputs: " + ", ".join(str(path) for path in missing))

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    durations = {key: wav_duration(NARRATION_DIR / f"{key}.wav") for key in ORDER}
    if sum(durations.values()) > 300:
        raise RuntimeError("Narration exceeds the competition's five-minute limit")

    segment_paths = [encode_segment(ffmpeg, key, durations[key]) for key in ORDER]
    build_subtitles(durations)

    concat_file = VIDEO_DIR / "segments.txt"
    concat_file.write_text(
        "\n".join(f"file '{path.relative_to(VIDEO_DIR).as_posix()}'" for path in segment_paths) + "\n",
        encoding="utf-8",
    )
    run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(CLEAN_VIDEO),
        ]
    )

    subtitle_filter = (
        "subtitles=output/video/NeuroChip_Copilot_Demo_zh.srt:"
        "force_style='FontName=Microsoft YaHei,FontSize=11,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BackColour=&H70000000,BorderStyle=3,Outline=1,"
        "Shadow=0,MarginV=8,Alignment=2'"
    )
    run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(CLEAN_VIDEO),
            "-vf",
            subtitle_filter,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(FINAL_VIDEO),
        ]
    )

    reader = imageio_ffmpeg.read_frames(str(FINAL_VIDEO), pix_fmt="rgb24")
    media_meta = next(reader)
    reader.close()
    final_duration = float(media_meta["duration"])
    if final_duration > 300:
        raise RuntimeError(f"Final video is {final_duration:.3f} s, exceeding five minutes")
    if tuple(media_meta["size"]) != (1280, 720):
        raise RuntimeError(f"Unexpected video size: {media_meta['size']}")

    digest = hashlib.sha256(FINAL_VIDEO.read_bytes()).hexdigest()
    metadata: dict[str, object] = {
        "title": "NeuroChip Copilot competition demo",
        "language": "zh-CN",
        "captioned": True,
        "resolution": list(media_meta["size"]),
        "fps": media_meta.get("fps"),
        "duration_s": final_duration,
        "size_bytes": FINAL_VIDEO.stat().st_size,
        "sha256": digest,
        "segments": [
            {"key": key, "narration_duration_s": durations[key], "source": "slide" if key in STATIC else "live_app_recording"}
            for key in ORDER
        ],
    }
    METADATA.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)
    return metadata


if __name__ == "__main__":
    build_video()
