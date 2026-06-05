"""Hybrid segment search combining visual and text FAISS indices."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from videoforge.resource_library.models import ResourceSearchHit
from videoforge.storage.database import AssetSegment, Database
from videoforge.storage.vector_store import VectorStore
from videoforge.utils.paths import PROJECT_ROOT, get_absolute_path

logger = logging.getLogger(__name__)

SEGMENT_VISUAL_INDEX = PROJECT_ROOT / "data" / "segment_visual_index"
SEGMENT_TEXT_INDEX = PROJECT_ROOT / "data" / "segment_text_index"

VISUAL_WEIGHT = 0.45
TEXT_WEIGHT = 0.45
QUALITY_WEIGHT = 0.10


def _compute_quality_bonus(segment: AssetSegment) -> float:
    """Compute quality bonus for a segment.

    Prefers segments with:
    - Duration between 8-20 seconds
    - Substantial transcript text
    - Keyframes present
    """
    score = 0.5

    duration = segment.duration_sec
    if 8.0 <= duration <= 20.0:
        score += 0.2
    elif 5.0 <= duration <= 30.0:
        score += 0.1

    if segment.transcript_text:
        text_len = len(segment.transcript_text)
        if text_len > 50:
            score += 0.2
        elif text_len > 20:
            score += 0.1

    if segment.keyframe_paths and len(segment.keyframe_paths) >= 3:
        score += 0.1

    return min(score, 1.0)


class ResourceSearcher:
    """Search indexed video segments using hybrid visual + text scoring."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = db_path
        self._segment_cache: dict[int, AssetSegment] = {}

    def _load_segment_cache(self) -> None:
        if self._segment_cache:
            return
        with Database(self.db_path) as db:
            segments = db.list_asset_segments(limit=100_000)
            for seg in segments:
                if seg.id is not None:
                    self._segment_cache[seg.id] = seg

    def search(
        self,
        query: str,
        limit: int = 10,
        *,
        visual_weight: float = VISUAL_WEIGHT,
        text_weight: float = TEXT_WEIGHT,
        quality_weight: float = QUALITY_WEIGHT,
    ) -> list[ResourceSearchHit]:
        """Search segments matching a text query.

        Searches both visual and transcript FAISS indices and merges
        results with weighted scoring:
            final = 0.45*visual + 0.45*transcript + 0.10*quality
        """
        from videoforge.skills.asset_tag.clip_embedder import get_text_embedding

        query_embedding = get_text_embedding(query)
        if query_embedding is None:
            logger.warning("CLIP text embedding unavailable, cannot search")
            return []

        visual_store = VectorStore(index_path=SEGMENT_VISUAL_INDEX)
        text_store = VectorStore(index_path=SEGMENT_TEXT_INDEX)

        visual_store.load()
        text_store.load()

        visual_results = visual_store.search(query_embedding, top_k=limit * 2)
        text_results = text_store.search(query_embedding, top_k=limit * 2)

        scores: dict[int, dict[str, float]] = {}

        for segment_id, score in visual_results:
            if segment_id not in scores:
                scores[segment_id] = {"visual": 0.0, "text": 0.0, "quality": 0.0}
            scores[segment_id]["visual"] = score

        for segment_id, score in text_results:
            if segment_id not in scores:
                scores[segment_id] = {"visual": 0.0, "text": 0.0, "quality": 0.0}
            scores[segment_id]["text"] = score

        self._load_segment_cache()

        for segment_id in scores:
            segment = self._segment_cache.get(segment_id)
            if segment:
                scores[segment_id]["quality"] = _compute_quality_bonus(segment)

        hits: list[ResourceSearchHit] = []

        with Database(self.db_path) as db:
            for segment_id, score_dict in scores.items():
                segment = self._segment_cache.get(segment_id)
                if segment is None:
                    continue

                visual_score = score_dict["visual"]
                text_score = score_dict["text"]
                quality_score = score_dict["quality"]

                final_score = (
                    visual_weight * visual_score
                    + text_weight * text_score
                    + quality_weight * quality_score
                )

                if visual_score > 0 and text_score > 0:
                    match_type = "hybrid"
                elif visual_score > 0:
                    match_type = "visual"
                else:
                    match_type = "text"

                asset = db.get_asset(segment.asset_id)
                asset_path = (
                    get_absolute_path(asset.path)
                    if asset
                    else Path(f"asset_{segment.asset_id}")
                )

                keyframe_paths = [
                    get_absolute_path(p) for p in (segment.keyframe_paths or [])
                ]

                hits.append(
                    ResourceSearchHit(
                        asset_path=asset_path,
                        segment_id=segment.id or 0,
                        start_sec=segment.start_sec,
                        end_sec=segment.end_sec,
                        score=final_score,
                        match_type=match_type,
                        transcript_text=segment.transcript_text,
                        keyframe_paths=keyframe_paths,
                    )
                )

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]
