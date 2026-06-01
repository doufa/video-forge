"""本地 FAISS 混合检索

三级检索策略：
1. 本地向量检索 - FAISS similarity search
2. 本地关键词检索 - SQLite FTS (description + tags)
3. 在线兜底 - yt-dlp (现有逻辑)
"""

from __future__ import annotations

import logging
from pathlib import Path

from videoforge.models import AssetResult
from videoforge.skills.asset_search.ytdlp_provider import YTDLPSearchProvider
from videoforge.skills.base import AssetSearchSkill
from videoforge.storage import Database
from videoforge.storage.vector_store import VectorStore, get_vector_store
from videoforge.utils.paths import get_absolute_path

logger = logging.getLogger(__name__)


class LocalFAISSProvider(AssetSearchSkill):
    """本地 FAISS 混合检索器"""

    def __init__(self, config: dict):
        self.config = config
        faiss_config = config.get("local_faiss", {})

        self.vector_threshold = faiss_config.get("threshold", 0.5)
        self.top_k = faiss_config.get("top_k", 5)
        self.enable_fallback = config.get("fallback") is not None

        self._vector_store: VectorStore | None = None
        self._fallback_provider: YTDLPSearchProvider | None = None

    @property
    def vector_store(self) -> VectorStore:
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store

    @property
    def fallback_provider(self) -> YTDLPSearchProvider | None:
        if self._fallback_provider is None and self.enable_fallback:
            self._fallback_provider = YTDLPSearchProvider(self.config)
        return self._fallback_provider

    def search(self, query: str, top_k: int | None = None, **kwargs) -> list[AssetResult]:
        """混合检索素材

        Args:
            query: 搜索查询
            top_k: 返回数量

        Returns:
            AssetResult 列表，按相关度排序
        """
        if not query.strip():
            return []

        k = top_k or self.top_k
        results: list[AssetResult] = []

        results = self._search_by_vector(query, k)
        if results:
            logger.info(f"Vector search found {len(results)} results for '{query}'")
            return results[:k]

        results = self._search_by_keywords(query, k)
        if results:
            logger.info(f"Keyword search found {len(results)} results for '{query}'")
            return results[:k]

        if self.fallback_provider:
            logger.info(f"Falling back to online search for '{query}'")
            return self.fallback_provider.search(query, top_k=k)

        logger.warning(f"No results found for '{query}'")
        return []

    def _search_by_vector(self, query: str, top_k: int) -> list[AssetResult]:
        """向量相似度检索"""
        try:
            from videoforge.skills.asset_tag.clip_embedder import is_clip_available

            if not is_clip_available():
                logger.debug("CLIP not available, skipping vector search")
                return []

            hits = self.vector_store.search_by_text(query, top_k, self.vector_threshold)
            if not hits:
                return []

            results = []
            with Database() as db:
                for asset_id, score in hits:
                    asset = db.get_asset(asset_id)
                    if asset is None:
                        continue

                    asset_path = get_absolute_path(asset.path)
                    if not asset_path.exists():
                        logger.debug(f"Asset file not found: {asset_path}")
                        continue

                    results.append(AssetResult(
                        asset_path=asset_path,
                        score=score,
                        source="local_vector",
                        description=asset.description or asset.original_query,
                        asset_type=asset.asset_type,
                    ))

            return results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def _search_by_keywords(self, query: str, top_k: int) -> list[AssetResult]:
        """关键词检索（基于 SQLite LIKE）"""
        try:
            keywords = query.lower().split()
            if not keywords:
                return []

            with Database() as db:
                all_assets = db.list_assets(limit=1000)

                scored_assets = []
                for asset in all_assets:
                    score = self._calculate_keyword_score(asset, keywords)
                    if score > 0:
                        scored_assets.append((asset, score))

                scored_assets.sort(key=lambda x: x[1], reverse=True)

                results = []
                for asset, score in scored_assets[:top_k]:
                    asset_path = get_absolute_path(asset.path)
                    if not asset_path.exists():
                        continue

                    results.append(AssetResult(
                        asset_path=asset_path,
                        score=score,
                        source="local_keyword",
                        description=asset.description or asset.original_query,
                        asset_type=asset.asset_type,
                    ))

                return results

        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            return []

    def _calculate_keyword_score(self, asset, keywords: list[str]) -> float:
        """计算关键词匹配分数"""
        score = 0.0

        searchable_text = " ".join([
            asset.original_query or "",
            asset.description or "",
            " ".join(asset.tags or []),
            asset.filename_original or "",
        ]).lower()

        for keyword in keywords:
            if len(keyword) < 2:
                continue
            if keyword in searchable_text:
                score += 1.0
                if keyword in (asset.tags or []):
                    score += 0.5

        if keywords:
            score = score / len(keywords)

        return score

    def add_to_index(self, asset_path: str | Path, asset_id: int) -> bool:
        """将素材添加到向量索引

        Args:
            asset_path: 素材文件路径
            asset_id: 数据库中的素材 ID

        Returns:
            是否成功添加
        """
        try:
            from videoforge.skills.asset_tag.clip_embedder import get_asset_embedding

            embedding = get_asset_embedding(asset_path)
            if embedding is None:
                logger.warning(f"Failed to extract embedding for {asset_path}")
                return False

            self.vector_store.add(embedding, asset_id)
            return True

        except Exception as e:
            logger.error(f"Failed to add asset to index: {e}")
            return False

    def save_index(self) -> None:
        """保存向量索引"""
        self.vector_store.save()

    def get_index_stats(self) -> dict:
        """获取索引统计信息"""
        return {
            "total_vectors": self.vector_store.size,
            "active_vectors": self.vector_store.active_count,
            "vector_threshold": self.vector_threshold,
        }
