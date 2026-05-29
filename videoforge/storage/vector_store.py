from __future__ import annotations

from pathlib import Path


class VectorStore:
    """FAISS 向量存储（Phase 3 实现）"""

    def __init__(self, index_path: str | Path = "data/faiss_index"):
        self.index_path = Path(index_path)
        self._index = None  # faiss.Index, 延迟加载

    def add(self, embedding: list[float], metadata_id: int) -> None:
        """添加向量到索引"""
        raise NotImplementedError("Phase 3 实现")

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[tuple[int, float]]:
        """检索最相似的向量，返回 (metadata_id, score) 列表"""
        raise NotImplementedError("Phase 3 实现")

    def save(self) -> None:
        """持久化索引到磁盘"""
        raise NotImplementedError("Phase 3 实现")

    def load(self) -> None:
        """从磁盘加载索引"""
        raise NotImplementedError("Phase 3 实现")
