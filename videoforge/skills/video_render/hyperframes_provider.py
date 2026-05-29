from __future__ import annotations

from videoforge.models import RenderResult
from videoforge.skills.base import VideoRenderSkill


class HyperFramesProvider(VideoRenderSkill):
    def __init__(self, config: dict) -> None:
        self.config = config

    def render(self, scene: dict) -> RenderResult:
        """Render a video scene using HyperFrames."""
        raise NotImplementedError
