"""FAISS 向量存储

支持向量的增删查和持久化。使用 IndexFlatIP (内积/余弦相似度)。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import faiss
import numpy as np

from videoforge.utils.paths import PROJECT_ROOT

logger = logging.getLogger(__name__)


class VectorStore:
    """FAISS 向量存储"""

    def __init__(
        self,
        index_path: str | Path | None = None,
        dimension: int = 512,
    ):
        """初始化向量存储

        Args:
            index_path: 索引文件路径（不含扩展名），默认 data/faiss_index
            dimension: 向量维度，默认512 (CLIP ViT-B/32)
        """
        if index_path is None:
            index_path = PROJECT_ROOT / "data" / "faiss_index"
        self.index_path = Path(index_path)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        self.dimension = dimension
        self._index: faiss.IndexFlatIP | None = None
        self._id_map: dict[int, int] = {}  # faiss_idx -> asset_id
        self._asset_to_faiss: dict[int, int] = {}  # asset_id -> faiss_idx
        self._next_faiss_idx = 0

    @property
    def bin_path(self) -> Path:
        return self.index_path.with_suffix(".bin")

    @property
    def map_path(self) -> Path:
        return self.index_path.with_suffix(".json")

    def _ensure_index(self) -> faiss.IndexFlatIP:
        """确保索引已初始化"""
        if self._index is None:
            self._index = faiss.IndexFlatIP(self.dimension)
        return self._index

    def add(self, embedding: np.ndarray | list[float], asset_id: int) -> None:
        """添加向量到索引

        Args:
            embedding: 向量（会自动归一化）
            asset_id: 关联的素材 ID
        """
        index = self._ensure_index()

        vec = np.array(embedding, dtype=np.float32).reshape(1, -1)
        vec = vec / np.linalg.norm(vec)

        if asset_id in self._asset_to_faiss:
            logger.debug(f"Asset {asset_id} already in index, skipping")
            return

        faiss_idx = self._next_faiss_idx
        index.add(vec)

        self._id_map[faiss_idx] = asset_id
        self._asset_to_faiss[asset_id] = faiss_idx
        self._next_faiss_idx += 1

    def remove(self, asset_id: int) -> bool:
        """从索引中移除向量（标记删除，重建时清理）

        Note: FAISS IndexFlatIP 不支持直接删除，这里只删除映射
        """
        if asset_id not in self._asset_to_faiss:
            return False

        faiss_idx = self._asset_to_faiss.pop(asset_id)
        del self._id_map[faiss_idx]
        return True

    def search(
        self,
        query_embedding: np.ndarray | list[float],
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> list[tuple[int, float]]:
        """检索最相似的向量

        Args:
            query_embedding: 查询向量
            top_k: 返回数量
            threshold: 最低相似度阈值

        Returns:
            [(asset_id, score), ...] 按相似度降序
        """
        index = self._ensure_index()
        if index.ntotal == 0:
            return []

        vec = np.array(query_embedding, dtype=np.float32).reshape(1, -1)
        vec = vec / np.linalg.norm(vec)

        k = min(top_k * 2, index.ntotal)  # 多取一些以过滤已删除的
        scores, indices = index.search(vec, k)

        results = []
        for score, faiss_idx in zip(scores[0], indices[0]):
            if faiss_idx < 0:
                continue
            if faiss_idx not in self._id_map:
                continue
            if score < threshold:
                continue

            asset_id = self._id_map[faiss_idx]
            results.append((asset_id, float(score)))

            if len(results) >= top_k:
                break

        return results

    def search_by_text(self, text: str, top_k: int = 5, threshold: float = 0.0) -> list[tuple[int, float]]:
        """使用文本查询向量检索

        需要 CLIP 可用。
        """
        from videoforge.skills.asset_tag.clip_embedder import get_text_embedding

        embedding = get_text_embedding(text)
        if embedding is None:
            logger.warning("Text embedding not available (CLIP not installed?)")
            return []

        return self.search(embedding, top_k, threshold)

    def get_embedding(self, asset_id: int) -> np.ndarray | None:
        """获取指定素材的向量"""
        if asset_id not in self._asset_to_faiss:
            return None

        faiss_idx = self._asset_to_faiss[asset_id]
        index = self._ensure_index()

        if faiss_idx >= index.ntotal:
            return None

        return index.reconstruct(faiss_idx)

    def save(self) -> None:
        """持久化索引到磁盘"""
        index = self._ensure_index()

        faiss.write_index(index, str(self.bin_path))

        map_data = {
            "dimension": self.dimension,
            "next_idx": self._next_faiss_idx,
            "id_map": {str(k): v for k, v in self._id_map.items()},
            "asset_to_faiss": {str(k): v for k, v in self._asset_to_faiss.items()},
        }
        with open(self.map_path, "w", encoding="utf-8") as f:
            json.dump(map_data, f)

        logger.info(f"Saved vector index: {index.ntotal} vectors -> {self.bin_path}")

    def load(self) -> bool:
        """从磁盘加载索引

        Returns:
            是否成功加载
        """
        if not self.bin_path.exists() or not self.map_path.exists():
            logger.info("No existing index found, starting fresh")
            return False

        try:
            self._index = faiss.read_index(str(self.bin_path))

            with open(self.map_path, encoding="utf-8") as f:
                map_data = json.load(f)

            self.dimension = map_data.get("dimension", 512)
            self._next_faiss_idx = map_data.get("next_idx", 0)
            self._id_map = {int(k): v for k, v in map_data.get("id_map", {}).items()}
            self._asset_to_faiss = {int(k): v for k, v in map_data.get("asset_to_faiss", {}).items()}

            logger.info(f"Loaded vector index: {self._index.ntotal} vectors from {self.bin_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            self._index = None
            return False

    def rebuild(self) -> None:
        """重建索引（清理已删除的向量）"""
        if self._index is None or self._index.ntotal == 0:
            return

        old_index = self._index
        new_index = faiss.IndexFlatIP(self.dimension)

        new_id_map = {}
        new_asset_to_faiss = {}
        new_idx = 0

        for old_faiss_idx, asset_id in sorted(self._id_map.items()):
            vec = old_index.reconstruct(old_faiss_idx).reshape(1, -1)
            new_index.add(vec)
            new_id_map[new_idx] = asset_id
            new_asset_to_faiss[asset_id] = new_idx
            new_idx += 1

        self._index = new_index
        self._id_map = new_id_map
        self._asset_to_faiss = new_asset_to_faiss
        self._next_faiss_idx = new_idx

        logger.info(f"Rebuilt index: {old_index.ntotal} -> {new_index.ntotal} vectors")

    @property
    def size(self) -> int:
        """当前索引中的向量数量（包括已删除的）"""
        return self._index.ntotal if self._index else 0

    @property
    def active_count(self) -> int:
        """活跃向量数量（不含已删除的）"""
        return len(self._id_map)

    def __len__(self) -> int:
        return self.active_count


def get_vector_store() -> VectorStore:
    """获取全局向量存储实例"""
    store = VectorStore()
    store.load()
    return store
