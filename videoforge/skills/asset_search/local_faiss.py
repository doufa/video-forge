from __future__ import annotations

from videoforge.models import AssetResult
from videoforge.skills.base import AssetSearchSkill


class LocalFAISSProvider(AssetSearchSkill):
    def __init__(self, config: dict) -> None:
        self.config = config

    def search(self, query: str) -> list[AssetResult]:
        """Search for assets using local FAISS index."""
        raise NotImplementedError
