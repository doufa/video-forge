"""Tests for videoforge.storage.database — new resource library tables."""

from __future__ import annotations

from datetime import datetime

import pytest

from videoforge.storage.database import AssetSegment, AssetTranscript, Database


# ── Table creation ──────────────────────────────────────────────

class TestTableCreation:
    def test_all_tables_exist(self, db: Database):
        """Verify the five core tables are created on init."""
        conn = db._conn  # type: ignore  # direct access for test
        tables = {row["name"] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert "assets" in tables
        assert "projects" in tables
        assert "rag_templates" in tables
        assert "asset_transcripts" in tables
        assert "asset_segments" in tables

    def test_segment_indexes_exist(self, db: Database):
        conn = db._conn  # type: ignore
        indexes = {row["name"] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()}
        assert "idx_asset_segments_asset" in indexes
        assert "idx_asset_segments_time" in indexes
        assert "idx_asset_transcripts_asset" in indexes
        assert "idx_asset_transcripts_time" in indexes


# ── AssetTranscript CRUD ────────────────────────────────────────

class TestAssetTranscript:
    def test_add_transcript(self, db: Database, sample_asset: int):
        tid = db.add_asset_transcript(
            AssetTranscript(
                asset_id=sample_asset,
                start_sec=1.0,
                end_sec=5.0,
                text="Hello world",
                language="en",
                is_auto_generated=False,
            )
        )
        assert tid > 0

    def test_list_transcripts_ordered(self, db_with_data):
        db, asset_id, tids, _ = db_with_data
        transcripts = db.list_asset_transcripts(asset_id)
        assert len(transcripts) == 5
        for t in transcripts:
            assert t.asset_id == asset_id
        # Verify ascending time order
        starts = [t.start_sec for t in transcripts]
        assert starts == sorted(starts)

    def test_list_transcripts_empty(self, db: Database):
        transcripts = db.list_asset_transcripts(9999)
        assert transcripts == []

    def test_transcript_fields_roundtrip(self, db: Database, sample_asset: int):
        tid = db.add_asset_transcript(
            AssetTranscript(
                asset_id=sample_asset,
                start_sec=10.5,
                end_sec=20.0,
                text="测试文本",
                language="zh",
                is_auto_generated=True,
            )
        )
        transcripts = db.list_asset_transcripts(sample_asset)
        t = transcripts[0]
        assert t.id == tid
        assert t.start_sec == 10.5
        assert t.end_sec == 20.0
        assert t.text == "测试文本"
        assert t.language == "zh"
        assert t.is_auto_generated is True

    def test_transcript_auto_flag_defaults_false(self, db: Database, sample_asset: int):
        db.add_asset_transcript(
            AssetTranscript(asset_id=sample_asset, start_sec=0.0, end_sec=1.0, text="x")
        )
        t = db.list_asset_transcripts(sample_asset)[0]
        assert t.is_auto_generated is False


# ── AssetSegment CRUD ───────────────────────────────────────────

class TestAssetSegment:
    def test_add_segment(self, db: Database, sample_asset: int):
        sid = db.add_asset_segment(
            AssetSegment(
                asset_id=sample_asset,
                start_sec=0.0,
                end_sec=10.0,
                duration_sec=10.0,
                transcript_text="some text",
                keyframe_paths=["kf1.jpg"],
                tags=["tag1"],
                quality_score=0.8,
            )
        )
        assert sid > 0

    def test_get_segment(self, db_with_data):
        db, _, _, sids = db_with_data
        sid = sids[0]
        seg = db.get_asset_segment(sid)
        assert seg is not None
        assert seg.id == sid
        assert seg.asset_id > 0
        assert seg.start_sec >= 0

    def test_get_segment_not_found(self, db: Database):
        assert db.get_asset_segment(99999) is None

    def test_update_segment(self, db_with_data):
        db, _, _, sids = db_with_data
        sid = sids[0]
        seg = db.get_asset_segment(sid)
        assert seg is not None

        seg.transcript_text = "updated text"
        seg.quality_score = 0.5
        seg.reviewed = True
        ok = db.update_asset_segment(seg)
        assert ok is True

        updated = db.get_asset_segment(sid)
        assert updated is not None
        assert updated.transcript_text == "updated text"
        assert updated.quality_score == 0.5
        assert updated.reviewed is True

    def test_update_segment_no_id_returns_false(self, db: Database):
        seg = AssetSegment(asset_id=1, start_sec=0.0, end_sec=1.0, duration_sec=1.0)
        assert db.update_asset_segment(seg) is False

    def test_list_segments_by_asset(self, db_with_data):
        db, asset_id, _, sids = db_with_data
        segments = db.list_asset_segments(asset_id=asset_id)
        assert len(segments) == len(sids)
        for s in segments:
            assert s.asset_id == asset_id

    def test_list_segments_all(self, db_with_data):
        db, _, _, sids = db_with_data
        all_segs = db.list_asset_segments(limit=1000)
        assert len(all_segs) >= len(sids)

    def test_list_segments_pagination(self, db: Database, sample_asset: int):
        # Insert 5 segments
        for i in range(5):
            db.add_asset_segment(
                AssetSegment(
                    asset_id=sample_asset,
                    start_sec=float(i * 10),
                    end_sec=float(i * 10 + 10),
                    duration_sec=10.0,
                )
            )
        page1 = db.list_asset_segments(limit=2, offset=0)
        page2 = db.list_asset_segments(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].id != page2[0].id

    def test_list_segments_empty(self, db: Database):
        assert db.list_asset_segments() == []

    def test_segment_json_fields_roundtrip(self, db: Database, sample_asset: int):
        paths = ["data/frames/frame_01.jpg", "data/frames/frame_02.jpg"]
        tags = ["science", "chemistry", "water"]
        sid = db.add_asset_segment(
            AssetSegment(
                asset_id=sample_asset,
                start_sec=0.0,
                end_sec=5.0,
                duration_sec=5.0,
                keyframe_paths=paths,
                tags=tags,
            )
        )
        seg = db.get_asset_segment(sid)
        assert seg is not None
        assert seg.keyframe_paths == paths
        assert seg.tags == tags

    def test_segment_json_fields_default_empty_list(self, db: Database, sample_asset: int):
        sid = db.add_asset_segment(
            AssetSegment(
                asset_id=sample_asset,
                start_sec=0.0,
                end_sec=1.0,
                duration_sec=1.0,
            )
        )
        seg = db.get_asset_segment(sid)
        assert seg is not None
        assert seg.keyframe_paths == []
        assert seg.tags == []

    def test_segment_created_at_is_datetime(self, db: Database, sample_asset: int):
        sid = db.add_asset_segment(
            AssetSegment(
                asset_id=sample_asset,
                start_sec=0.0,
                end_sec=1.0,
                duration_sec=1.0,
            )
        )
        seg = db.get_asset_segment(sid)
        assert seg is not None
        assert isinstance(seg.created_at, datetime)


# ── clear_asset_resource_data ───────────────────────────────────

class TestClearResourceData:
    def test_clear_removes_transcripts_and_segments(self, db_with_data):
        db, asset_id, tids, sids = db_with_data
        assert len(db.list_asset_transcripts(asset_id)) > 0
        assert len(db.list_asset_segments(asset_id=asset_id)) > 0

        db.clear_asset_resource_data(asset_id)

        assert db.list_asset_transcripts(asset_id) == []
        assert db.list_asset_segments(asset_id=asset_id) == []

    def test_clear_does_not_delete_asset(self, db_with_data):
        db, asset_id, _, _ = db_with_data
        assert db.get_asset(asset_id) is not None
        db.clear_asset_resource_data(asset_id)
        assert db.get_asset(asset_id) is not None

    def test_clear_nonexistent_asset_does_not_raise(self, db: Database):
        # Should not crash when clearing an asset_id that never existed
        db.clear_asset_resource_data(99999)


# ── _load_json_list edge cases ──────────────────────────────────

class TestLoadJsonList:
    """Test the internal _load_json_list helper via segment round-trip."""

    def test_none_becomes_empty_list(self, db: Database, sample_asset: int):
        sid = db.add_asset_segment(
            AssetSegment(
                asset_id=sample_asset,
                start_sec=0.0,
                end_sec=1.0,
                duration_sec=1.0,
                keyframe_paths=None,
                tags=None,
            )
        )
        seg = db.get_asset_segment(sid)
        assert seg is not None
        assert seg.keyframe_paths == []
        assert seg.tags == []

    def test_invalid_json_becomes_empty_list(self, db: Database, sample_asset: int):
        """Directly write invalid JSON to the DB to test _load_json_list."""
        conn = db._conn  # type: ignore
        conn.execute(
            """
            INSERT INTO asset_segments
                (asset_id, start_sec, end_sec, duration_sec, keyframe_paths, tags)
            VALUES (?, 0, 1, 1, 'not-json', 'not-json')
            """,
            (sample_asset,),
        )
        conn.commit()
        sid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        seg = db.get_asset_segment(sid)
        assert seg is not None
        assert seg.keyframe_paths == []
        assert seg.tags == []

    def test_non_list_json_becomes_empty_list(self, db: Database, sample_asset: int):
        conn = db._conn  # type: ignore
        conn.execute(
            """
            INSERT INTO asset_segments
                (asset_id, start_sec, end_sec, duration_sec, keyframe_paths, tags)
            VALUES (?, 0, 1, 1, '"string"', '42')
            """,
            (sample_asset,),
        )
        conn.commit()
        sid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        seg = db.get_asset_segment(sid)
        assert seg is not None
        assert seg.keyframe_paths == []
        assert seg.tags == []
