from __future__ import annotations

from pathlib import Path

from videoforge.models import AssetMetadata
from videoforge.skills.base import AssetTagSkill


class DummyTagProvider(AssetTagSkill):
    """
    一个空的打标占位符。
    因为当前直接使用了在线搜索引擎的搜索能力，不需要在本地做复杂的特征提取。
    """

    def __init__(self, config: dict):
        pass

    def tag(self, asset_path: str, **kwargs) -> AssetMetadata:
        # 直接返回空打标数据
        return AssetMetadata(
            asset_path=Path(asset_path),
            description="Dummy tag placeholder",
            tags=[],
            embedding=[],
            reviewed=True
        )
