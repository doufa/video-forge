"""Tests for videoforge.resource_library.search — quality scoring."""

from __future__ import annotations

import pytest

from videoforge.storage.database import AssetSegment

# Import the private function directly for unit testing
from videoforge.resource_library.search import _compute_quality_bonus


# ── _compute_quality_bonus ──────────────────────────────────────

class TestComputeQualityBonus:
    # Baseline: duration_sec=3.0 is below the 5s threshold, so no duration bonus.

    def test_baseline_score(self):
        """A segment with duration below threshold should have baseline 0.5."""
        seg = AssetSegment(start_sec=0.0, end_sec=3.0, duration_sec=3.0)
        score = _compute_quality_bonus(seg)
        assert score == pytest.approx(0.5)

    def test_duration_bonus_8_to_20(self):
        """8-20s duration should add 0.2."""
        seg = AssetSegment(start_sec=0.0, end_sec=15.0, duration_sec=15.0)
        score = _compute_quality_bonus(seg)
        assert score == pytest.approx(0.7)

    def test_duration_bonus_5_to_30_excluding_8_20(self):
        """5-30s duration (but not 8-20) should add 0.1."""
        seg = AssetSegment(start_sec=0.0, end_sec=6.0, duration_sec=6.0)
        score = _compute_quality_bonus(seg)
        assert score == pytest.approx(0.6)

    def test_duration_bonus_outside_range(self):
        """Duration outside 5-30 should get no bonus."""
        seg = AssetSegment(start_sec=0.0, end_sec=45.0, duration_sec=45.0)
        score = _compute_quality_bonus(seg)
        assert score == pytest.approx(0.5)

    def test_text_length_bonus_over_50(self):
        """Transcript text > 50 chars should add 0.2 (baseline + duration 5-30 bonus + text)."""
        seg = AssetSegment(start_sec=0.0, end_sec=3.0, duration_sec=3.0,
                           transcript_text="A" * 60)
        score = _compute_quality_bonus(seg)
        assert score == pytest.approx(0.7)

    def test_text_length_bonus_20_to_50(self):
        """Transcript text 20-50 chars should add 0.1."""
        seg = AssetSegment(start_sec=0.0, end_sec=3.0, duration_sec=3.0,
                           transcript_text="A" * 30)
        score = _compute_quality_bonus(seg)
        assert score == pytest.approx(0.6)

    def test_text_length_under_20_no_bonus(self):
        seg = AssetSegment(start_sec=0.0, end_sec=3.0, duration_sec=3.0,
                           transcript_text="short")
        score = _compute_quality_bonus(seg)
        assert score == pytest.approx(0.5)

    def test_empty_text_no_bonus(self):
        seg = AssetSegment(start_sec=0.0, end_sec=3.0, duration_sec=3.0,
                           transcript_text="")
        score = _compute_quality_bonus(seg)
        assert score == pytest.approx(0.5)

    def test_keyframe_bonus_3_or_more(self):
        """3+ keyframes should add 0.1 (baseline + duration 5-30 bonus + kf)."""
        seg = AssetSegment(start_sec=0.0, end_sec=3.0, duration_sec=3.0,
                           keyframe_paths=["a.jpg", "b.jpg", "c.jpg"])
        score = _compute_quality_bonus(seg)
        assert score == pytest.approx(0.6)

    def test_keyframe_bonus_under_3_no_bonus(self):
        seg = AssetSegment(start_sec=0.0, end_sec=3.0, duration_sec=3.0,
                           keyframe_paths=["a.jpg", "b.jpg"])
        score = _compute_quality_bonus(seg)
        assert score == pytest.approx(0.5)

    def test_keyframes_none_no_bonus(self):
        seg = AssetSegment(start_sec=0.0, end_sec=3.0, duration_sec=3.0)
        score = _compute_quality_bonus(seg)
        assert score == pytest.approx(0.5)

    def test_all_bonuses_combined(self):
        """All bonuses should stack, capped at 1.0."""
        seg = AssetSegment(
            start_sec=0.0, end_sec=15.0, duration_sec=15.0,  # +0.2 (8-20s)
            transcript_text="A" * 60,  # +0.2
            keyframe_paths=["a.jpg", "b.jpg", "c.jpg"],  # +0.1
        )
        score = _compute_quality_bonus(seg)
        expected = min(0.5 + 0.2 + 0.2 + 0.1, 1.0)
        assert score == pytest.approx(expected)

    def test_score_capped_at_one(self):
        """Quality score should never exceed 1.0 even with all bonuses."""
        seg = AssetSegment(
            start_sec=0.0, end_sec=15.0, duration_sec=15.0,
            transcript_text="A" * 100,
            keyframe_paths=["a.jpg", "b.jpg", "c.jpg", "d.jpg"],
        )
        score = _compute_quality_bonus(seg)
        assert score <= 1.0
