"""Tests for videoforge.resource_library.models — dataclass construction & properties."""

from __future__ import annotations

from pathlib import Path

from videoforge.resource_library.models import (
    DownloadedResource,
    IngestResult,
    ResourceSearchHit,
    SceneSegment,
    TranscriptCue,
)


class TestTranscriptCue:
    def test_defaults(self):
        cue = TranscriptCue(start_sec=0.0, end_sec=1.0, text="hello")
        assert cue.language == ""
        assert cue.is_auto_generated is False

    def test_auto_generated_flag(self):
        cue = TranscriptCue(start_sec=0.0, end_sec=1.0, text="auto",
                            is_auto_generated=True)
        assert cue.is_auto_generated is True

    def test_language(self):
        cue = TranscriptCue(start_sec=0.0, end_sec=1.0, text="hola",
                            language="es")
        assert cue.language == "es"


class TestSceneSegment:
    def test_duration_property(self):
        seg = SceneSegment(start_sec=10.0, end_sec=20.0)
        assert seg.duration_sec == 10.0

    def test_duration_non_negative(self):
        seg = SceneSegment(start_sec=20.0, end_sec=10.0)
        assert seg.duration_sec == 0.0  # max(0, -10)

    def test_duration_zero(self):
        seg = SceneSegment(start_sec=5.0, end_sec=5.0)
        assert seg.duration_sec == 0.0

    def test_defaults(self):
        seg = SceneSegment(start_sec=0.0, end_sec=1.0)
        assert seg.transcript_text == ""
        assert seg.keyframe_paths == []
        assert seg.tags == []
        assert seg.quality_score == 1.0


class TestDownloadedResource:
    def test_minimal(self):
        r = DownloadedResource(video_path=Path("/videos/test.mp4"))
        assert r.source_url == ""
        assert r.title == ""

    def test_full(self):
        r = DownloadedResource(
            video_path=Path("/videos/test.mp4"),
            info_path=Path("/videos/test.info.json"),
            subtitle_paths=[Path("/videos/test.en.vtt")],
            source_url="https://example.com/video",
            title="Test Video",
        )
        assert r.info_path == Path("/videos/test.info.json")
        assert len(r.subtitle_paths) == 1


class TestIngestResult:
    def test_default_vectors_zero(self):
        r = IngestResult(
            asset_id=1,
            asset_path=Path("/v/test.mp4"),
            segments_created=5,
            transcripts_created=3,
        )
        assert r.visual_vectors == 0
        assert r.text_vectors == 0


class TestResourceSearchHit:
    def test_default_keyframe_paths(self):
        hit = ResourceSearchHit(
            asset_path=Path("/v/test.mp4"),
            segment_id=1,
            start_sec=0.0,
            end_sec=10.0,
            score=0.85,
            match_type="hybrid",
        )
        assert hit.keyframe_paths == []
        assert hit.transcript_text == ""
