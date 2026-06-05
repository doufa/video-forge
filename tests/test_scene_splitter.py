"""Tests for videoforge.resource_library.scene_splitter — segmentation & normalization."""

from __future__ import annotations

from videoforge.resource_library.models import SceneSegment
from videoforge.resource_library.scene_splitter import (
    fixed_window_segments,
    normalize_segments,
)


# ── fixed_window_segments ───────────────────────────────────────

class TestFixedWindowSegments:
    def test_normal_duration(self):
        """A 60s video with default 12s window should produce 5 segments."""
        segments = fixed_window_segments(60.0, window_sec=12.0)
        assert len(segments) == 5
        assert segments[0].start_sec == 0.0
        assert segments[0].end_sec == 12.0
        assert segments[-1].start_sec == 48.0
        assert segments[-1].end_sec == 60.0

    def test_exact_window(self):
        """A duration exactly equal to the window should produce one segment."""
        segments = fixed_window_segments(12.0, window_sec=12.0)
        assert len(segments) == 1
        assert segments[0].start_sec == 0.0
        assert segments[0].end_sec == 12.0

    def test_partial_last_window(self):
        """When duration is not a multiple, the last segment is shorter."""
        segments = fixed_window_segments(15.0, window_sec=12.0)
        assert len(segments) == 2
        assert segments[1].start_sec == 12.0
        assert segments[1].end_sec == 15.0

    def test_zero_duration(self):
        assert fixed_window_segments(0.0) == []

    def test_negative_duration(self):
        assert fixed_window_segments(-1.0) == []

    def test_custom_window(self):
        segments = fixed_window_segments(100.0, window_sec=30.0)
        assert len(segments) == 4  # 30 + 30 + 30 + 10
        assert segments[-1].end_sec == 100.0


# ── normalize_segments ──────────────────────────────────────────

class TestNormalizeSegments:
    def test_empty_list_returns_fallback(self):
        """Empty segment list should produce fixed-window fallback."""
        segments = normalize_segments([], duration_sec=24.0, fallback_window_sec=12.0)
        assert len(segments) == 2
        assert segments[0].start_sec == 0.0
        assert segments[1].end_sec == 24.0

    def test_empty_list_zero_duration(self):
        assert normalize_segments([], duration_sec=0.0) == []

    def test_merges_short_segments(self):
        """A segment shorter than min_duration should be merged into the previous one."""
        segments = [
            SceneSegment(start_sec=0.0, end_sec=10.0),
            SceneSegment(start_sec=10.0, end_sec=11.5),  # 1.5s < 3s → merge
            SceneSegment(start_sec=11.5, end_sec=20.0),
        ]
        result = normalize_segments(segments, duration_sec=20.0, min_duration_sec=3.0)
        assert len(result) == 2
        # The short middle segment should be absorbed into the first
        assert result[0].end_sec >= 11.5

    def test_splits_long_segments(self):
        """A segment longer than max_duration should be split."""
        segments = [
            SceneSegment(start_sec=0.0, end_sec=70.0),  # 70s > 30s max
        ]
        result = normalize_segments(segments, duration_sec=70.0, max_duration_sec=30.0, fallback_window_sec=12.0)
        assert len(result) > 2
        for seg in result:
            assert seg.duration_sec <= 30.0

    def test_preserves_normal_segments(self):
        """Segments within the acceptable range should pass through unchanged."""
        segments = [
            SceneSegment(start_sec=0.0, end_sec=10.0),
            SceneSegment(start_sec=10.0, end_sec=20.0),
        ]
        result = normalize_segments(segments, duration_sec=20.0)
        assert len(result) == 2
        assert result[0].start_sec == 0.0
        assert result[0].end_sec == 10.0
        assert result[1].start_sec == 10.0
        assert result[1].end_sec == 20.0

    def test_last_segment_short_merged_into_previous(self):
        """If the last segment is too short, merge it into the previous one."""
        segments = [
            SceneSegment(start_sec=0.0, end_sec=12.0),
            SceneSegment(start_sec=12.0, end_sec=14.0),  # 2s < 3s → merge into previous
        ]
        result = normalize_segments(segments, duration_sec=14.0, min_duration_sec=3.0)
        assert len(result) == 1
        assert result[0].end_sec == 14.0

    def test_clamps_to_duration(self):
        """Segment end times should not exceed the video duration."""
        segments = [
            SceneSegment(start_sec=0.0, end_sec=50.0),
        ]
        result = normalize_segments(segments, duration_sec=30.0)
        for seg in result:
            assert seg.end_sec <= 30.0

    def test_removes_zero_duration_segments(self):
        """Segments where end <= start should be removed."""
        segments = [
            SceneSegment(start_sec=10.0, end_sec=5.0),  # invalid
            SceneSegment(start_sec=10.0, end_sec=10.0),  # zero duration
            SceneSegment(start_sec=20.0, end_sec=30.0),  # valid
        ]
        result = normalize_segments(segments, duration_sec=30.0)
        # After removing the first two, only the valid one + fallback if empty
        assert len(result) >= 1
        for seg in result:
            assert seg.end_sec > seg.start_sec

    def test_preserves_segment_metadata(self):
        """Quality score and tags should survive normalization."""
        segments = [
            SceneSegment(start_sec=0.0, end_sec=10.0, tags=["intro"], quality_score=0.9),
        ]
        result = normalize_segments(segments, duration_sec=10.0)
        assert result[0].tags == ["intro"]
        assert result[0].quality_score == 0.9
