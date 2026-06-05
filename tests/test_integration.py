"""Integration test: complete Resource Library ingest → DB → search flow.

Tests the full orchestration pipeline with mocked external dependencies
(CLIP, ffmpeg, PySceneDetect, yt-dlp) but real SQLite and FAISS operations.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from videoforge.resource_library.indexer import ResourceIndexer
from videoforge.resource_library.models import SceneSegment, TranscriptCue
from videoforge.resource_library.search import ResourceSearcher
from videoforge.storage.database import Database

pytest.importorskip("faiss", reason="FAISS is required for VectorStore operations")
pytest.importorskip("numpy", reason="NumPy is required for vector operations")


@pytest.fixture
def fake_video(tmp_path: Path) -> Path:
    """A fake video file that exists on disk."""
    p = tmp_path / "demo_video.mp4"
    p.write_text("fake video bytes")
    return p


@pytest.fixture
def fake_subtitle(tmp_path: Path) -> Path:
    """A fake subtitle file (content not read — parsing is mocked)."""
    p = tmp_path / "subtitle.zh.vtt"
    p.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nplaceholder", encoding="utf-8")
    return p


@pytest.fixture
def fake_keyframes(tmp_path: Path) -> list[Path]:
    """Fake keyframe image files that exist on disk."""
    paths = []
    for i in range(1, 4):
        p = tmp_path / f"kf_{i:02d}.jpg"
        p.write_text("fake jpeg data")
        paths.append(p)
    return paths


@pytest.fixture
def sample_cues() -> list[TranscriptCue]:
    """Transcript cues returned by the mocked subtitle parser."""
    return [
        TranscriptCue(start_sec=0.0, end_sec=3.0, text="Hello and welcome to this video", language="zh"),
        TranscriptCue(start_sec=3.5, end_sec=6.0, text="Today we will learn about water molecules", language="zh"),
        TranscriptCue(start_sec=7.0, end_sec=10.0, text="水分子由两个氢原子和一个氧原子组成", language="zh"),
    ]


@pytest.fixture
def sample_scenes() -> list[SceneSegment]:
    """Scene segments returned by the mocked scene detector (no keyframes yet)."""
    return [
        SceneSegment(start_sec=0.0, end_sec=5.0),
        SceneSegment(start_sec=5.0, end_sec=10.0),
    ]


# ── Helpers ─────────────────────────────────────────────────────

def _make_embedding(value: float = 0.1, dim: int = 512) -> np.ndarray:
    """Create a unit-normalized embedding vector."""
    vec = np.full(dim, value, dtype=np.float32)
    norm = np.linalg.norm(vec)
    return (vec / norm).astype(np.float32) if norm > 0 else vec


# ── Integration tests ───────────────────────────────────────────

class TestIngestAndSearch:
    """End-to-end flow: ingest_local → verify DB → rebuild → search."""

    def test_ingest_then_search(
        self,
        tmp_path: Path,
        fake_video: Path,
        fake_subtitle: Path,
        fake_keyframes: list[Path],
        sample_cues: list[TranscriptCue],
        sample_scenes: list[SceneSegment],
    ):
        db_path = tmp_path / "library.db"
        vis_path = tmp_path / "segment_visual"
        txt_path = tmp_path / "segment_text"

        # ── Phase 1: Ingest ──────────────────────────────────

        with (
            patch("videoforge.resource_library.indexer.detect_scene_segments", return_value=sample_scenes),
            patch("videoforge.resource_library.indexer.parse_subtitle_file", return_value=sample_cues),
            patch("videoforge.resource_library.indexer.sample_segment_keyframes", return_value=fake_keyframes),
            patch.object(ResourceIndexer, "_segment_visual_embedding", return_value=_make_embedding(0.1)),
            patch.object(ResourceIndexer, "_segment_text_embedding", return_value=_make_embedding(0.2)),
            patch("videoforge.resource_library.indexer.SEGMENT_VISUAL_INDEX", vis_path),
            patch("videoforge.resource_library.indexer.SEGMENT_TEXT_INDEX", txt_path),
        ):
            indexer = ResourceIndexer(db_path=db_path)
            result = indexer.ingest_local(
                str(fake_video),
                subtitle_paths=[str(fake_subtitle)],
            )

        # ── Verify IngestResult ──────────────────────────
        assert result.asset_id > 0
        assert result.segments_created == 2
        assert result.transcripts_created == 3
        assert result.visual_vectors == 2  # one per segment
        assert result.text_vectors == 2

        # ── Verify DB state — asset ──────────────────────
        with Database(db_path) as db:
            asset = db.get_asset(result.asset_id)
            assert asset is not None
            assert asset.filename_original == fake_video.name
            assert asset.asset_type == "video"
            assert asset.source == "local"
            assert asset.file_size == fake_video.stat().st_size

            # ── Verify DB state — transcripts ────────────
            transcripts = db.list_asset_transcripts(result.asset_id)
            assert len(transcripts) == 3
            assert transcripts[0].text == "Hello and welcome to this video"
            assert transcripts[0].language == "zh"
            assert transcripts[1].text == "Today we will learn about water molecules"
            assert transcripts[2].text == "水分子由两个氢原子和一个氧原子组成"
            # Verify ascending time order
            starts = [t.start_sec for t in transcripts]
            assert starts == sorted(starts)

            # ── Verify DB state — segments ───────────────
            segments = db.list_asset_segments(asset_id=result.asset_id)
            assert len(segments) == 2

            # Segment 0: 0–5s
            seg0 = segments[0]
            assert seg0.start_sec == 0.0
            assert seg0.end_sec == 5.0
            assert len(seg0.keyframe_paths) > 0
            assert seg0.visual_embedding_id == f"segment:{seg0.id}:visual"
            assert seg0.text_embedding_id == f"segment:{seg0.id}:text"
            assert seg0.quality_score == 1.0

            # Segment 1: 5–10s
            seg1 = segments[1]
            assert seg1.start_sec == 5.0
            assert seg1.end_sec == 10.0
            assert len(seg1.keyframe_paths) > 0

        # ── Phase 2: Search ──────────────────────────────────

        with (
            patch("videoforge.resource_library.search.SEGMENT_VISUAL_INDEX", vis_path),
            patch("videoforge.resource_library.search.SEGMENT_TEXT_INDEX", txt_path),
            patch(
                "videoforge.skills.asset_tag.clip_embedder.get_text_embedding",
                return_value=_make_embedding(0.15),
                create=True,
            ),
        ):
            searcher = ResourceSearcher(db_path=db_path)
            results = searcher.search("water molecules", limit=5)

        # ── Verify search results ───────────────────────
        assert len(results) > 0
        for hit in results:
            assert hit.score > 0
            assert hit.match_type in ("hybrid", "visual", "text")
            assert hit.segment_id > 0

        # All results should have transcript text attached
        for hit in results:
            assert isinstance(hit.transcript_text, str)

        # Verify keyframe paths are resolved
        for hit in results:
            assert len(hit.keyframe_paths) > 0
            for kfp in hit.keyframe_paths:
                assert isinstance(kfp, Path)
                assert kfp.exists()

    # ── Edge cases ────────────────────────────────────────────

    def test_ingest_without_subtitles(
        self,
        tmp_path: Path,
        fake_video: Path,
        sample_scenes: list[SceneSegment],
    ):
        """Ingest a video with no subtitles should still create segments."""
        db_path = tmp_path / "no_sub.db"
        vis_path = tmp_path / "no_sub_visual"
        txt_path = tmp_path / "no_sub_text"

        with (
            patch("videoforge.resource_library.indexer.detect_scene_segments", return_value=sample_scenes),
            patch("videoforge.resource_library.indexer.sample_segment_keyframes", return_value=[]),
            patch.object(ResourceIndexer, "_segment_text_embedding", return_value=None),
            patch.object(ResourceIndexer, "_segment_visual_embedding", return_value=None),
            patch("videoforge.resource_library.indexer.SEGMENT_VISUAL_INDEX", vis_path),
            patch("videoforge.resource_library.indexer.SEGMENT_TEXT_INDEX", txt_path),
        ):
            indexer = ResourceIndexer(db_path=db_path)
            result = indexer.ingest_local(str(fake_video))

        assert result.segments_created == 2
        assert result.transcripts_created == 0
        assert result.visual_vectors == 0  # no keyframes → no visual
        assert result.text_vectors == 0  # no transcript → no text

        with Database(db_path) as db:
            segments = db.list_asset_segments(asset_id=result.asset_id)
            for seg in segments:
                assert seg.keyframe_paths == []
                assert seg.visual_embedding_id == ""
                assert seg.text_embedding_id == ""

    def test_rebuild_index(
        self,
        tmp_path: Path,
        fake_video: Path,
        fake_subtitle: Path,
        sample_cues: list[TranscriptCue],
        sample_scenes: list[SceneSegment],
    ):
        """Rebuilding the index from existing DB data should work."""
        db_path = tmp_path / "rebuild.db"
        vis_path = tmp_path / "rebuild_visual"
        txt_path = tmp_path / "rebuild_text"

        # First ingest
        with (
            patch("videoforge.resource_library.indexer.detect_scene_segments", return_value=sample_scenes),
            patch("videoforge.resource_library.indexer.parse_subtitle_file", return_value=sample_cues),
            patch("videoforge.resource_library.indexer.sample_segment_keyframes", return_value=[]),
            patch.object(ResourceIndexer, "_segment_visual_embedding", return_value=_make_embedding(0.1)),
            patch.object(ResourceIndexer, "_segment_text_embedding", return_value=_make_embedding(0.2)),
            patch("videoforge.resource_library.indexer.SEGMENT_VISUAL_INDEX", vis_path),
            patch("videoforge.resource_library.indexer.SEGMENT_TEXT_INDEX", txt_path),
        ):
            indexer = ResourceIndexer(db_path=db_path)
            indexer.ingest_local(str(fake_video), subtitle_paths=[str(fake_subtitle)])

        # Now rebuild
        with (
            patch.object(ResourceIndexer, "_segment_visual_embedding", return_value=_make_embedding(0.1)),
            patch.object(ResourceIndexer, "_segment_text_embedding", return_value=_make_embedding(0.2)),
            patch("videoforge.resource_library.indexer.SEGMENT_VISUAL_INDEX", vis_path),
            patch("videoforge.resource_library.indexer.SEGMENT_TEXT_INDEX", txt_path),
        ):
            indexer2 = ResourceIndexer(db_path=db_path)
            v, t = indexer2.rebuild_segment_indexes()
            assert v == 2
            assert t == 2

    def test_ingest_twice_updates_existing_asset(
        self,
        tmp_path: Path,
        fake_video: Path,
        sample_cues: list[TranscriptCue],
        sample_scenes: list[SceneSegment],
    ):
        """Re-ingesting the same video should clear old data and re-index."""
        db_path = tmp_path / "reingest.db"
        vis_path = tmp_path / "reingest_visual"
        txt_path = tmp_path / "reingest_text"

        # Create a subtitle file that matches the video stem for auto-discovery
        subtitle_path = tmp_path / "demo_video.zh.vtt"
        subtitle_path.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nplaceholder", encoding="utf-8")

        patchers = {
            "detect": patch("videoforge.resource_library.indexer.detect_scene_segments", return_value=sample_scenes),
            "subs": patch("videoforge.resource_library.indexer.parse_subtitle_file", return_value=sample_cues),
            "kf": patch("videoforge.resource_library.indexer.sample_segment_keyframes", return_value=[]),
            "vis_emb": patch.object(ResourceIndexer, "_segment_visual_embedding", return_value=_make_embedding(0.1)),
            "txt_emb": patch.object(ResourceIndexer, "_segment_text_embedding", return_value=_make_embedding(0.2)),
            "vis_idx": patch("videoforge.resource_library.indexer.SEGMENT_VISUAL_INDEX", vis_path),
            "txt_idx": patch("videoforge.resource_library.indexer.SEGMENT_TEXT_INDEX", txt_path),
        }

        # Ingest once
        with contextlib.ExitStack() as stack:
            for p in patchers.values():
                stack.enter_context(p)
            indexer = ResourceIndexer(db_path=db_path)
            r1 = indexer.ingest_local(str(fake_video))

        # Ingest again
        with contextlib.ExitStack() as stack:
            for p in patchers.values():
                stack.enter_context(p)
            indexer = ResourceIndexer(db_path=db_path)
            r2 = indexer.ingest_local(str(fake_video))

        # Same asset reused
        assert r2.asset_id == r1.asset_id

        with Database(db_path) as db:
            # Old transcripts/segs gone, new ones exist
            assert len(db.list_asset_transcripts(r2.asset_id)) == 3
            segments = db.list_asset_segments(asset_id=r2.asset_id)
            assert len(segments) == 2
            assert len(db.list_asset_segments(asset_id=99999)) == 0

        # Search should still work after re-ingest
        with (
            patch("videoforge.resource_library.search.SEGMENT_VISUAL_INDEX", vis_path),
            patch("videoforge.resource_library.search.SEGMENT_TEXT_INDEX", txt_path),
            patch("videoforge.skills.asset_tag.clip_embedder.get_text_embedding", return_value=_make_embedding(0.15), create=True),
        ):
            searcher = ResourceSearcher(db_path=db_path)
            results = searcher.search("water", limit=5)
            assert len(results) > 0
