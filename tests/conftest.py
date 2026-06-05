"""Shared fixtures for resource library tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from videoforge.resource_library.models import SceneSegment, TranscriptCue
from videoforge.storage.database import Asset, AssetSegment, AssetTranscript, Database


@pytest.fixture
def db() -> Database:
    """Yields a Database connected to :memory: with all tables created."""
    with Database(":memory:") as database:
        yield database


@pytest.fixture
def sample_asset(db: Database) -> int:
    """Create and return the ID of a sample asset."""
    asset = Asset(
        path="videos/demo.mp4",
        asset_type="video",
        source="local",
        filename_original="demo.mp4",
        description="A test video",
        tags=["demo", "test"],
        duration_sec=120.0,
        width=1920,
        height=1080,
        file_size=10_485_760,
        reviewed=False,
    )
    return db.add_asset(asset)


@pytest.fixture
def sample_transcripts() -> list[TranscriptCue]:
    """Sample subtitle cues for testing."""
    return [
        TranscriptCue(start_sec=0.0, end_sec=3.0, text="Hello and welcome", language="en"),
        TranscriptCue(start_sec=3.5, end_sec=6.0, text="This is a test video", language="en"),
        TranscriptCue(start_sec=7.0, end_sec=10.0, text="Today we will learn about water molecules", language="en"),
        TranscriptCue(start_sec=10.5, end_sec=14.0, text="水分子由两个氢原子和一个氧原子组成", language="zh"),
        TranscriptCue(start_sec=15.0, end_sec=18.0, text="Thanks for watching", language="en"),
    ]


@pytest.fixture
def sample_segments() -> list[SceneSegment]:
    """Sample scene segments for testing."""
    return [
        SceneSegment(start_sec=0.0, end_sec=5.0, transcript_text="Hello and welcome this is a test video", quality_score=1.0),
        SceneSegment(start_sec=5.0, end_sec=12.0, transcript_text="Today we will learn about water molecules", quality_score=1.0),
        SceneSegment(start_sec=12.0, end_sec=20.0, transcript_text="水分子由两个氢原子和一个氧原子组成 Thanks for watching", quality_score=1.0),
    ]


@pytest.fixture
def sample_vtt_content() -> str:
    """Standard VTT subtitle content."""
    return """WEBVTT

00:00:00.000 --> 00:00:03.000
Hello and welcome

00:00:03.500 --> 00:00:06.000
This is a test video

00:00:07.000 --> 00:00:10.000
Today we will learn about
water molecules

00:00:10.500 --> 00:00:14.000
水分子由两个氢原子和一个氧原子组成

00:00:15.000 --> 00:00:18.000
Thanks for watching
"""


@pytest.fixture
def sample_srt_content() -> str:
    """Standard SRT subtitle content."""
    return """1
00:00:00,000 --> 00:00:03,000
Hello and welcome

2
00:00:03,500 --> 00:00:06,000
This is a test video

3
00:00:07,000 --> 00:00:10,000
Today we will learn about water molecules

4
00:00:10,500 --> 00:00:14,000
水分子由两个氢原子和一个氧原子组成

5
00:00:15,000 --> 00:00:18,000
Thanks for watching
"""


@pytest.fixture
def sample_vtt_path(tmp_path: Path, sample_vtt_content: str) -> Path:
    """Write sample VTT content to a temp file."""
    path = tmp_path / "subtitle.en.vtt"
    path.write_text(sample_vtt_content, encoding="utf-8")
    return path


@pytest.fixture
def sample_srt_path(tmp_path: Path, sample_srt_content: str) -> Path:
    """Write sample SRT content to a temp file."""
    path = tmp_path / "subtitle.en.srt"
    path.write_text(sample_srt_content, encoding="utf-8")
    return path


@pytest.fixture
def db_with_data(db: Database, sample_asset: int, sample_transcripts: list[TranscriptCue], sample_segments: list[SceneSegment]) -> tuple[Database, int, list[int], list[int]]:
    """Database pre-populated with an asset, transcripts, and segments.

    Returns (db, asset_id, transcript_ids, segment_ids).
    """
    asset_id = sample_asset
    transcript_ids: list[int] = []
    for cue in sample_transcripts:
        tid = db.add_asset_transcript(
            AssetTranscript(
                asset_id=asset_id,
                start_sec=cue.start_sec,
                end_sec=cue.end_sec,
                text=cue.text,
                language=cue.language,
                is_auto_generated=cue.is_auto_generated,
            )
        )
        transcript_ids.append(tid)

    segment_ids: list[int] = []
    for seg in sample_segments:
        sid = db.add_asset_segment(
            AssetSegment(
                asset_id=asset_id,
                start_sec=seg.start_sec,
                end_sec=seg.end_sec,
                duration_sec=seg.duration_sec,
                transcript_text=seg.transcript_text,
                keyframe_paths=["frames/frame_01.jpg", "frames/frame_02.jpg"],
                tags=["scene", "test"],
                quality_score=seg.quality_score,
            )
        )
        segment_ids.append(sid)

    return db, asset_id, transcript_ids, segment_ids
