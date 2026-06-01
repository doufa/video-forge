"""项目路径工具

所有路径在数据库和配置中以相对路径存储，运行时动态解析为绝对路径。
这使得整个项目目录可以作为自包含工作空间迁移。
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def get_absolute_path(relative_path: str | Path) -> Path:
    """将相对路径转换为绝对路径"""
    path = Path(relative_path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def get_relative_path(absolute_path: str | Path) -> str:
    """将绝对路径转换为相对于项目根目录的路径（用于存储）"""
    path = Path(absolute_path).resolve()
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def generate_asset_filename(content: bytes, query: str, ext: str) -> str:
    """生成素材文件名: {hash8}_{slug}.{ext}

    Args:
        content: 文件内容（用于计算 hash）
        query: 原始搜索词（用于生成可读 slug）
        ext: 文件扩展名（不含点号）

    Returns:
        格式化的文件名，如 "a1b2c3d4_einstein_portrait.mp4"
    """
    hash8 = hashlib.md5(content).hexdigest()[:8]
    slug = re.sub(r"[^a-z0-9]+", "_", query.lower())[:40].strip("_")
    if not slug:
        slug = "asset"
    return f"{hash8}_{slug}.{ext}"


def generate_asset_filename_from_path(file_path: str | Path, query: str) -> str:
    """从已有文件生成规范文件名"""
    path = Path(file_path)
    content = path.read_bytes()
    ext = path.suffix.lstrip(".")
    return generate_asset_filename(content, query, ext)
