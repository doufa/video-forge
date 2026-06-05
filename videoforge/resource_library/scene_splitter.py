from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from videoforge.resource_library.models import SceneSegment

logger = logging.getLogger(__name__)


def get_video_duration(video_path: str | Path) -> float:
    """Return video duration in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            return max(0.0, float(result.stdout.strip()))
    except Exception as exc:
        logger.debug("ffprobe duration failed for %s: %s", video_path, exc)
    return 0.0


def fixed_window_segments(duration_sec: float, window_sec: float = 12.0) -> list[SceneSegment]:
    """Create fixed-size fallback segments."""
    if duration_sec <= 0:
        return []

    segments = []
    start = 0.0
    while start < duration_sec:
        end = min(duration_sec, start + window_sec)
        segments.append(SceneSegment(start_sec=start, end_sec=end))
        start = end
    return segments


def normalize_segments(
    segments: list[SceneSegment],
    duration_sec: float,
    min_duration_sec: float = 3.0,
    max_duration_sec: float = 30.0,
    fallback_window_sec: float = 12.0,
) -> list[SceneSegment]:
    """Merge tiny segments and split very long ones."""
    if not segments:
        return fixed_window_segments(duration_sec, fallback_window_sec)

    ordered = sorted(
        (
            SceneSegment(
                start_sec=max(0.0, segment.start_sec),
                end_sec=min(duration_sec, segment.end_sec) if duration_sec > 0 else segment.end_sec,
                transcript_text=segment.transcript_text,
                keyframe_paths=list(segment.keyframe_paths),
                tags=list(segment.tags),
                quality_score=segment.quality_score,
            )
            for segment in segments
            if segment.end_sec > segment.start_sec
        ),
        key=lambda segment: segment.start_sec,
    )
    if not ordered:
        return fixed_window_segments(duration_sec, fallback_window_sec)

    merged: list[SceneSegment] = []
    for segment in ordered:
        if merged and segment.duration_sec < min_duration_sec:
            previous = merged[-1]
            previous.end_sec = max(previous.end_sec, segment.end_sec)
        else:
            merged.append(segment)

    if len(merged) > 1 and merged[-1].duration_sec < min_duration_sec:
        tail = merged.pop()
        merged[-1].end_sec = max(merged[-1].end_sec, tail.end_sec)

    normalized: list[SceneSegment] = []
    for segment in merged:
        if segment.duration_sec <= max_duration_sec:
            normalized.append(segment)
            continue

        start = segment.start_sec
        while start < segment.end_sec:
            end = min(segment.end_sec, start + fallback_window_sec)
            normalized.append(SceneSegment(start_sec=start, end_sec=end))
            start = end

    return normalized


def detect_scene_segments(
    video_path: str | Path,
    threshold: float = 27.0,
    min_duration_sec: float = 3.0,
    max_duration_sec: float = 30.0,
    fallback_window_sec: float = 12.0,
) -> list[SceneSegment]:
    """Detect scene segments using PySceneDetect, with deterministic fallback."""
    path = Path(video_path)
    duration_sec = get_video_duration(path)

    raw_segments: list[SceneSegment] = []
    try:
        from scenedetect import ContentDetector, detect

        scene_list = detect(str(path), ContentDetector(threshold=threshold))
        for start_time, end_time in scene_list:
            raw_segments.append(
                SceneSegment(
                    start_sec=start_time.get_seconds(),
                    end_sec=end_time.get_seconds(),
                )
            )
    except Exception as exc:
        logger.warning("PySceneDetect failed for %s, using fixed windows: %s", path, exc)

    return normalize_segments(
        raw_segments,
        duration_sec=duration_sec,
        min_duration_sec=min_duration_sec,
        max_duration_sec=max_duration_sec,
        fallback_window_sec=fallback_window_sec,
    )
