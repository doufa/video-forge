"""Tests for videoforge.resource_library.subtitles — VTT/SRT parsing & alignment."""

from __future__ import annotations

from pathlib import Path

import pytest

from videoforge.resource_library.models import SceneSegment, TranscriptCue
from videoforge.resource_library.subtitles import (
    assign_transcripts_to_segments,
    choose_preferred_subtitle,
    clean_subtitle_text,
    infer_subtitle_language,
    is_auto_subtitle,
    parse_subtitle_file,
    parse_timestamp,
)


# ── parse_timestamp ─────────────────────────────────────────────

class TestParseTimestamp:
    def test_full_format(self):
        assert parse_timestamp("01:23:45.678") == 5025.678

    def test_short_format(self):
        assert parse_timestamp("12:34.567") == 754.567

    def test_zero(self):
        assert parse_timestamp("00:00.000") == 0.0

    def test_hours_only(self):
        assert parse_timestamp("01:00:00.000") == 3600.0

    def test_comma_separator(self):
        """SRT uses comma as decimal separator."""
        assert parse_timestamp("00:01:30,500") == 90.5

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            parse_timestamp("invalid")


# ── clean_subtitle_text ────────────────────────────────────────

class TestCleanSubtitleText:
    def test_removes_html_tags(self):
        assert clean_subtitle_text("<b>Hello</b> <i>world</i>") == "Hello world"

    def test_unescapes_html_entities(self):
        assert clean_subtitle_text("Tom &amp; Jerry") == "Tom & Jerry"

    def test_collapses_whitespace(self):
        result = clean_subtitle_text("Hello    world\n\nline2")
        assert result == "Hello world line2"

    def test_removes_vtt_style_annotations(self):
        result = clean_subtitle_text("Hello {\\an8}world")
        assert result == "Hello world"

    def test_strips_surrounding_whitespace(self):
        assert clean_subtitle_text("  hello  ") == "hello"

    def test_empty_string(self):
        assert clean_subtitle_text("") == ""


# ── infer_subtitle_language ─────────────────────────────────────

class TestInferSubtitleLanguage:
    def test_zh_from_suffix(self):
        assert infer_subtitle_language("video.zh.vtt") == "zh"

    def test_en_from_suffix(self):
        assert infer_subtitle_language("video.en.srt") == "en"

    def test_ja_from_suffix(self):
        assert infer_subtitle_language("video.ja.vtt") == "ja"

    def test_auto_suffix_not_treated_as_language(self):
        """The '.auto.' suffix should not be parsed as a language code."""
        lang = infer_subtitle_language("video.auto.vtt")
        assert lang == ""

    def test_orig_suffix_not_treated_as_language(self):
        lang = infer_subtitle_language("video.orig.srt")
        assert lang == ""

    def test_no_language_suffix(self):
        assert infer_subtitle_language("subtitles.vtt") == ""


# ── is_auto_subtitle ────────────────────────────────────────────

class TestIsAutoSubtitle:
    def test_auto_in_name(self):
        assert is_auto_subtitle("video.auto.zh.vtt") is True

    def test_automatic_keyword(self):
        assert is_auto_subtitle("Automatic subtitle.en.vtt") is True

    def test_manual_subtitle(self):
        assert is_auto_subtitle("video.en.vtt") is False


# ── parse_subtitle_file ─────────────────────────────────────────

