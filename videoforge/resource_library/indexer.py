from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from videoforge.resource_library.downloader import DownloadedResource, download_video_resource, local_video_resource
from videoforge.resource_library.frame_sampler import sample_segment_keyframes
from videoforge.resource_library.models import IngestResult, SceneSegment, TranscriptCue
from videoforge.resource_library.scene_splitter import detect_scene_segments
from videoforge.resource_library.subtitles import (
    assign_transcripts_to_segments,
    choose_preferred_subtitle,
    infer_subtitle_language,
    is_auto_subtitle,
    parse_subtitle_file,
)
from videoforge.storage.database import Asset, AssetSegment, AssetTranscript, Database
from videoforge.storage.vector_store import VectorStore
from videoforge.utils.paths import KEYFRAMES_DIR, PROJECT_ROOT, get_absolute_path, get_relative_path

logger = logging.getLogger(__name__)


SEGMENT_VISUAL_INDEX = PROJECT_ROOT / "data" / "segment_visual_index"
SEGMENT_TEXT_INDEX = PROJECT_ROOT / "data" / "segment_text_index"


class ResourceIndexer:
    """Build segment-level resource library metadata and FAISS indexes."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = db_path

    def ingest_url(self, url: str) -> IngestResult:
        resource = download_video_resource(url)
        return self.ingest_resource(resource, source="youtube")

    def ingest_local(
        self,
        video_path: str | Path,
        subtitle_paths: list[str | Path] | None = None,
    ) -> IngestResult:
        resource = local_video_resource(video_path, subtitle_paths)
        return self.ingest_resource(resource, source="local")

    def ingest_resource(self, resource: DownloadedResource, source: str = "local") -> IngestResult:
        """Ingest a downloaded or local resource into the segment library."""
        video_path = resource.video_path
        cues = self._load_preferred_subtitles(resource.subtitle_paths)
        segments = detect_scene_segments(video_path)
        segments = assign_transcripts_to_segments(cues, segments)

        with Database(self.db_path) as db:
            asset_id = self._ensure_asset(db, resource, source=source)
            db.clear_asset_resource_data(asset_id)

            for cue in cues:
                db.add_asset_transcript(
                    AssetTranscript(
                        asset_id=asset_id,
                        start_sec=cue.start_sec,
                        end_sec=cue.end_sec,
                        text=cue.text,
                        language=cue.language,
                        is_auto_generated=cue.is_auto_generated,
                    )
                )

            created_segments = []
            for segment in segments:
                segment_id = db.add_asset_segment(
                    AssetSegment(
                        asset_id=asset_id,
                        start_sec=segment.start_sec,
                        end_sec=segment.end_sec,
                        duration_sec=segment.duration_sec,
                        transcript_text=segment.transcript_text,
                        tags=segment.tags,
                        quality_score=segment.quality_score,
                    )
                )

                keyframe_dir = KEYFRAMES_DIR / f"asset_{asset_id}" / f"segment_{segment_id}"
                keyframes = sample_segment_keyframes(
                    video_path,
                    keyframe_dir,
                    segment.start_sec,
                    segment.end_sec,
                )
                db_segment = db.get_asset_segment(segment_id)
                if db_segment:
                    db_segment.keyframe_paths = [get_relative_path(path) for path in keyframes]
                    db.update_asset_segment(db_segment)
                    created_segments.append(db_segment)

            visual_vectors, text_vectors = self._index_segments(created_segments)

        return IngestResult(
            asset_id=asset_id,
            asset_path=video_path,
            segments_created=len(created_segments),
            transcripts_created=len(cues),
            visual_vectors=visual_vectors,
            text_vectors=text_vectors,
        )

    def rebuild_segment_indexes(self) -> tuple[int, int]:
        """Rebuild segment-level visual and transcript indexes from SQLite metadata."""
        with Database(self.db_path) as db:
            segments = db.list_asset_segments(limit=100000)
        return self._index_segments(segments, fresh=True)

    def _ensure_asset(self, db: Database, resource: DownloadedResource, source: str) -> int:
        rel_path = get_relative_path(resource.video_path)
        existing = db.get_asset_by_path(rel_path)
        if existing and existing.id is not None:
            return existing.id

        info = self._load_info(resource.info_path)
        asset = Asset(
            path=rel_path,
            asset_type="video",
            source=source,
            original_query=resource.title,
            original_url=resource.source_url or info.get("webpage_url", ""),
            filename_original=resource.video_path.name,
            description=info.get("title", resource.title),
            tags=[],
            duration_sec=info.get("duration"),
            width=info.get("width"),
            height=info.get("height"),
            file_size=resource.video_path.stat().st_size if resource.video_path.exists() else None,
            reviewed=False,
        )
        return db.add_asset(asset)

    def _load_info(self, info_path: Path | None) -> dict:
        if not info_path or not info_path.exists():
            return {}
        try:
            return json.loads(info_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _load_preferred_subtitles(self, subtitle_paths: list[Path]) -> list[TranscriptCue]:
        subtitle_path = choose_preferred_subtitle(subtitle_paths)
        if not subtitle_path:
            return []
        return parse_subtitle_file(
            subtitle_path,
            language=infer_subtitle_language(subtitle_path),
            is_auto_generated=is_auto_subtitle(subtitle_path),
        )

    def _index_segments(
        self,
        segments: list[AssetSegment],
        fresh: bool = False,
    ) -> tuple[int, int]:
        visual_store = VectorStore(index_path=SEGMENT_VISUAL_INDEX)
        text_store = VectorStore(index_path=SEGMENT_TEXT_INDEX)
        if not fresh:
            visual_store.load()
            text_store.load()

        visual_vectors = 0
        text_vectors = 0

        with Database(self.db_path) as db:
            for segment in segments:
                if segment.id is None:
                    continue

                visual_embedding = self._segment_visual_embedding(segment)
                text_embedding = self._segment_text_embedding(segment)
                changed = False

                if visual_embedding is not None:
                    visual_store.add(visual_embedding, segment.id)
                    segment.visual_embedding_id = f"segment:{segment.id}:visual"
                    visual_vectors += 1
                    changed = True

                if text_embedding is not None:
                    text_store.add(text_embedding, segment.id)
                    segment.text_embedding_id = f"segment:{segment.id}:text"
                    text_vectors += 1
                    changed = True

                if changed:
                    db.update_asset_segment(segment)

        if visual_vectors or fresh:
            visual_store.save()
        if text_vectors or fresh:
            text_store.save()

        return visual_vectors, text_vectors

    def _segment_visual_embedding(self, segment: AssetSegment) -> np.ndarray | None:
        if not segment.keyframe_paths:
            return None

        try:
            from videoforge.skills.asset_tag.clip_embedder import get_image_embedding
        except Exception as exc:
            logger.warning("CLIP image embedding unavailable: %s", exc)
            return None

        embeddings = []
        for frame_path in segment.keyframe_paths:
            embedding = get_image_embedding(get_absolute_path(frame_path))
            if embedding is not None:
                embeddings.append(embedding)

        if not embeddings:
            return None

        vector = np.mean(embeddings, axis=0)
        norm = np.linalg.norm(vector)
        if norm == 0:
            return None
        return (vector / norm).astype(np.float32)

    def _segment_text_embedding(self, segment: AssetSegment) -> np.ndarray | None:
        if not segment.transcript_text.strip():
            return None

        try:
            from videoforge.skills.asset_tag.clip_embedder import get_text_embedding
        except Exception as exc:
            logger.warning("CLIP text embedding unavailable: %s", exc)
            return None

        return get_text_embedding(segment.transcript_text)
