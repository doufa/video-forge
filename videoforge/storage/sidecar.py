"""JSON Sidecar 元数据管理

每个素材文件 xxx.mp4 旁边放 xxx.meta.json 存储元数据。
这种模式让元数据与文件绑定，便于文件系统层面的管理。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class AssetMetadata:
    """素材元数据结构"""
    source: str = "local"
    original_query: str = ""
    original_url: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    duration_sec: float | None = None
    resolution: str = ""
    file_size: int | None = None
    reviewed: bool = False
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if data["duration_sec"] is None:
            del data["duration_sec"]
        if data["file_size"] is None:
            del data["file_size"]
        if not data["resolution"]:
            del data["resolution"]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetMetadata":
        return cls(
            source=data.get("source", "local"),
            original_query=data.get("original_query", ""),
            original_url=data.get("original_url", ""),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            duration_sec=data.get("duration_sec"),
            resolution=data.get("resolution", ""),
            file_size=data.get("file_size"),
            reviewed=data.get("reviewed", False),
            created_at=data.get("created_at", ""),
        )


def get_sidecar_path(asset_path: str | Path) -> Path:
    """获取素材对应的 sidecar 路径: xxx.mp4 -> xxx.meta.json"""
    path = Path(asset_path)
    return path.with_suffix(".meta.json")


def read_sidecar(asset_path: str | Path) -> AssetMetadata | None:
    """读取素材的 sidecar 元数据

    Args:
        asset_path: 素材文件路径（非 sidecar 路径）

    Returns:
        AssetMetadata 对象，如果 sidecar 不存在则返回 None
    """
    sidecar_path = get_sidecar_path(asset_path)
    if not sidecar_path.exists():
        return None

    try:
        with open(sidecar_path, encoding="utf-8") as f:
            data = json.load(f)
        return AssetMetadata.from_dict(data)
    except (json.JSONDecodeError, OSError):
        return None


def write_sidecar(asset_path: str | Path, metadata: AssetMetadata) -> Path:
    """写入素材的 sidecar 元数据

    Args:
        asset_path: 素材文件路径（非 sidecar 路径）
        metadata: 要写入的元数据

    Returns:
        sidecar 文件路径
    """
    sidecar_path = get_sidecar_path(asset_path)
    with open(sidecar_path, "w", encoding="utf-8") as f:
        json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False)
    return sidecar_path


def update_sidecar(asset_path: str | Path, **kwargs) -> AssetMetadata:
    """更新 sidecar 的部分字段

    Args:
        asset_path: 素材文件路径
        **kwargs: 要更新的字段

    Returns:
        更新后的 AssetMetadata
    """
    metadata = read_sidecar(asset_path) or AssetMetadata()

    for key, value in kwargs.items():
        if hasattr(metadata, key):
            setattr(metadata, key, value)

    write_sidecar(asset_path, metadata)
    return metadata


def delete_sidecar(asset_path: str | Path) -> bool:
    """删除素材的 sidecar 文件

    Returns:
        是否成功删除
    """
    sidecar_path = get_sidecar_path(asset_path)
    if sidecar_path.exists():
        sidecar_path.unlink()
        return True
    return False