class TestParseSubtitleFile:
    def test_parse_vtt(self, sample_vtt_path: Path):
        cues = parse_subtitle_file(sample_vtt_path, language="en")
        assert len(cues) == 5
        assert cues[0].start_sec == 0.0
        assert cues[0].end_sec == 3.0
        assert cues[0].text == "Hello and welcome"
        assert cues[0].language == "en"

    def test_parse_vtt_multiline_text(self, sample_vtt_path: Path):
        """VTT cues can span multiple lines; they should be joined."""
        cues = parse_subtitle_file(sample_vtt_path)
        # The third cue has two lines
        assert cues[2].text == "Today we will learn about water molecules"

    def test_parse_srt(self, sample_srt_path: Path):
        cues = parse_subtitle_file(sample_srt_path, language="en")
        assert len(cues) == 5
        assert cues[0].start_sec == 0.0
        assert cues[0].end_sec == 3.0

    def test_parse_srt_comma_timestamps(self, sample_srt_path: Path):
        """SRT uses comma decimal separator; verify correct parsing."""
        cues = parse_subtitle_file(sample_srt_path)
        assert cues[0].start_sec == 0.0

    def test_parse_srt_index_lines_ignored(self, sample_srt_path: Path):
        """SRT index lines (1, 2, 3…) before timestamps should be ignored."""
        cues = parse_subtitle_file(sample_srt_path)
        assert len(cues) == 5

    def test_parse_empty_file(self, tmp_path: Path):
        path = tmp_path / "empty.vtt"
        path.write_text("", encoding="utf-8")
        assert parse_subtitle_file(path) == []

    def test_parse_file_with_only_headers(self, tmp_path: Path):
        path = tmp_path / "no_cues.vtt"
        path.write_text("WEBVTT\n\nNOTE\nThis is a comment\n", encoding="utf-8")
        assert parse_subtitle_file(path) == []

    def test_parse_file_with_style_region_blocks(self, tmp_path: Path):
        """VTT STYLE and REGION blocks should be ignored."""
        content = """WEBVTT

STYLE
::cue { color: white }

REGION
id:test

00:00:01.000 --> 00:00:02.000
Hello
"""
        path = tmp_path / "styled.vtt"
        path.write_text(content, encoding="utf-8")
        cues = parse_subtitle_file(path)
        assert len(cues) == 1
        assert cues[0].text == "Hello"

    def test_preserves_text_encoding(self, tmp_path: Path):
        """Chinese characters should survive the round trip."""
        content = """WEBVTT

00:00:00.000 --> 00:00:02.000
你好世界
"""
        path = tmp_path / "chinese.vtt"
        path.write_text(content, encoding="utf-8")
        cues = parse_subtitle_file(path)
        assert cues[0].text == "你好世界"

    def test_bom_handling(self, tmp_path: Path):
        """File with UTF-8 BOM should be parsed correctly."""
        content = "﻿WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello\n"
        path = tmp_path / "bom.vtt"
        path.write_text(content, encoding="utf-8-sig")
        cues = parse_subtitle_file(path)
        assert len(cues) == 1

    def test_skip_cues_without_text(self, tmp_path: Path):
        """Cue with only whitespace should be skipped."""
        content = """WEBVTT

00:00:01.000 --> 00:00:02.000


00:00:03.000 --> 00:00:04.000
Real text
"""
        path = tmp_path / "whitespace.vtt"
        path.write_text(content, encoding="utf-8")
        cues = parse_subtitle_file(path)
        assert len(cues) == 1
        assert cues[0].text == "Real text"

    def test_skip_zero_duration_cues(self, tmp_path: Path):
        """Cues where end <= start should be skipped."""
        content = """WEBVTT

00:00:05.000 --> 00:00:05.000
Zero duration

00:00:06.000 --> 00:00:04.000
Negative duration
"""
        path = tmp_path / "zero_dur.vtt"
        path.write_text(content, encoding="utf-8")
        cues = parse_subtitle_file(path)
        assert len(cues) == 0


# ── choose_preferred_subtitle ───────────────────────────────────

class TestChoosePreferredSubtitle:
    def test_prefers_zh_over_en(self):
        paths = [
            Path("video.en.vtt"),
            Path("video.zh.vtt"),
        ]
        chosen = choose_preferred_subtitle(paths)
        assert chosen is not None
        assert "zh" in chosen.name

    def test_prefers_en_over_other(self):
        paths = [
            Path("video.ja.vtt"),
            Path("video.en.vtt"),
        ]
        chosen = choose_preferred_subtitle(paths)
        assert chosen is not None
        assert "en" in chosen.name

    def test_prefers_manual_over_auto(self):
        paths = [
            Path("video.auto.zh.vtt"),
            Path("video.zh.vtt"),
        ]
        chosen = choose_preferred_subtitle(paths)
        assert chosen is not None
        assert "auto" not in chosen.name

    def test_returns_none_for_empty_list(self):
        assert choose_preferred_subtitle([]) is None

    def test_single_path(self):
        path = Path("video.en.vtt")
        chosen = choose_preferred_subtitle([path])
        assert chosen == path


