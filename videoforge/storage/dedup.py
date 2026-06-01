"""素材去重工具

支持两种去重策略：
1. 文件 hash 去重 - 完全相同的文件
2. CLIP 向量去重 - 视觉相似的素材 (相似度 > 0.95)
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from videoforge.storage import Asset, Database
from videoforge.storage.vector_store import VectorStore
from videoforge.utils.paths import get_absolute_path

logger = logging.getLogger(__name__)


@dataclass
class DuplicateGroup:
    """重复素材组"""
    original_id: int
    original_path: str
    duplicates: list[tuple[int, str, float]]  # (id, path, similarity)


def compute_file_hash(file_path: str | Path) -> str:
    """计算文件 MD5 哈希"""
    path = Path(file_path)
    if not path.exists():
        return ""

    hasher = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def find_hash_duplicates() -> list[DuplicateGroup]:
    """查找文件哈希完全相同的重复素材"""
    hash_to_assets: dict[str, list[Asset]] = {}

    with Database() as db:
        assets = db.list_assets(limit=10000)

        for asset in assets:
            asset_path = get_absolute_path(asset.path)
            if not asset_path.exists():
                continue

            file_hash = compute_file_hash(asset_path)
            if not file_hash:
                continue

            if file_hash not in hash_to_assets:
                hash_to_assets[file_hash] = []
            hash_to_assets[file_hash].append(asset)

    groups = []
    for file_hash, assets in hash_to_assets.items():
        if len(assets) < 2:
            continue

        original = assets[0]
        duplicates = [(a.id, a.path, 1.0) for a in assets[1:]]

        groups.append(DuplicateGroup(
            original_id=original.id,
            original_path=original.path,
            duplicates=duplicates,
        ))

    return groups


def find_visual_duplicates(
    threshold: float = 0.95,
    vector_store: VectorStore | None = None,
) -> list[DuplicateGroup]:
    """查找视觉相似的重复素材（基于 CLIP 向量）

    Args:
        threshold: 相似度阈值，默认 0.95
        vector_store: 向量存储实例

    Returns:
        重复组列表
    """
    if vector_store is None:
        vector_store = VectorStore()
        vector_store.load()

    if vector_store.active_count < 2:
        logger.info("Not enough indexed assets for visual deduplication")
        return []

    processed_ids: set[int] = set()
    groups: list[DuplicateGroup] = []

    with Database() as db:
        for asset_id in list(vector_store._asset_to_faiss.keys()):
            if asset_id in processed_ids:
                continue

            embedding = vector_store.get_embedding(asset_id)
            if embedding is None:
                continue

            hits = vector_store.search(embedding, top_k=10, threshold=threshold)

            duplicates = []
            for hit_id, score in hits:
                if hit_id == asset_id:
                    continue
                if hit_id in processed_ids:
                    continue

                hit_asset = db.get_asset(hit_id)
                if hit_asset:
                    duplicates.append((hit_id, hit_asset.path, score))
                    processed_ids.add(hit_id)

            if duplicates:
                original = db.get_asset(asset_id)
                if original:
                    groups.append(DuplicateGroup(
                        original_id=asset_id,
                        original_path=original.path,
                        duplicates=duplicates,
                    ))

            processed_ids.add(asset_id)

    return groups


def deduplicate_assets(
    method: str = "hash",
    threshold: float = 0.95,
    dry_run: bool = True,
) -> dict:
    """执行去重

    Args:
        method: "hash" 或 "visual"
        threshold: 视觉去重的相似度阈值
        dry_run: 仅预览不执行删除

    Returns:
        去重统计信息
    """
    if method == "hash":
        groups = find_hash_duplicates()
    elif method == "visual":
        groups = find_visual_duplicates(threshold)
    else:
        raise ValueError(f"Unknown deduplication method: {method}")

    total_duplicates = sum(len(g.duplicates) for g in groups)
    freed_bytes = 0

    for group in groups:
        for dup_id, dup_path, similarity in group.duplicates:
            dup_file = get_absolute_path(dup_path)
            if dup_file.exists():
                freed_bytes += dup_file.stat().st_size

                if not dry_run:
                    logger.info(f"Removing duplicate: {dup_path} (similar to {group.original_path}, score={similarity:.3f})")
                    dup_file.unlink()

                    with Database() as db:
                        db.delete_asset(dup_id)

    return {
        "method": method,
        "dry_run": dry_run,
        "groups": len(groups),
        "duplicates": total_duplicates,
        "freed_bytes": freed_bytes,
        "details": groups if dry_run else [],
    }


def check_duplicate_before_add(
    file_path: str | Path,
    check_hash: bool = True,
    check_visual: bool = False,
    visual_threshold: float = 0.95,
) -> Asset | None:
    """在添加新素材前检查是否已存在重复

    Args:
        file_path: 新文件路径
        check_hash: 检查文件哈希
        check_visual: 检查视觉相似度
        visual_threshold: 视觉相似度阈值

    Returns:
        如果找到重复，返回已存在的 Asset；否则返回 None
    """
    path = Path(file_path)
    if not path.exists():
        return None

    if check_hash:
        new_hash = compute_file_hash(path)

        with Database() as db:
            for asset in db.list_assets(limit=10000):
                asset_path = get_absolute_path(asset.path)
                if asset_path.exists():
                    if compute_file_hash(asset_path) == new_hash:
                        logger.info(f"Hash duplicate found: {asset.path}")
                        return asset

    if check_visual:
        try:
            from videoforge.skills.asset_tag.clip_embedder import get_asset_embedding

            new_embedding = get_asset_embedding(path)
            if new_embedding is not None:
                vector_store = VectorStore()
                vector_store.load()

                hits = vector_store.search(new_embedding, top_k=1, threshold=visual_threshold)
                if hits:
                    asset_id, score = hits[0]
                    with Database() as db:
                        existing = db.get_asset(asset_id)
                        if existing:
                            logger.info(f"Visual duplicate found: {existing.path} (score={score:.3f})")
                            return existing
        except Exception as e:
            logger.debug(f"Visual dedup check failed: {e}")

    return None
