from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def sample_segment_keyframes(
    video_path: str | Path,
    output_dir: str | Path,
    start_sec: float,
    end_sec: float,
    count: int = 3,
) -> list[Path]:
    """Extract keyframes from the start/middle/end of a video segment."""
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    duration = max(0.0, end_sec - start_sec)
    if duration <= 0:
        return []

    if count <= 1:
        timestamps = [start_sec + duration / 2]
    elif count == 2:
        timestamps = [start_sec + min(0.5, duration / 4), end_sec - min(0.5, duration / 4)]
    else:
        timestamps = [
            start_sec + min(0.5, duration * 0.15),
            start_sec + duration / 2,
            end_sec - min(0.5, duration * 0.15),
        ]

    frame_paths: list[Path] = []
    for index, timestamp in enumerate(timestamps[:count], 1):
        frame_path = output_dir / f"frame_{index:02d}.jpg"
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{max(0.0, timestamp):.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(frame_path),
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0 and frame_path.exists() and frame_path.stat().st_size > 0:
                frame_paths.append(frame_path)
            else:
                logger.debug("ffmpeg frame extraction failed: %s", result.stderr)
        except Exception as exc:
            logger.debug("Failed to extract keyframe at %.3fs: %s", timestamp, exc)

    return frame_paths
