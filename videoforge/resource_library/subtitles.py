from __future__ import annotations

import html
import re
from pathlib import Path

from videoforge.resource_library.models import SceneSegment, TranscriptCue

_TIMING_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}:\d{2}[.,]\d{3}|\d{1,2}:\d{2}[.,]\d{3})"
    r"\s*-->\s*"
    r"(?P<end>\d{1,2}:\d{2}:\d{2}[.,]\d{3}|\d{1,2}:\d{2}[.,]\d{3})"
)
_TAG_RE = re.compile(r"<[^>]+>")


def parse_timestamp(value: str) -> float:
    """Parse a VTT/SRT timestamp into seconds."""
    value = value.strip().replace(",", ".")
    parts = value.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours = "0"
        minutes, seconds = parts
    else:
        raise ValueError(f"Invalid subtitle timestamp: {value}")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def clean_subtitle_text(text: str) -> str:
    """Remove VTT/SRT markup and normalize whitespace."""
    text = html.unescape(text)
    text = _TAG_RE.sub("", text)
    text = re.sub(r"\{\\.*?\}", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_subtitle_file(
    subtitle_path: str | Path,
    language: str = "",
    is_auto_generated: bool = False,
) -> list[TranscriptCue]:
    """Parse VTT or SRT subtitles while keeping cue timestamps."""
    path = Path(subtitle_path)
    content = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    cues: list[TranscriptCue] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = _TIMING_RE.search(line)
        if not match:
            i += 1
            continue

        start_sec = parse_timestamp(match.group("start"))
        end_sec = parse_timestamp(match.group("end"))
        i += 1

        text_lines = []
        while i < len(lines) and lines[i].strip():
            text_line = lines[i].strip()
            if not text_line.startswith(("NOTE", "STYLE", "REGION")):
                text_lines.append(text_line)
            i += 1

        text = clean_subtitle_text(" ".join(text_lines))
        if text and end_sec > start_sec:
            cues.append(
                TranscriptCue(
                    start_sec=start_sec,
                    end_sec=end_sec,
                    text=text,
                    language=language,
                    is_auto_generated=is_auto_generated,
                )
            )
    return cues


def infer_subtitle_language(path: str | Path) -> str:
    """Infer language from yt-dlp subtitle filenames like video.zh.vtt."""
    suffixes = Path(path).suffixes
    if len(suffixes) >= 2:
        candidate = suffixes[-2].lstrip(".")
        if candidate and candidate not in {"auto", "orig"}:
            return candidate
    return ""


def is_auto_subtitle(path: str | Path) -> bool:
    name = Path(path).name.lower()
    return ".auto." in name or "automatic" in name


def choose_preferred_subtitle(paths: list[Path]) -> Path | None:
    """Choose the best subtitle file, preferring human zh then human en."""
    if not paths:
        return None

    def score(path: Path) -> tuple[int, str]:
        lang = infer_subtitle_language(path).lower()
        auto_penalty = 10 if is_auto_subtitle(path) else 0
        if lang.startswith("zh"):
            lang_score = 0
        elif lang.startswith("en"):
            lang_score = 1
        else:
            lang_score = 2
        return (auto_penalty + lang_score, path.name)

    return sorted(paths, key=score)[0]


def assign_transcripts_to_segments(
    cues: list[TranscriptCue],
    segments: list[SceneSegment],
) -> list[SceneSegment]:
    """Attach overlapping subtitle text to each scene segment."""
    assigned: list[SceneSegment] = []
    for segment in segments:
        texts = [
            cue.text
            for cue in cues
            if cue.end_sec > segment.start_sec and cue.start_sec < segment.end_sec
        ]
        transcript_text = clean_subtitle_text(" ".join(texts))
        assigned.append(
            SceneSegment(
                start_sec=segment.start_sec,
                end_sec=segment.end_sec,
                transcript_text=transcript_text,
                keyframe_paths=list(segment.keyframe_paths),
                tags=list(segment.tags),
                quality_score=segment.quality_score,
            )
        )
    return assigned
