from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TranscriptCue:
    """Timed subtitle cue parsed from VTT/SRT."""

    start_sec: float
    end_sec: float
    text: str
    language: str = ""
    is_auto_generated: bool = False


@dataclass
class SceneSegment:
    """Logical video segment used for indexing and retrieval."""

    start_sec: float
    end_sec: float
    transcript_text: str = ""
    keyframe_paths: list[Path] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    quality_score: float = 1.0

    @property
    def duration_sec(self) -> float:
        return max(0.0, self.end_sec - self.start_sec)


@dataclass
class DownloadedResource:
    """Downloaded video plus optional subtitles and metadata."""

    video_path: Path
    info_path: Path | None = None
    subtitle_paths: list[Path] = field(default_factory=list)
    source_url: str = ""
    title: str = ""


@dataclass
class IngestResult:
    """Resource ingestion summary."""

    asset_id: int
    asset_path: Path
    segments_created: int
    transcripts_created: int
    visual_vectors: int = 0
    text_vectors: int = 0


@dataclass
class ResourceSearchHit:
    """Segment-level search result."""

    asset_path: Path
    segment_id: int
    start_sec: float
    end_sec: float
    score: float
    match_type: str
    transcript_text: str = ""
    keyframe_paths: list[Path] = field(default_factory=list)
