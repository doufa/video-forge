from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
from pathlib import Path

from videoforge.resource_library.models import DownloadedResource
from videoforge.utils.paths import PROJECT_ROOT

logger = logging.getLogger(__name__)


def slugify(value: str, fallback: str = "resource") -> str:
    value = re.sub(r"[^\w\-. ]+", "_", value, flags=re.UNICODE)
    value = re.sub(r"\s+", "_", value).strip("._")
    return value[:120] or fallback


def find_related_files(video_path: Path, suffixes: set[str]) -> list[Path]:
    """Find yt-dlp sidecar files that share a video stem prefix."""
    parent = video_path.parent
    stem = video_path.stem
    files = []
    for candidate in parent.iterdir():
        if candidate == video_path or not candidate.is_file():
            continue
        if candidate.name.startswith(stem) and candidate.suffix.lower() in suffixes:
            files.append(candidate)
    return sorted(files)


def download_video_resource(
    url: str,
    output_dir: str | Path | None = None,
    subtitle_languages: str = "zh,en",
) -> DownloadedResource:
    """Download a video URL with subtitles and metadata using yt-dlp."""
    if output_dir is None:
        output_dir = PROJECT_ROOT / "output" / "assets"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_template = str(output_dir / "%(title).120B-%(id)s.%(ext)s")
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        url,
        "-f",
        "bestvideo[height<=1080][ext=mp4]+bestaudio/best[height<=1080]/best",
        "--merge-output-format",
        "mp4",
        "--write-info-json",
        "--write-subs",
        "--write-auto-subs",
        "--sub-lang",
        subtitle_languages,
        "--no-playlist",
        "-o",
        output_template,
    ]

    logger.info("Downloading resource: %s", url)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"yt-dlp timed out for URL: {url}") from exc

    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed for URL {url}: {result.stderr}")

    videos = sorted(
        [
            path
            for path in output_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".mp4", ".webm", ".mkv", ".mov"}
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not videos:
        raise FileNotFoundError(f"yt-dlp completed but no video was found in {output_dir}")

    video_path = videos[0]
    info_files = find_related_files(video_path, {".json"})
    subtitle_paths = find_related_files(video_path, {".vtt", ".srt"})

    title = video_path.stem
    info_path = info_files[0] if info_files else None
    if info_path:
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
            title = info.get("title") or title
        except (OSError, json.JSONDecodeError):
            pass

    return DownloadedResource(
        video_path=video_path,
        info_path=info_path,
        subtitle_paths=subtitle_paths,
        source_url=url,
        title=title,
    )


def local_video_resource(video_path: str | Path, subtitle_paths: list[str | Path] | None = None) -> DownloadedResource:
    """Wrap an existing local video as a resource."""
    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(f"Local video not found: {path}")

    subtitles = [Path(p) for p in subtitle_paths or []]
    if not subtitles:
        subtitles = find_related_files(path, {".vtt", ".srt"})

    info_files = find_related_files(path, {".json"})
    return DownloadedResource(
        video_path=path,
        info_path=info_files[0] if info_files else None,
        subtitle_paths=subtitles,
        source_url="",
        title=path.stem,
    )