# ── assign_transcripts_to_segments ──────────────────────────────

class TestAssignTranscriptsToSegments:
    def test_segment_fully_contains_transcript(self):
        """A transcript entirely within a segment should be assigned."""
        segments = [SceneSegment(start_sec=0.0, end_sec=10.0)]
        cues = [TranscriptCue(start_sec=2.0, end_sec=5.0, text="inside")]
        result = assign_transcripts_to_segments(cues, segments)
        assert len(result) == 1
        assert "inside" in result[0].transcript_text

    def test_segment_partially_overlaps_transcript(self):
        """Transcript that overlaps segment start/end should still match."""
        segments = [SceneSegment(start_sec=5.0, end_sec=10.0)]
        cues = [TranscriptCue(start_sec=3.0, end_sec=8.0, text="overlap")]
        result = assign_transcripts_to_segments(cues, segments)
        assert "overlap" in result[0].transcript_text

    def test_no_overlap_returns_empty(self):
        segments = [SceneSegment(start_sec=10.0, end_sec=20.0)]
        cues = [TranscriptCue(start_sec=0.0, end_sec=5.0, text="no overlap")]
        result = assign_transcripts_to_segments(cues, segments)
        assert result[0].transcript_text == ""

    def test_multiple_cues_in_segment(self):
        segments = [SceneSegment(start_sec=0.0, end_sec=10.0)]
        cues = [
            TranscriptCue(start_sec=1.0, end_sec=3.0, text="first"),
            TranscriptCue(start_sec=4.0, end_sec=6.0, text="second"),
        ]
        result = assign_transcripts_to_segments(cues, segments)
        assert "first" in result[0].transcript_text
        assert "second" in result[0].transcript_text

    def test_multiple_segments(self):
        segments = [
            SceneSegment(start_sec=0.0, end_sec=5.0),
            SceneSegment(start_sec=5.0, end_sec=10.0),
        ]
        cues = [
            TranscriptCue(start_sec=2.0, end_sec=4.0, text="seg0"),
            TranscriptCue(start_sec=6.0, end_sec=8.0, text="seg1"),
        ]
        result = assign_transcripts_to_segments(cues, segments)
        assert "seg0" in result[0].transcript_text
        assert "seg1" in result[1].transcript_text

    def test_preserves_segment_metadata(self):
        segments = [
            SceneSegment(start_sec=0.0, end_sec=5.0, tags=["intro"], quality_score=0.9)
        ]
        cues = [TranscriptCue(start_sec=1.0, end_sec=3.0, text="hello")]
        result = assign_transcripts_to_segments(cues, segments)
        assert result[0].tags == ["intro"]
        assert result[0].quality_score == 0.9
        assert result[0].start_sec == 0.0

    def test_empty_cues_list(self):
        segments = [SceneSegment(start_sec=0.0, end_sec=5.0)]
        result = assign_transcripts_to_segments([], segments)
        assert result[0].transcript_text == ""

    def test_empty_segments_list(self):
        assert assign_transcripts_to_segments([TranscriptCue(start_sec=0.0, end_sec=1.0, text="x")], []) == []

    def test_adjacent_cue_boundary(self):
        """A cue ending exactly at a segment's start should NOT overlap (end > start check)."""
        segments = [SceneSegment(start_sec=5.0, end_sec=10.0)]
        cues = [TranscriptCue(start_sec=3.0, end_sec=5.0, text="boundary")]
        result = assign_transcripts_to_segments(cues, segments)
        assert result[0].transcript_text == ""
