from __future__ import annotations

from videoforge.models import AssetMetadata
from videoforge.skills.base import AssetTagSkill


class CLIPGeminiProvider(AssetTagSkill):
    def __init__(self, config: dict) -> None:
        self.config = config

    def tag(self, asset_path: str) -> AssetMetadata:
        """Tag an asset using CLIP and Gemini."""
        raise NotImplementedError
